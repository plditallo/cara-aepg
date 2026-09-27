"""v0.4.3: unbound constraints, asymmetric receipts, per-dependency heartbeats.
Tests marked "v0.4.2 regression" were exploitable in v0.4.2."""
from copy import deepcopy
import pytest
from aepg_ref.canonical import sha256_uri
from aepg_ref.consumption import ConfirmationAuthority, ConsumptionLedger
from aepg_ref.evidence import EvidenceLog
from aepg_ref.pep import Tier3PEP
from aepg_ref.receipts import ReceiptSigner
from aepg_ref.revocation_heartbeat import (HeartbeatState, RevocationService, check_release, dep_key)
from aepg_ref.signing import Signer
from conftest import PEP, AGENT_A, codes

T = "2026-09-27T18:00:00+00:00"
T_PLUS = lambda s: f"2026-09-27T18:00:{s:06.3f}+00:00"
DEPS = ["grant:g1", "root:r1", "subject:a", "issuer:p", "key:k1"]


def bound(value=10):
    return {"type": "max_writes", "value": value, "comparator_id": "numeric-max/v1", "comparator_version": "1",
            "binds_to": "params.count", "parameter_type": "integer"}


# ---- unbound constraints -------------------------------------------------
def test_unbound_constraint_denies(case):  # v0.4.2 regression
    case.grants[0]["constraints"] = [{"type": "max_writes", "value": 10, "comparator_id": "numeric-max/v1",
                                       "comparator_version": "1"}]
    res = case.run()
    assert res.decision == "DENY" and "UNBOUND_CONSTRAINT" in codes(res)


def test_bound_constraint_allows_within_and_denies_outside(case):
    case.grants[0]["constraints"] = [bound(10)]
    for count, expected in ((5, "ALLOW"), (11, "DENY")):
        case.action = {"operation": "db.write", "action": "write", "resource": "db", "params": {"count": count}}
        h = sha256_uri(case.action)
        case.request["canonical_action_hash"] = h
        case.activity["canonical_action_hash"] = h
        assert case.run().decision == expected


def test_bound_parameter_absent_denies(case):
    case.grants[0]["constraints"] = [bound(10)]
    assert "BOUND_PARAMETER_UNRESOLVED" in codes(case.run())


# ---- asymmetric receipts -------------------------------------------------
def test_receipt_verifier_cannot_sign():
    s = ReceiptSigner(b"pep-receipt-seed-0000000000000001", "k1")
    v = s.verifier()
    assert not hasattr(v, "sign") and v.verify(s.sign({"a": 1}))


def test_receipt_signed_with_other_key_rejected():
    s = ReceiptSigner(b"pep-receipt-seed-0000000000000001", "k1")
    forged = ReceiptSigner(b"attacker-guess-seed-000000000001", "k1").sign({"a": 1})
    assert not s.verifier().verify(forged)


def test_pep_binds_lineage_dependencies_into_receipt(engine, case):
    ca = ConfirmationAuthority(b"user-confirmation-key-0123456789")
    led = ConsumptionLedger(ca)
    led.open(ca.confirm(confirmation_id="c1", subject_id=AGENT_A, grant_id="cara:grant:t:g1", resource_id="db",
                        action="write", budget=1, canonical_action_hash=None))
    pep = Tier3PEP(engine, led, ReceiptSigner(b"pep-receipt-seed-0000000000000001", "k1"), EvidenceLog(), PEP)
    _, rc = pep.authorize(request=case.request, activity=case.activity, basis=case.basis, grants=case.grants,
                          revocations=[], policy=case.policy, current_state=case.state, action=case.action,
                          slot_id="c1", now=case.now)
    deps = set(rc["authority_dependencies"])
    assert {"grant:cara:grant:t:g1", "root:cara:root:t:r1", f"subject:{AGENT_A}", "key:key-issuer-1"} <= deps
    assert "revocation_epoch" not in rc


# ---- heartbeats ---------------------------------------------------------------
@pytest.fixture
def svc():
    return RevocationService(b"revocation-service-seed-00000001")


