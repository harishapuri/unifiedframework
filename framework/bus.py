"""Typed, priority-queued message bus shared by CRC, ZeroGuard, and InfraAgent.

In-memory by default (tests). File-backed when a path is set or
`FRAMEWORK_BUS_PATH` is present — survives a process restart mid-release.
Optional Redis Streams when `REDIS_URL` is set and the `redis` package is
installed; otherwise the file backend is used.
"""

from __future__ import annotations

import heapq
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Priority = Literal["safety", "identity", "capacity", "advisory"]

PRIORITY_RANK = {"safety": 0, "identity": 1, "capacity": 2, "advisory": 3}

MessageKind = Literal[
    "RiskReport",
    "ZtaScore",
    "IamProposal",
    "PatchSet",
    "Forecast",
    "GateDecision",
    "Outcome",
]


@dataclass(order=True)
class BusMessage:
    rank: int
    seq: int
    kind: MessageKind = field(compare=False)
    priority: Priority = field(compare=False)
    payload: dict[str, Any] = field(compare=False)
    source: str = field(compare=False, default="")
    service: str = field(compare=False, default="")
    status: str = field(compare=False, default="pending")


def _row(msg: BusMessage) -> dict[str, Any]:
    return {
        "seq": msg.seq,
        "rank": msg.rank,
        "kind": msg.kind,
        "priority": msg.priority,
        "payload": msg.payload,
        "source": msg.source,
        "service": msg.service,
        "status": msg.status,
    }


def _from_row(row: dict[str, Any]) -> BusMessage:
    return BusMessage(
        rank=int(row.get("rank", PRIORITY_RANK.get(row.get("priority", "advisory"), 3))),
        seq=int(row["seq"]),
        kind=row["kind"],
        priority=row["priority"],
        payload=row.get("payload") or {},
        source=row.get("source") or "",
        service=row.get("service") or "",
        status=row.get("status") or "pending",
    )


class _RedisStreams:
    """Thin optional backend. Missing package or bad URL → caller falls back."""

    def __init__(self, url: str, stream: str = "framework:bus") -> None:
        import redis  # type: ignore

        self.r = redis.from_url(url)
        self.stream = stream
        self.r.ping()

    def add(self, row: dict[str, Any]) -> None:
        self.r.xadd(self.stream, {"json": json.dumps(row, default=str)})

    def pending(self) -> list[dict[str, Any]]:
        rows = self.r.xrange(self.stream, min="-", max="+", count=500)
        out: list[dict[str, Any]] = []
        for _xid, fields in rows:
            blob = fields.get("json") or fields.get(b"json")
            if blob is None:
                continue
            if isinstance(blob, bytes):
                blob = blob.decode()
            row = json.loads(blob)
            row["_xid"] = _xid.decode() if isinstance(_xid, bytes) else str(_xid)
            out.append(row)
        return out

    def ack(self, rows: list[dict[str, Any]]) -> None:
        ids = [r["_xid"] for r in rows if r.get("_xid")]
        if ids:
            self.r.xdel(self.stream, *ids)


class MessageBus:
    def __init__(
        self,
        path: Path | str | None = None,
        redis_url: str | None = None,
    ) -> None:
        self.path = Path(path) if path else None
        self._heap: list[BusMessage] = []
        self._seq = 0
        self.log: list[BusMessage] = []
        self._redis: _RedisStreams | None = None
        self.backend = "memory"
        if redis_url:
            try:
                self._redis = _RedisStreams(redis_url)
                self.backend = "redis"
            except Exception:
                self._redis = None
        if self.path and self.backend != "redis":
            self.backend = "file"
            self._load_file()
        elif self._redis:
            self._load_redis()

    @classmethod
    def from_env(cls) -> MessageBus:
        redis_url = os.environ.get("REDIS_URL") or os.environ.get("FRAMEWORK_REDIS_URL")
        path = os.environ.get("FRAMEWORK_BUS_PATH")
        return cls(path=Path(path) if path else None, redis_url=redis_url or None)

    def _load_file(self) -> None:
        if not self.path or not self.path.exists():
            return
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            msg = _from_row(json.loads(line))
            self._seq = max(self._seq, msg.seq)
            self.log.append(msg)
            if msg.status == "pending":
                heapq.heappush(self._heap, msg)

    def _load_redis(self) -> None:
        assert self._redis is not None
        for row in self._redis.pending():
            msg = _from_row(row)
            self._seq = max(self._seq, msg.seq)
            self.log.append(msg)
            heapq.heappush(self._heap, msg)

    def _persist_all(self) -> None:
        if not self.path or self._redis:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as handle:
            for msg in self.log:
                handle.write(json.dumps(_row(msg), default=str) + "\n")

    def publish(
        self,
        kind: MessageKind,
        payload: dict[str, Any],
        *,
        priority: Priority = "advisory",
        source: str = "",
        service: str = "",
    ) -> BusMessage:
        self._seq += 1
        msg = BusMessage(
            rank=PRIORITY_RANK[priority],
            seq=self._seq,
            kind=kind,
            priority=priority,
            payload=payload,
            source=source,
            service=service,
            status="pending",
        )
        heapq.heappush(self._heap, msg)
        self.log.append(msg)
        if self._redis:
            self._redis.add(_row(msg))
        elif self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as handle:
                handle.write(json.dumps(_row(msg), default=str) + "\n")
        return msg

    def drain(self) -> list[BusMessage]:
        out: list[BusMessage] = []
        while self._heap:
            msg = heapq.heappop(self._heap)
            msg.status = "consumed"
            out.append(msg)
        if self._redis:
            # Reload ids then delete consumed stream entries.
            try:
                self._redis.ack(self._redis.pending())
            except Exception:
                pass
        elif self.path:
            self._persist_all()
        return out

    def pending_count(self) -> int:
        return len(self._heap)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": m.kind,
                "priority": m.priority,
                "source": m.source,
                "service": m.service,
                "payload": m.payload,
                "status": m.status,
            }
            for m in self.log[-12:]
        ]
