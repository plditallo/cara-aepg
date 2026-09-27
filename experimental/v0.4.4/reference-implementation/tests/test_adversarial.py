"""Negative and adversarial tests for AEPG Reference Implementation v0.2.

Each class targets one way an attacker (or a buggy caller) could obtain an
ALLOW the specification forbids. Every class also carries a positive
control, so a suite that denies everything cannot pass.

Tests marked "v0.1 regression" returned ALLOW under Reference
Implementation v0.1.
"""
from copy import deepcopy
import pytest
from aepg_ref.canonical import sha256_uri
from conftest import (make_grant, delegate, make_revocation, codes,
                      AGENT_A, AGENT_B, PRINCIPAL)

AGENT_C = "cara:agent:t:c"


def budget(value, comparator="numeric-max/v1", version="1"):
    return {"type": "daily_budget", "value": value, "comparator_id": comparator, "comparator_version": version}


def chain_case(case, depth=1, **leaf_over):
    """Root grant held by A, delegated A->B (->C ...). Request is made by the leaf."""
    root = case.grants[0]
    agents = [AGENT_A, AGENT_B, AGENT_C] + [f"cara:agent:t:x{i}" for i in range(20)]
    grants = [root]
    for i in range(1, depth + 1):
        over = leaf_over if i == depth else {}
        grants.append(delegate(grants[-1], f"cara:grant:t:d{i}", agents[i], **over))
    case.grants = grants
    case.use([grants[-1]["grant_id"]], subject=grants[-1]["subject"])
    return grants


# --------------------------------------------------------------------------
# Identity: a grant only authorizes the agent it was issued to.
# --------------------------------------------------------------------------
class TestSubjectBinding:
    def test_control(self, case):
        assert case.run().allowed

    def test_grant_issued_to_another_agent(self, case):  # v0.1 regression
        case.grants[0]["subject"] = AGENT_B
        res = case.run()
        assert res.decision == "DENY"
        assert "GRANT_SUBJECT_MISMATCH" in codes(res)

    def test_request_subject_differs_from_activity_actor(self, case):  # v0.1 regression
        case.request["subject"] = AGENT_B
        res = case.run()
        assert res.decision == "DENY"
        assert "SUBJECT_ACTOR_MISMATCH" in codes(res)

    def test_basis_names_grant_not_presented_in_request(self, case):
        case.request["candidate_grant_ids"] = ["cara:grant:t:other"]
        assert "BASIS_GRANT_NOT_REQUESTED" in codes(case.run())


# --------------------------------------------------------------------------
# Time: validity is checked at authorization, against the PDP's clock.
# --------------------------------------------------------------------------
class TestValidityWindow:
    def test_expired_grant(self, case):  # v0.1 regression
        case.grants[0]["validity"] = {"not_before": "2020-01-01T00:00:00Z", "expires_at": "2020-02-01T00:00:00Z"}
        res = case.run()
        assert res.decision == "DENY"
        assert "GRANT_EXPIRED" in codes(res)

    def test_not_yet_valid_grant(self, case):
        case.grants[0]["validity"] = {"not_before": "2026-12-01T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z"}
        assert "GRANT_NOT_YET_VALID" in codes(case.run())

    def test_expiry_is_exclusive(self, case):
        case.grants[0]["validity"]["expires_at"] = case.now
        assert case.run().decision == "DENY"

    def test_offset_timestamps_compare_as_instants(self, case):
        # 19:30+02:00 is 17:30Z, which is before NOW (18:00Z). v0.1 compared strings.
        case.grants[0]["validity"]["expires_at"] = "2026-09-27T19:30:00+02:00"
        assert "GRANT_EXPIRED" in codes(case.run())

    def test_expired_ancestor_invalidates_leaf(self, case):
        grants = chain_case(case)
        grants[0]["validity"]["expires_at"] = "2026-06-01T00:00:00Z"
        assert case.run().decision == "DENY"

    def test_unparseable_now_is_indeterminate(self, case):
        case.now = "yesterday-ish"
        assert "TIME_INDETERMINATE" in codes(case.run())


# --------------------------------------------------------------------------
# Audience: a grant is only usable at the PEPs it names.
# --------------------------------------------------------------------------
class TestAudience:
    def test_grant_for_a_different_pep(self, case):  # v0.1 regression
        case.grants[0]["audience"] = ["pep-payments"]
        res = case.run()
        assert res.decision == "DENY"
        assert "PEP_AUDIENCE_MISMATCH" in codes(res)

    def test_missing_pep_id(self, case):
        case.pep = ""
        assert "PEP_AUDIENCE_BINDING_MISSING" in codes(case.run())


