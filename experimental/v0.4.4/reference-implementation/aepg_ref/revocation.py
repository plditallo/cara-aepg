"""Revocation state and lineage dependencies (AEPG v0.2 sections 10-11)."""
from datetime import datetime, timezone
from .timeutil import parse_ts

# "subject" is included so that revoking an agent invalidates grants held by
# that agent AND grants it delegated onward (via lineage below).
INVALIDATING_TYPES = frozenset({
    "grant", "root", "subject", "issuer", "key", "policy",
    "attestation_authority", "trust_relationship",
})

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class LineageError(Exception):
    def __init__(self, code, message, grant_id=None):
        super().__init__(message)
        self.code = code
        self.grant_id = grant_id


def grant_dependencies(grant):
    """Dependencies of ONE grant record. Use lineage_dependencies for a path."""
    deps = {
        ("grant", grant["grant_id"]),
        ("root", grant["root_id"]),
        ("issuer", grant["issuer"]),
        ("subject", grant["subject"]),
        ("key", (grant.get("signature") or {}).get("key_id", "")),
    }
    return {d for d in deps if d[1]}


def lineage(grant, grants_by_id, max_depth):
    """Return [grant, parent, grandparent, ...] up to the root grant.

    Fails closed on a missing ancestor, a cycle, or a chain longer than
    max_depth (AEPG-GRAPH-001 bounded evaluation).
    """
    chain = [grant]
    seen = {grant["grant_id"]}
    current = grant
    while current.get("parent_grant_id"):
        if len(chain) > max_depth:
            raise LineageError("AUTHORIZATION_EVALUATION_BOUND_EXCEEDED",
                               f"lineage exceeds max depth {max_depth}", grant["grant_id"])
        pid = current["parent_grant_id"]
        if pid in seen:
            raise LineageError("LINEAGE_CYCLE", f"grant lineage cycles at {pid}", grant["grant_id"])
        parent = grants_by_id.get(pid)
        if parent is None:
            raise LineageError("LINEAGE_UNRESOLVED", f"ancestor {pid} not supplied", grant["grant_id"])
        chain.append(parent)
        seen.add(pid)
        current = parent
    return chain


def lineage_dependencies(chain):
    out = set()
    for g in chain:
        out |= grant_dependencies(g)
    return out


def revocation_state(revocations, now):
    """Fold revocation records effective at `now` into (revoked, suspended).

    REVOKE is permanent. SUSPEND is temporary and can be lifted by RESUME.
    RESUME never lifts a REVOKE (AEPG-ROOT-002). Records dated in the future
    are not yet effective. Records with no effective_at are treated as
    already effective.
    """
    effective = []
    for r in revocations:
        at = parse_ts(r["effective_at"]) if r.get("effective_at") else _EPOCH
        if at <= now:
            effective.append((at, r))
    # Stable sort; at equal times REVOKE is applied last so it wins.
    rank = {"RESUME": 0, "SUSPEND": 1, "REVOKE": 2}
    effective.sort(key=lambda x: (x[0], rank.get(x[1].get("operation"), 3)))

    revoked, suspended = set(), set()
    for _, r in effective:
        if r.get("target_type") not in INVALIDATING_TYPES:
            continue
        key = (r["target_type"], r["target_id"])
        op = r.get("operation")
        if op == "REVOKE":
            revoked.add(key)
            suspended.discard(key)
        elif op == "SUSPEND" and key not in revoked:
            suspended.add(key)
        elif op == "RESUME":
            suspended.discard(key)
    return revoked, suspended
