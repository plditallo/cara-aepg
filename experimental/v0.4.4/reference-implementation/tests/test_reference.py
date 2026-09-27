"""The original v0.1 tests, ported to the v0.2 authorize() signature."""
from copy import deepcopy
from conftest import delegate, make_revocation, codes, AGENT_B


def test_allow(case):
    assert case.run().decision == "ALLOW"


def test_revoked_grant_denied(case):
    case.revocations = [make_revocation("grant", "cara:grant:t:g1")]
    res = case.run()
    assert res.decision == "DENY"
    assert "AUTHORITY_BASIS_INSUFFICIENT" in codes(res)
    assert "AUTHORITY_REVOKED" in codes(res)


def test_state_change_denied(case):
    assert case.run(current_state={"x": 2}).decision == "DENY"


def test_provenance_root_cannot_be_authority(case):
    case.basis["authority_root_ids"] = ["cara:root:t:info"]
    res = case.run()
    assert res.decision == "DENY"
    assert "PROVENANCE_ROOT_PROMOTED_TO_AUTHORITY" in codes(res)


def test_broader_delegation_denied(engine, case):
    parent = case.grants[0]
    child = delegate(parent, "cara:grant:t:g2", AGENT_B, resources=["db", "payments"])
    assert "CONSTRAINT_NOT_PROVEN_ATTENUATED" in {f.code for f in engine.validate_delegation(child, parent)}


def test_constraint_numeric_max(engine, case):
    parent = case.grants[0]
    parent["constraints"] = [{"type": "daily_budget", "value": 1000, "comparator_id": "numeric-max/v1", "comparator_version": "1"}]
    child = delegate(parent, "cara:grant:t:g2", AGENT_B)
    child["constraints"] = [{"type": "daily_budget", "value": 500, "comparator_id": "numeric-max/v1", "comparator_version": "1"}]
    assert engine.validate_delegation(child, parent) == []


def test_all_basis_insufficient(case):
    case.use(["cara:grant:t:g1", "cara:grant:t:missing"], mode="ALL")
    assert case.run().decision == "DENY"


def test_evaluation_budget_fail_closed(case):
    case.policy["evaluation_budget_exceeded"] = True
    res = case.run()
    assert res.decision == "DENY"
    assert "AUTHORIZATION_EVALUATION_BOUND_EXCEEDED" in codes(res)