# --------------------------------------------------------------------------
# Action binding: the thing checked against grants is the thing hashed.
# --------------------------------------------------------------------------
class TestActionBinding:
    def test_arbitrary_matching_hashes_rejected(self, case):  # v0.1 regression
        case.request["canonical_action_hash"] = "sha256:deadbeef"
        case.activity["canonical_action_hash"] = "sha256:deadbeef"
        res = case.run()
        assert res.decision == "DENY"
        assert "CANONICAL_ACTION_BINDING_MISSING" in codes(res)

    def test_action_swapped_after_hashing(self, case):
        case.action = {"operation": "db.write", "action": "write", "resource": "payments"}
        assert case.run().decision == "DENY"

    def test_hashed_action_outside_grant_scope(self, case):
        case.action = {"operation": "db.drop", "action": "drop", "resource": "db"}
        h = sha256_uri(case.action)
        case.request["canonical_action_hash"] = h
        case.activity["canonical_action_hash"] = h
        res = case.run()
        assert res.decision == "DENY"
        assert "GRANT_SCOPE_INSUFFICIENT" in codes(res)

    def test_policy_can_no_longer_name_the_action(self, case):
        # v0.1 took action/resource from the caller's policy dict.
        case.policy.update(action_name="write", resource_name="db")
        case.action = {"operation": "db.drop", "action": "drop", "resource": "db"}
        h = sha256_uri(case.action)
        case.request["canonical_action_hash"] = h
        case.activity["canonical_action_hash"] = h
        assert case.run().decision == "DENY"

    def test_malformed_action(self, case):
        case.action = {"action": "write"}
        assert "CANONICAL_ACTION_BINDING_MISSING" in codes(case.run())


# --------------------------------------------------------------------------
# Descendant invalidation: revoking anything on a lineage kills the leaf.
# --------------------------------------------------------------------------
class TestDescendantRevocation:
    def test_control_delegated_chain_allows(self, case):
        chain_case(case, depth=2)
        assert case.run().allowed

    def test_parent_grant_revoked(self, case):  # v0.1 regression
        grants = chain_case(case)
        case.revocations = [make_revocation("grant", grants[0]["grant_id"])]
        res = case.run()
        assert res.decision == "DENY"
        assert "AUTHORITY_REVOKED" in codes(res)

    def test_grandparent_revoked(self, case):
        grants = chain_case(case, depth=2)
        case.revocations = [make_revocation("grant", grants[0]["grant_id"])]
        assert case.run().decision == "DENY"

    def test_root_revoked(self, case):
        chain_case(case, depth=2)
        case.revocations = [make_revocation("root", "cara:root:t:r1")]
        assert case.run().decision == "DENY"

    def test_requesting_agent_revoked(self, case):  # v0.1 regression
        case.revocations = [make_revocation("subject", AGENT_A)]
        assert case.run().decision == "DENY"

    def test_intermediate_delegator_revoked(self, case):
        # A -> B -> C. Revoking agent B must cut off C.
        chain_case(case, depth=2)
        case.revocations = [make_revocation("subject", AGENT_B)]
        assert case.run().decision == "DENY"

    def test_signing_key_revoked(self, case):
        # The OpenAI / Hugging Face timeline includes a stolen signing key.
        # Revoking the key must invalidate everything it signed.
        case.revocations = [make_revocation("key", "key-issuer-1")]
        assert case.run().decision == "DENY"

    def test_unrelated_revocation_does_not_deny(self, case):
        case.revocations = [make_revocation("grant", "cara:grant:t:unrelated")]
        assert case.run().allowed

    def test_missing_ancestor_fails_closed(self, case):
        grants = chain_case(case)
        case.grants = [grants[1]]  # parent withheld, so its revocation state is unknowable
        res = case.run()
        assert res.decision == "DENY"
        assert "LINEAGE_UNRESOLVED" in codes(res)

    def test_lineage_cycle_fails_closed(self, case):
        grants = chain_case(case)
        grants[0]["parent_grant_id"] = grants[1]["grant_id"]
        res = case.run()
        assert res.decision == "DENY"
        assert "LINEAGE_CYCLE" in codes(res)

    def test_lineage_depth_is_bounded(self, engine, case):
        case.grants[0]["delegation"]["remaining_depth"] = 30
        chain_case(case, depth=20)
        res = case.run()
        assert res.decision == "DENY"
        assert "AUTHORIZATION_EVALUATION_BOUND_EXCEEDED" in codes(res)


