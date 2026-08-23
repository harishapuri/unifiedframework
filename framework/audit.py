"""SHA-256 hash-chained append-only audit log.

Each row seals `{event, traces, action, outcome, extra, prev, ts, index}`.
`prev` is the previous row's hash (64 zeros for the first row).

Two writers used to append with a stale tip and fork the file — verify then
failed forever and the demo showed "log is broken". Append now takes an
exclusive lock, reloads the tip from disk, then writes. A file that is
already forked is repaired: the longest valid prefix is kept, the rest is
moved to `*.broken`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # Windows — demo host is macOS; lock becomes a no-op
    fcntl = None  # type: ignore


GENESIS = "0" * 64


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def _line(entry: dict[str, Any]) -> str:
    return _canonical(entry)


def _hash_body(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(body).encode()).hexdigest()


def _entry_ok(entry: dict[str, Any], prev: str) -> bool:
    if "hash" not in entry:
        return False
    copy = {k: v for k, v in entry.items() if k != "hash"}
    if copy.get("prev") != prev:
        return False
    return _hash_body(copy) == entry["hash"]


class AuditChain:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.entries: list[dict[str, Any]] = []
        self._prev = GENESIS
        self.repaired = False
        if path and path.exists():
            self._load(path)
            self.repaired = self._repair_if_needed()

    def _parse(self, text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            out.append(json.loads(line))
        return out

    def _load(self, path: Path) -> None:
        self.entries = self._parse(path.read_text())
        self._prev = self.entries[-1]["hash"] if self.entries else GENESIS

    def _reload_from_disk(self) -> None:
        self.entries = []
        self._prev = GENESIS
        if self.path and self.path.exists():
            self._load(self.path)

    def _valid_prefix(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        prev = GENESIS
        good: list[dict[str, Any]] = []
        for i, entry in enumerate(self.entries):
            if not _entry_ok(entry, prev):
                return good, self.entries[i:]
            prev = entry["hash"]
            good.append(entry)
        return good, []

    def _rewrite(self, rows: list[dict[str, Any]]) -> None:
        assert self.path is not None
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("".join(_line(r) + "\n" for r in rows) if rows else "")
        tmp.replace(self.path)

    def _repair_if_needed(self) -> bool:
        good, bad = self._valid_prefix()
        if not bad:
            self.entries = good
            self._prev = good[-1]["hash"] if good else GENESIS
            return False
        if self.path:
            broken = self.path.with_name(self.path.name + ".broken")
            existing = broken.read_text() if broken.exists() else ""
            with broken.open("a") as handle:
                if existing and not existing.endswith("\n"):
                    handle.write("\n")
                for row in bad:
                    handle.write(_line(row) + "\n")
            self._rewrite(good)
        self.entries = good
        self._prev = good[-1]["hash"] if good else GENESIS
        return True

    def _make_entry(
        self,
        event: str,
        traces: dict[str, Any],
        action: str,
        outcome: str,
        extra: dict[str, Any] | None,
    ) -> dict[str, Any]:
        body = {
            "event": event,
            "traces": traces,
            "action": action,
            "outcome": outcome,
            "extra": extra or {},
            "prev": self._prev,
            "ts": datetime.now(timezone.utc).isoformat(),
            "index": len(self.entries),
        }
        body["hash"] = _hash_body(body)
        return body

    def _with_lock(self):
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        handle = lock_path.open("a+")
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    def append(
        self,
        event: str,
        traces: dict[str, Any],
        action: str,
        outcome: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.path:
            entry = self._make_entry(event, traces, action, outcome, extra)
            self.entries.append(entry)
            self._prev = entry["hash"]
            return entry
        lock = self._with_lock()
        try:
            if self.path.exists():
                self._load(self.path)
                self._repair_if_needed()
            else:
                self.entries = []
                self._prev = GENESIS
            entry = self._make_entry(event, traces, action, outcome, extra)
            self.entries.append(entry)
            self._prev = entry["hash"]
            self._rewrite(self.entries)
            return entry
        finally:
            lock.close()

    def verify(self) -> bool:
        good, bad = self._valid_prefix()
        return not bad and good == self.entries

    def tail(self, n: int = 8) -> list[dict[str, Any]]:
        return [
            {
                "index": e["index"],
                "ts": e["ts"],
                "event": e["event"],
                "action": e["action"],
                "outcome": e["outcome"],
                "hash": e["hash"][:12],
            }
            for e in self.entries[-n:]
        ]
