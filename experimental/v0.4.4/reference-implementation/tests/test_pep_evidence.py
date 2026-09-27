"""Tier 3 PEP flow, receipts, and the evidence chain."""
from copy import deepcopy
import pytest
from aepg_ref.canonical import sha256_uri
from aepg_ref.consumption import ConfirmationAuthority, ConsumptionLedger
from aepg_ref.evidence import EvidenceLog
from aepg_ref.pep import Tier3PEP
from aepg_ref.receipts import ReceiptSigner
from conftest import make_revocation, PEP, AGENT_A

CKEY = b"user-confirmation-key-0123456789"
RKEY = b"pep-actuator-receipt-key-0123456"


@pytest.fixture
def rig(engine, case):
    ca = ConfirmationAuthority(CKEY)
    led = ConsumptionLedger(ca)
    led.open(ca.confirm(confirmation_id="c1", subject_id=AGENT_A, grant_id="cara:grant:t:g1",
                        resource_id="db", action="write", budget=1, canonical_action_hash=None))
    ev = EvidenceLog()
    pep = Tier3PEP(engine, led, ReceiptSigner(RKEY, "k1"), ev, PEP)
    return case, pep, led, ev


def call(case, pep, rid="cara:request:t:q1"):
    case.request["request_id"] = rid
    return pep.authorize(request=case.request, activity=case.activity, basis=case.basis, grants=case.grants,
                         revocations=case.revocations, policy=case.policy, current_state=case.state,
                         action=case.action, slot_id="c1", now=case.now)


def test_allow_issues_verifiable_receipt(rig):
    case, pep, led, ev = rig
    res, rc = call(case, pep)
    assert res.allowed and pep.signer.verify(rc)
    assert rc["canonical_action_hash"] == sha256_uri(case.action) and rc["pep_id"] == PEP
    assert ev.of_type("PREACTION_RECEIPT")


def test_tampered_receipt_fails_verification(rig):
    case, pep, *_ = rig
    _, rc = call(case, pep)
    bad = dict(rc, canonical_action_hash="sha256:" + "f" * 64)
    assert not pep.signer.verify(bad)
    assert not ReceiptSigner(b"some-other-key-000000000000000", "k1").verify(rc)


def test_deny_consumes_nothing_and_is_logged(rig):
    case, pep, led, ev = rig
    case.revocations = [make_revocation("grant", "cara:grant:t:g1")]
    res, rc = call(case, pep)
    assert not res.allowed and rc is None
    assert led.slot("c1").in_flight == 0
    assert ev.of_type("AUTHORITY_DENIED")


def test_second_request_denied_by_budget(rig):
    case, pep, *_ = rig
    assert call(case, pep)[1] is not None
    res, rc = call(case, pep, rid="cara:request:t:q2")
    assert rc is None and "AUTHORITY_CONSUMPTION_DENIED" in {f.code for f in res.findings}


def test_settle_commit_and_authority_loss(rig):
    case, pep, led, ev = rig
    _, rc = call(case, pep)
    ack = {"receipt_id": rc["receipt_id"], "executed": True, "outcome": []}
    assert pep.settle(rc, ack, lambda: False) == "EFFECT_AFTER_AUTHORITY_LOSS"
    assert ev.of_type("EFFECT_AFTER_AUTHORITY_LOSS")[0]["payload"]["recovery_required"]


def test_evidence_chain_detects_edit_delete_reorder(rig):
    case, pep, led, ev = rig
    _, rc = call(case, pep)
    pep.settle(rc, {"receipt_id": rc["receipt_id"], "executed": True, "outcome": []}, lambda: True)
    entries = ev.entries()
    assert EvidenceLog.verify(entries) == (True, None)
    edited = deepcopy(entries); edited[0]["payload"]["decision"] = "DENY"
    assert EvidenceLog.verify(edited)[0] is False
    assert EvidenceLog.verify(entries[1:])[0] is False
    assert EvidenceLog.verify([entries[1], entries[0]] + entries[2:])[0] is False
