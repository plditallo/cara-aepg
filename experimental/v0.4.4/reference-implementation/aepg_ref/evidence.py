"""Hash-chained, append-only evidence log (CARA section 10, reference only).

Each entry commits to its predecessor, so deleting, reordering, or editing
any entry breaks verification from that point on. This detects tampering by
anyone who does not also rewrite every later hash; anchoring the head hash
externally (a transparency log) is what stops a full rewrite.
"""
import hashlib
from copy import deepcopy

from .canonical import canonical_json

GENESIS = "sha256:" + "0" * 64


def _h(obj):
    return "sha256:" + hashlib.sha256(canonical_json(obj)).hexdigest()


class EvidenceLog:
    def __init__(self):
        self._entries = []

    @property
    def head(self):
        return self._entries[-1]["entry_hash"] if self._entries else GENESIS

    def append(self, event_type: str, payload: dict) -> dict:
        body = {"seq": len(self._entries), "type": event_type, "payload": deepcopy(payload), "prev_hash": self.head}
        entry = dict(body, entry_hash=_h(body))
        self._entries.append(entry)
        return entry

    def entries(self):
        return deepcopy(self._entries)

    def of_type(self, event_type):
        return [e for e in self.entries() if e["type"] == event_type]

    @staticmethod
    def verify(entries) -> tuple[bool, int | None]:
        prev = GENESIS
        for i, e in enumerate(entries):
            body = {k: e[k] for k in ("seq", "type", "payload", "prev_hash")}
            if e["seq"] != i or e["prev_hash"] != prev or e["entry_hash"] != _h(body):
                return False, i
            prev = e["entry_hash"]
        return True, None