class TestSuspendResume:
    def test_suspend_denies(self, case):
        case.revocations = [make_revocation("grant", "cara:grant:t:g1", "SUSPEND")]
        res = case.run()
        assert res.decision == "DENY"
        assert "AUTHORITY_SUSPENDED" in codes(res)
        assert "AUTHORITY_REVOKED" not in codes(res)

    def test_resume_restores(self, case):
        case.revocations = [
            make_revocation("grant", "cara:grant:t:g1", "SUSPEND", "2026-09-01T00:00:00Z"),
            make_revocation("grant", "cara:grant:t:g1", "RESUME", "2026-09-02T00:00:00Z"),
        ]
        assert case.run().allowed

    def test_resume_cannot_undo_revoke(self, case):
        case.revocations = [
            make_revocation("grant", "cara:grant:t:g1", "REVOKE", "2026-09-01T00:00:00Z"),
            make_revocation("grant", "cara:grant:t:g1", "RESUME", "2026-09-02T00:00:00Z"),
        ]
        assert case.run().decision == "DENY"

    def test_future_dated_revocation_not_yet_effective(self, case):
        case.revocations = [make_revocation("grant", "cara:grant:t:g1", effective_at="2026-10-01T00:00:00Z")]
        assert case.run().allowed

    def test_revoke_and_resume_at_same_instant_revoke_wins(self, case):
        t = "2026-09-01T00:00:00Z"
        case.revocations = [make_revocation("grant", "cara:grant:t:g1", "RESUME", t),
                            make_revocation("grant", "cara:grant:t:g1", "REVOKE", t)]
        assert case.run().decision == "DENY"

    def test_malformed_revocation_record_fails_closed(self, case):
        # v0.1 silently ignored records it did not understand.
        case.revocations = [{"operation": "REVOKE", "target_type": "grant", "target_id": "cara:grant:t:g1"}]
        assert "SCHEMA_INVALID" in codes(case.run())


# --------------------------------------------------------------------------
# Attenuation: a child can never hold more than its parent.
# --------------------------------------------------------------------------
class TestAttenuation:
    @pytest.fixture
    def parent(self, case):
        p = case.grants[0]
        p["constraints"] = [budget(1000)]
        return p

    def child(self, parent, **over):
        return delegate(parent, "cara:grant:t:g2", AGENT_B, **over)

    def rejected(self, engine, child, parent):
        return {f.code for f in engine.validate_delegation(child, parent)} == {"CONSTRAINT_NOT_PROVEN_ATTENUATED"}

    def test_control(self, engine, parent):
        assert engine.validate_delegation(self.child(parent), parent) == []

    def test_child_drops_parent_constraint(self, engine, parent):  # v0.1 regression
        assert self.rejected(engine, self.child(parent, constraints=[]), parent)

    def test_child_swaps_comparator_to_invert_meaning(self, engine, parent):  # v0.1 regression
        c = self.child(parent, constraints=[budget(50000, comparator="numeric-min/v1")])
        assert self.rejected(engine, c, parent)

    def test_child_changes_comparator_version(self, engine, parent):
        assert self.rejected(engine, self.child(parent, constraints=[budget(500, version="2")]), parent)

    def test_child_raises_budget(self, engine, parent):
        assert self.rejected(engine, self.child(parent, constraints=[budget(1001)]), parent)

    def test_duplicate_constraint_type(self, engine, parent):
        assert self.rejected(engine, self.child(parent, constraints=[budget(10), budget(5000)]), parent)

    def test_boolean_is_not_a_budget(self, engine, parent):
        assert self.rejected(engine, self.child(parent, constraints=[budget(True)]), parent)

    def test_side_effect_escalation(self, engine, parent):  # v0.1 regression
        assert self.rejected(engine, self.child(parent, side_effect_class="irreversible"), parent)

    def test_side_effect_narrowing_allowed(self, engine, parent):
        assert engine.validate_delegation(self.child(parent, side_effect_class="read_only"), parent) == []

    def test_unknown_side_effect_class(self, engine, parent):
        assert self.rejected(engine, self.child(parent, side_effect_class="mostly_harmless"), parent)

    def test_issuer_is_not_parent_holder(self, engine, parent):
        # A grant that claims a parent but was not issued by that parent's holder.
        assert self.rejected(engine, self.child(parent, issuer=AGENT_C), parent)

    def test_root_changed(self, engine, parent):
        assert self.rejected(engine, self.child(parent, root_id="cara:root:t:r2"), parent)

    def test_parent_has_no_remaining_depth(self, engine, parent):
        parent["delegation"]["remaining_depth"] = 0
        c = self.child(parent)
        c["delegation"]["remaining_depth"] = 0
        assert self.rejected(engine, c, parent)

    def test_parent_disallows_delegation(self, engine, parent):
        parent["delegation"]["allowed"] = False
        c = self.child(parent)
        c["delegation"]["allowed"] = False
        assert self.rejected(engine, c, parent)

    def test_child_drops_max_children(self, engine, parent):
        c = self.child(parent)
        del c["delegation"]["max_children"]
        assert self.rejected(engine, c, parent)

    def test_child_outlives_parent(self, engine, parent):
        c = self.child(parent)
        c["validity"] = dict(parent["validity"], expires_at="2028-01-01T00:00:00Z")
        assert self.rejected(engine, c, parent)

    def test_string_is_not_a_set(self, engine, parent):
        # set("db") == {"d", "b"}; v0.1 would have compared characters.
        assert self.rejected(engine, self.child(parent, resources="db"), parent)

    def test_unattenuated_link_is_caught_at_authorization(self, case):
        # Attenuation is re-proven on every link at authorization time,
        # not trusted from issuance.
        chain_case(case, side_effect_class="irreversible")
        res = case.run()
        assert res.decision == "DENY"
        assert "CONSTRAINT_NOT_PROVEN_ATTENUATED" in codes(res)


