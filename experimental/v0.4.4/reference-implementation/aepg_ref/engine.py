from datetime import datetime, timezone
from .schema_store import SchemaStore
from .comparators import ComparatorRegistry, DEFAULT_SIDE_EFFECT_ORDER
from .attenuation import prove_attenuation
from .authority import GrantContext, evaluate_basis
from .revocation import revocation_state
from .models import ValidationFinding, DecisionResult
from .canonical import sha256_uri
from .timeutil import parse_ts
from .constraint_binding import evaluate_bound_constraints


def _hard(rule, code, message, **details):
    return ValidationFinding(rule, code, message, details=details)


class AEPGEngine:
    def __init__(self, schema_dir, comparators=None, side_effect_order=DEFAULT_SIDE_EFFECT_ORDER,
                 max_lineage_depth=16):
        self.schemas = SchemaStore(schema_dir)
        self.comparators = comparators or ComparatorRegistry.default()
        self.side_effect_order = tuple(side_effect_order)
        self.max_lineage_depth = max_lineage_depth

    def validate_schema(self, name, obj):
        return self.schemas.validate(name, obj)

    def validate_delegation(self, child, parent):
        return prove_attenuation(child, parent, self.comparators, self.side_effect_order)

    def authorize(self, request, activity, basis, grants, revocations, policy, current_state,
                  *, action, pep_id, now=None):
        """Evaluate one authorization request.

        action   The canonical action object. Its sha256_uri MUST equal the
                 canonical_action_hash on both the request and the Activity,
                 and its "action"/"resource" fields are what grants must
                 cover. The caller-supplied policy no longer names them.
        pep_id   The enforcement point this decision is for. Every grant used
                 must list it in its audience.
        now      Trusted evaluation time (the PDP's clock). Defaults to the
                 system clock. Never taken from the request.
        """
        findings = []

        # 1. Structure. Every object that influences the decision is validated.
        objects = [("authorization-request", request), ("activity", activity), ("authority-basis", basis)]
        objects += [("authority-grant", g) for g in grants]
        objects += [("revocation", r) for r in revocations]
        for name, obj in objects:
            for e in self.validate_schema(name, obj):
                findings.append(_hard("SCHEMA", "SCHEMA_INVALID", f"{name}: {e.message}"))
        if not isinstance(action, dict) or not isinstance(action.get("action"), str) \
                or not isinstance(action.get("resource"), str):
            findings.append(_hard("AEPG-DEC-005", "CANONICAL_ACTION_BINDING_MISSING",
                                  "canonical action must be an object with string 'action' and 'resource'"))
        if not isinstance(pep_id, str) or not pep_id:
            findings.append(_hard("AEPG-DEC-006", "PEP_AUDIENCE_BINDING_MISSING", "pep_id is required"))
        if findings:
            return DecisionResult("DENY", tuple(findings))

        # 2. Time and revocation state. Unparseable timestamps are INDETERMINATE -> deny.
        try:
            now = parse_ts(now) if now is not None else datetime.now(timezone.utc)
            revoked, suspended = revocation_state(revocations, now)
        except ValueError as exc:
            return DecisionResult("DENY", (_hard("AEPG-REF-TIME", "TIME_INDETERMINATE", str(exc)),))

        # 3. Request / Activity / basis binding.
        if request["activity_id"] != activity["activity_id"]:
            findings.append(_hard("AEPG-ACT-001", "MISSING_ACTIVITY", "request/activity mismatch"))
        if request["subject"] != activity["actor_id"]:
            findings.append(_hard("AEPG-REF-BIND-001", "SUBJECT_ACTOR_MISMATCH",
                                  "request subject is not the Activity's actor"))
        if activity["tier"] >= 2 and not activity.get("authority_basis_id"):
            findings.append(_hard("AEPG-AUTH-011", "AUTHORITY_BASIS_INSUFFICIENT", "Tier 2/3 Activity lacks AuthorityBasis"))
        if activity.get("authority_basis_id") != basis["authority_basis_id"]:
            findings.append(_hard("AEPG-AUTH-011", "AUTHORITY_BASIS_INSUFFICIENT", "Activity references different AuthorityBasis"))
        if not set(basis["grant_ids"]).issubset(request["candidate_grant_ids"]):
            findings.append(_hard("AEPG-REF-BIND-002", "BASIS_GRANT_NOT_REQUESTED",
                                  "AuthorityBasis names grants the request did not present"))

        action_hash = sha256_uri(action)
        if request["canonical_action_hash"] != action_hash or activity["canonical_action_hash"] != action_hash:
            findings.append(_hard("AEPG-DEC-005", "CANONICAL_ACTION_BINDING_MISSING",
                                  "request/Activity action hash does not match the canonical action",
                                  expected=action_hash))

        if request["state_hash"] != sha256_uri(current_state):
            findings.append(_hard("AEPG-DEC-008", "BOUND_STATE_CHANGED", "current state does not match request-bound state"))

        # 4. Grants and AuthorityBasis.
        byid = {}
        for g in grants:
            if g["grant_id"] in byid and byid[g["grant_id"]] != g:
                findings.append(_hard("AEPG-LIFE-001", "AUTHORITATIVE_OBJECT_MUTATED",
                                      "two different records share one grant_id", grant_id=g["grant_id"]))
            byid[g["grant_id"]] = g
        ctx = GrantContext(
            subject=request["subject"], pep_id=pep_id, now=now,
            action=action["action"], resource=action["resource"],
            grants_by_id=byid, revoked=revoked, suspended=suspended,
            registry=self.comparators, side_effect_order=self.side_effect_order,
            max_lineage_depth=self.max_lineage_depth,
        )
        ok, usable, gf = evaluate_basis(basis, ctx)
        findings.extend(gf)

        # 4b. Bound constraint parameters are checked against the canonical action.
        # Binding metadata is issuer-controlled and attenuation-protected.
        if ok:
            findings.extend(evaluate_bound_constraints(usable, action, self.comparators))

        # 5. Authority roots come only from grants, never from provenance.
        # A root no named grant carries is a promoted provenance root; a root
        # whose grants are all unusable is simply insufficient authority.
        basis_roots = set(basis["authority_root_ids"])
        named_roots = {byid[g]["root_id"] for g in basis["grant_ids"] if g in byid}
        usable_roots = {g["root_id"] for g in usable}
        if not basis_roots.issubset(named_roots):
            findings.append(_hard("AEPG-PROV-001", "PROVENANCE_ROOT_PROMOTED_TO_AUTHORITY",
                                  "AuthorityBasis contains a root no named grant carries",
                                  roots=sorted(basis_roots - named_roots)))
        elif ok and not basis_roots.issubset(usable_roots):
            findings.append(_hard("AEPG-AUTH-011", "AUTHORITY_BASIS_INSUFFICIENT",
                                  "AuthorityBasis root has no usable grant",
                                  roots=sorted(basis_roots - usable_roots)))

        # 6. Critical policy inputs.
        critical = set(policy.get("critical_policy_information_source_ids", []))
        supplied = set(request.get("policy_information_source_ids", []))
        if activity["tier"] == 3 and not critical.issubset(supplied):
            findings.append(_hard("AEPG-PIS-001", "CRITICAL_POLICY_INPUT_UNATTRIBUTED", "critical policy information source missing"))

        # 7. Bounded evaluation (caller-supplied budget signal in this core).
        if policy.get("evaluation_budget_exceeded"):
            findings.append(_hard("AEPG-GRAPH-001", "AUTHORIZATION_EVALUATION_BOUND_EXCEEDED", "authorization evaluation budget exceeded"))

        hard = [f for f in findings if f.hard]
        return DecisionResult("DENY" if hard else "ALLOW", tuple(findings), basis if not hard else None)
