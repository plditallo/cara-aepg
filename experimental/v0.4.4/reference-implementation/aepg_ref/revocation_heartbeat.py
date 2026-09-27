"""Signed revocation heartbeats for effect-time complete mediation.

v0.4.3 replaces the v0.4.2 global epoch with per-dependency revocation state:

* The RevocationService runs on its own clock (optionally skewed), holds the
  only signing key, and publishes heartbeats listing every authority
  dependency (grant, root, subject, issuer, key) revoked or suspended as of
  the heartbeat time. Future-dated revocations are not listed until they take
  effect.
* A receipt carries the dependency set of its grant lineage.
* At release, and at every control tick during motion, the actuator requires
  a verified heartbeat no older than delta whose revoked set does not
  intersect the receipt's dependencies.

An unrelated revocation therefore never stops this arm, and the actuator,
which holds only a public key, cannot forge freshness.

The revoked set is sent in full. That is fine for a simulation; a fleet
needs a compact encoding (per-dependency epochs, or a signed Merkle/bloom
commitment) and a spec rule for it.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from .signing import Signer
from .timeutil import parse_ts

REVOKING_OPS = {"REVOKE", "SUSPEND"}


def dep_key(dep_type, dep_id):
    return f"{dep_type}:{dep_id}"


class RevocationService:
    def __init__(self, seed: bytes, key_id="revocation-hb-k1", clock_offset_s=0.0):
        self._signer = Signer(seed, key_id)
        self.clock_offset = timedelta(seconds=clock_offset_s)
        self._records = []  # (effective_at, op, dep_key)
        self._seq = 0

    def verifier(self):
        return self._signer.verifier()

    def record(self, target_type, target_id, operation, effective_at):
        self._records.append((parse_ts(effective_at), operation, dep_key(target_type, target_id)))

    def revoked_as_of(self, t):
        revoked, suspended = set(), set()
        for at, op, k in sorted(self._records, key=lambda r: r[0]):
            if at > t:
                continue
            if op == "REVOKE":
                revoked.add(k); suspended.discard(k)
            elif op == "SUSPEND" and k not in revoked:
                suspended.add(k)
            elif op == "RESUME":
                suspended.discard(k)
        return revoked | suspended

    def heartbeat(self, true_time):
        """true_time is simulation ground truth; issued_at is this service's clock."""
        t = parse_ts(true_time)
        self._seq += 1
        return self._signer.sign({
            "seq": self._seq,
            "issued_at": (t + self.clock_offset).isoformat(),
            "revoked": sorted(self.revoked_as_of(t)),
        })


@dataclass
class HeartbeatState:
    """What an enforcement point keeps: the newest verified heartbeat."""
    verifier: object
    latest: dict | None = None
    rejected: int = 0

    def receive(self, hb):
        if not self.verifier.verify(hb):
            self.rejected += 1
            return False
        if self.latest is None or hb["seq"] > self.latest["seq"]:
            self.latest = hb
        return True


def check_release(state: HeartbeatState, now, max_age_s, dependencies, max_future_skew_s=0.05):
    """Return None if release may proceed, else a reason code."""
    hb = state.latest
    if hb is None:
        return "REVOCATION_HEARTBEAT_MISSING"
    age = (parse_ts(now) - parse_ts(hb["issued_at"])).total_seconds()
    if age < -max_future_skew_s:
        return "REVOCATION_HEARTBEAT_FROM_FUTURE"
    if age > max_age_s:
        return "REVOCATION_HEARTBEAT_STALE"
    if not dependencies:
        return "AUTHORITY_DEPENDENCIES_UNBOUND"
    if set(dependencies) & set(hb["revoked"]):
        return "AUTHORITY_DEPENDENCY_REVOKED"
    return None