def state_with(svc, *hbs):
    st = HeartbeatState(svc.verifier())
    for hb in hbs:
        st.receive(hb)
    return st


def test_fresh_heartbeat_releases(svc):
    st = state_with(svc, svc.heartbeat(T))
    assert check_release(st, T_PLUS(0.2), 0.5, DEPS) is None


def test_stale_heartbeat_blocks(svc):
    st = state_with(svc, svc.heartbeat(T))
    assert check_release(st, T_PLUS(0.6), 0.5, DEPS) == "REVOCATION_HEARTBEAT_STALE"


def test_missing_heartbeat_blocks(svc):
    assert check_release(HeartbeatState(svc.verifier()), T, 0.5, DEPS) == "REVOCATION_HEARTBEAT_MISSING"


def test_revoked_dependency_blocks(svc):
    svc.record("grant", "g1", "REVOKE", T)
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, DEPS) == "AUTHORITY_DEPENDENCY_REVOKED"


def test_signing_key_revocation_blocks(svc):
    svc.record("key", "k1", "REVOKE", T)
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, DEPS) == "AUTHORITY_DEPENDENCY_REVOKED"


def test_unrelated_revocation_does_not_block(svc):  # v0.4.2 regression (global epoch)
    svc.record("grant", "some-other-robot", "REVOKE", T)
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, DEPS) is None


def test_future_dated_revocation_not_listed_until_effective(svc):  # v0.4.2 regression
    svc.record("grant", "g1", "REVOKE", T_PLUS(5))
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, DEPS) is None
    assert check_release(state_with(svc, svc.heartbeat(T_PLUS(5))), T_PLUS(5), 0.5, DEPS) \
        == "AUTHORITY_DEPENDENCY_REVOKED"


def test_suspend_then_resume(svc):
    svc.record("subject", "a", "SUSPEND", T)
    svc.record("subject", "a", "RESUME", T_PLUS(1))
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, DEPS) == "AUTHORITY_DEPENDENCY_REVOKED"
    assert check_release(state_with(svc, svc.heartbeat(T_PLUS(1))), T_PLUS(1), 0.5, DEPS) is None


def test_forged_heartbeat_rejected(svc):  # v0.4.2 regression
    forged = Signer(b"whoever-holds-a-verifier-0000001", "revocation-hb-k1").sign(
        {"seq": 99, "issued_at": T, "revoked": []})
    st = state_with(svc)
    assert not st.receive(forged) and st.rejected == 1
    assert not hasattr(svc.verifier(), "sign")


def test_older_heartbeat_does_not_replace_newer(svc):
    svc.record("grant", "g1", "REVOKE", T)
    old = RevocationService(b"revocation-service-seed-00000001").heartbeat(T)  # seq 1, revoked []
    new = svc.heartbeat(T)                                                  # seq 1 too
    newer = svc.heartbeat(T)                                                # seq 2, revoked [g1]
    st = state_with(svc, newer, old)
    assert st.latest["seq"] == 2
    assert check_release(st, T, 0.5, DEPS) == "AUTHORITY_DEPENDENCY_REVOKED"


def test_tampered_revoked_list_rejected(svc):
    svc.record("grant", "g1", "REVOKE", T)
    hb = svc.heartbeat(T)
    hb = dict(hb, revoked=[])
    assert not state_with(svc).receive(hb)


def test_skewed_service_clock(svc):
    fast = RevocationService(b"revocation-service-seed-00000001", clock_offset_s=0.3)
    st = state_with(fast, fast.heartbeat(T))
    assert check_release(st, T, 0.5, DEPS, max_future_skew_s=0.05) == "REVOCATION_HEARTBEAT_FROM_FUTURE"


def test_receipt_without_dependencies_fails_closed(svc):
    assert check_release(state_with(svc, svc.heartbeat(T)), T, 0.5, []) == "AUTHORITY_DEPENDENCIES_UNBOUND"
