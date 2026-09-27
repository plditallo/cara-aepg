"""Tier 3 Policy Enforcement Point: authorize -> reserve -> receipt -> settle.

Ties the AEPG engine (authority), the consumption ledger (durable use), the
receipt signer (binding), and the evidence log into the Tier 3 flow of AEPG
Technical Specification v0.2 sections 13-16.
"""
from datetime import timedelta

from .canonical import sha256_uri
from .consumption import ConsumptionError
from .models import DecisionResult, ValidationFinding
from .revocation import lineage, lineage_dependencies, LineageError
from .revocation_heartbeat import dep_key
from .timeutil import parse_ts


class Tier3PEP:
    def __init__(self, engine, ledger, signer, evidence, pep_id, receipt_ttl_s=2.0):
        self.engine = engine
        self.ledger = ledger
        self.signer = signer
        self.evidence = evidence
        self.pep_id = pep_id
        self.ttl = timedelta(seconds=receipt_ttl_s)

    def authorize(self, *, request, activity, basis, grants, revocations, policy, current_state,
                  action, slot_id, now, release_limits=None):
        action_hash = sha256_uri(action)
        res = self.engine.authorize(request, activity, basis, grants, revocations, policy, current_state,
                                    action=action, pep_id=self.pep_id, now=now)
        if not res.allowed:
            self.evidence.append("AUTHORITY_DENIED", {
                "request_id": request["request_id"], "canonical_action_hash": action_hash,
                "codes": sorted({f.code for f in res.findings if f.hard}),
            })
            return res, None
        if basis["mode"] != "SINGLE":
            # Consumption is tracked per grant; multi-grant bases need a policy
            # for which grant's budget is spent. Not defined yet, so fail closed.
            f = ValidationFinding("AEPG-REF-CONS-002", "CONSUMPTION_BASIS_UNSUPPORTED",
                                  "Tier 3 consumption currently requires a SINGLE AuthorityBasis")
            self.evidence.append("CONSUMPTION_DENIED", {"request_id": request["request_id"], "reason": f.message})
            return DecisionResult("DENY", res.findings + (f,)), None
        try:
            reservation = self.ledger.prepare(
                slot_id, reservation_id=request["request_id"], subject_id=request["subject"],
                grant_id=basis["grant_ids"][0], resource_id=action["resource"], action=action["action"],
                canonical_action_hash=action_hash, effect_hash=action_hash,
            )
        except ConsumptionError as exc:
            f = ValidationFinding("AEPG-REF-CONS-001", "AUTHORITY_CONSUMPTION_DENIED", str(exc))
            self.evidence.append("CONSUMPTION_DENIED", {"request_id": request["request_id"], "reason": str(exc)})
            return DecisionResult("DENY", res.findings + (f,)), None

        # Bind the lineage's revocation dependencies into the receipt so the
        # actuator can check them against signed heartbeats at release time.
        byid = {g["grant_id"]: g for g in grants}
        chain = lineage(byid[basis["grant_ids"][0]], byid, self.engine.max_lineage_depth)
        dependencies = sorted(dep_key(t_, i_) for t_, i_ in lineage_dependencies(chain))

        t = parse_ts(now)
        receipt = self.signer.sign({
            "receipt_id": "rcpt:" + request["request_id"],
            "decision": "ALLOW",
            "pep_id": self.pep_id,
            "subject": request["subject"],
            "canonical_action_hash": action_hash,
            "request_hash": sha256_uri(request),
            "state_hash": request["state_hash"],
            "authority_basis_id": basis["authority_basis_id"],
            "revocation_snapshot_id": basis["revocation_snapshot_id"],
            "authority_dependencies": dependencies,
            "release_limits": release_limits or {},
            "reservation_id": reservation.reservation_id,
            "issued_at": t.isoformat(),
            "expires_at": (t + self.ttl).isoformat(),
        })
        self.evidence.append("PREACTION_RECEIPT", receipt)
        return res, receipt

    def settle(self, receipt, ack, reauthorize):
        """Record the actuator's outcome and settle the reservation.

        Returns one of: COMMITTED, ABORTED, EFFECT_AFTER_AUTHORITY_LOSS.
        The last means the physical effect happened but authority was gone
        by commit time. Revocation cannot undo it (CARA 8.4); it becomes a
        recovery obligation in the evidence log.
        """
        self.evidence.append("EXECUTION_ACK", ack)
        rid = receipt["reservation_id"]
        if not ack.get("executed"):
            self.ledger.abort(rid)
            self.evidence.append("RESERVATION_ABORTED", {"reservation_id": rid, "reason": ack.get("reason")})
            return "ABORTED"
        try:
            self.ledger.commit(rid, receipt["canonical_action_hash"], reauthorize)
        except Exception as exc:
            self.evidence.append("EFFECT_AFTER_AUTHORITY_LOSS", {
                "reservation_id": rid, "reason": str(exc), "outcome": ack.get("outcome"),
                "recovery_required": True,
            })
            return "EFFECT_AFTER_AUTHORITY_LOSS"
        self.evidence.append("RESERVATION_COMMITTED", {"reservation_id": rid})
        return "COMMITTED"
