"""Audit chain stays intact across two writers and a forked file."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framework.audit import AuditChain  # noqa: E402


def _add(chain: AuditChain, name: str) -> dict:
    return chain.append(name, {"n": 1}, "ALLOW", "shadow")


class AuditIntegrity(unittest.TestCase):
    def test_two_clients_do_not_fork_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            first = AuditChain(path)
            second = AuditChain(path)
            _add(first, "deploy:a")
            _add(second, "deploy:b")
            _add(first, "deploy:c")
            loaded = AuditChain(path)
            self.assertTrue(loaded.verify())
            self.assertEqual(len(loaded.entries), 3)
            self.assertTrue(first.verify())
            self.assertTrue(second.verify())

    def test_forked_file_is_repaired_and_new_row_is_intact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "audit.jsonl"
            good = AuditChain(path)
            a = _add(good, "deploy:a")
            _add(good, "deploy:b")
            # Simulate the old bug: a second genesis row appended by a stale writer.
            fork = {
                "event": "deploy:fork",
                "traces": {},
                "action": "ALLOW",
                "outcome": "shadow",
                "extra": {},
                "prev": "0" * 64,
                "ts": "2020-01-01T00:00:00+00:00",
                "index": 0,
                "hash": "deadbeef",
            }
            with path.open("a") as handle:
                handle.write(json.dumps(fork) + "\n")
            repaired = AuditChain(path)
            self.assertTrue(repaired.repaired)
            self.assertTrue(repaired.verify())
            self.assertEqual(len(repaired.entries), 2)
            self.assertEqual(repaired.entries[0]["hash"], a["hash"])
            self.assertTrue((path.with_name("audit.jsonl.broken")).exists())
            _add(repaired, "deploy:c")
            self.assertTrue(repaired.verify())
            self.assertTrue(AuditChain(path).verify())

    def test_fresh_chain_verifies(self) -> None:
        chain = AuditChain()
        _add(chain, "deploy:x")
        _add(chain, "deploy:y")
        self.assertTrue(chain.verify())


if __name__ == "__main__":
    unittest.main()