# --------------------------------------------------------------------------
# AuthorityBasis modes.
# --------------------------------------------------------------------------
class TestBasisModes:
    @pytest.fixture
    def three(self, case):
        gs = [make_grant(f"cara:grant:t:m{i}") for i in range(3)]
        case.grants = gs
        return [g["grant_id"] for g in gs]

    def test_any_with_one_usable(self, case, three):
        case.use(three, mode="ANY")
        case.revocations = [make_revocation("grant", three[0]), make_revocation("grant", three[1])]
        assert case.run().allowed

    def test_any_with_none_usable(self, case, three):
        case.use(three, mode="ANY")
        case.revocations = [make_revocation("grant", g) for g in three]
        assert case.run().decision == "DENY"

    def test_any_is_not_poisoned_by_an_irrelevant_grant(self, case, three):
        # v0.1 denied ANY if any active grant lacked scope, even when another covered it.
        case.grants[1]["actions"] = ["read"]
        case.use(three, mode="ANY")
        assert case.run().allowed

    def test_threshold_met(self, case, three):
        case.use(three, mode="THRESHOLD", threshold=2)
        case.revocations = [make_revocation("grant", three[0])]
        assert case.run().allowed

    def test_threshold_not_met(self, case, three):
        case.use(three, mode="THRESHOLD", threshold=3)
        case.revocations = [make_revocation("grant", three[0])]
        assert case.run().decision == "DENY"

    def test_threshold_null(self, case, three):
        case.use(three, mode="THRESHOLD", threshold=None)
        assert case.run().decision == "DENY"

    def test_threshold_larger_than_grant_count(self, case, three):
        case.use(three, mode="THRESHOLD", threshold=4)
        assert case.run().decision == "DENY"

    def test_all_requires_every_grant(self, case, three):
        case.use(three, mode="ALL")
        assert case.run().allowed
        case.revocations = [make_revocation("grant", three[2])]
        assert case.run().decision == "DENY"

    def test_single_with_two_grants(self, case, three):
        case.use(three[:2], mode="SINGLE")
        assert case.run().decision == "DENY"

    def test_root_must_come_from_a_usable_grant(self, case, three):
        case.grants[0]["root_id"] = "cara:root:t:r2"
        case.use(three, mode="ANY")
        case.basis["authority_root_ids"] = ["cara:root:t:r2"]
        case.revocations = [make_revocation("grant", three[0])]
        res = case.run()
        assert res.decision == "DENY"
        assert "AUTHORITY_BASIS_INSUFFICIENT" in codes(res)
        assert "PROVENANCE_ROOT_PROMOTED_TO_AUTHORITY" not in codes(res)


# --------------------------------------------------------------------------
# Structure: every input that affects the decision is schema-validated.
# --------------------------------------------------------------------------
class TestStructure:
    def test_grant_without_signature(self, case):  # v0.1 regression
        del case.grants[0]["signature"]
        assert "SCHEMA_INVALID" in codes(case.run())

    def test_grant_with_empty_issuer(self, case):
        case.grants[0]["issuer"] = ""
        assert "SCHEMA_INVALID" in codes(case.run())

    def test_conflicting_records_with_same_grant_id(self, case):
        twin = deepcopy(case.grants[0])
        twin["actions"] = ["write", "drop"]
        case.grants.append(twin)
        assert "AUTHORITATIVE_OBJECT_MUTATED" in codes(case.run())

    def test_findings_explain_denial(self, case):
        case.grants[0]["subject"] = AGENT_B
        res = case.run()
        hard = [f for f in res.findings if f.hard]
        assert hard and all(f.rule_id and f.message for f in res.findings)
