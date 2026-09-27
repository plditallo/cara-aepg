"""Shared fixtures. Every object here is schema-valid; tests mutate copies."""
from copy import deepcopy
from pathlib import Path
import itertools
import pytest
from aepg_ref import AEPGEngine
from aepg_ref.canonical import sha256_uri

ROOT = Path(__file__).resolve().parents[1]
SIG = {"key_id": "key-issuer-1", "algorithm": "EdDSA", "value": "sig"}
NOW = "2026-09-27T18:00:00Z"
PEP = "pep-db"
PRINCIPAL = "cara:principal:t:p"
AGENT_A = "cara:agent:t:a"
AGENT_B = "cara:agent:t:b"
ACTION = {"operation": "db.write", "action": "write", "resource": "db"}

_ids = itertools.count(1)


@pytest.fixture(scope="session")
def engine():
    return AEPGEngine(ROOT / "schemas")


def make_grant(grant_id="cara:grant:t:g1", subject=AGENT_A, issuer=PRINCIPAL, parent=None, **over):
    g = {
        "schema": "cara.authority-grant/v0.2", "grant_id": grant_id, "issuer": issuer, "subject": subject,
        "root_id": "cara:root:t:r1", "parent_grant_id": parent, "audience": [PEP],
        "resources": ["db"], "actions": ["write"], "constraints": [], "side_effect_class": "persistent",
        "delegation": {"allowed": True, "remaining_depth": 3, "max_children": 4},
        "validity": {"not_before": "2026-01-01T00:00:00Z", "expires_at": "2027-01-01T00:00:00Z"},
        "revocation_epoch": 1, "issued_at": "2026-01-01T00:00:00Z", "signature": dict(SIG),
    }
    g.update(over)
    return g


def delegate(parent, grant_id, subject, **over):
    """A correctly attenuated child of `parent`."""
    child = deepcopy(parent)
    child.update(grant_id=grant_id, subject=subject, issuer=parent["subject"], parent_grant_id=parent["grant_id"])
    child["delegation"] = dict(parent["delegation"], remaining_depth=parent["delegation"]["remaining_depth"] - 1)
    child.update(over)
    return child


def make_revocation(target_type, target_id, operation="REVOKE", effective_at="2026-09-01T00:00:00Z"):
    return {
        "schema": "cara.revocation/v0.2", "revocation_id": f"cara:revocation:t:{next(_ids)}",
        "issuer": PRINCIPAL, "target_type": target_type, "target_id": target_id, "operation": operation,
        "reason_code": "test", "effective_at": effective_at, "new_epoch": 2,
        "dependency_classes": [], "signature": dict(SIG),
    }


class Case:
    """One authorization call with sensible, schema-valid defaults."""

    def __init__(self, engine):
        self.engine = engine
        self.state = {"x": 1}
        self.action = dict(ACTION)
        self.grants = [make_grant()]
        self.revocations = []
        self.pep = PEP
        self.now = NOW
        self.activity = {
            "schema": "cara.activity/v0.2", "activity_id": "cara:activity:t:a1", "actor_id": AGENT_A, "tier": 3,
            "operation": "db.write", "provenance_root_ids": ["cara:root:t:r1", "cara:root:t:info"],
            "authority_basis_id": "cara:authority-basis:t:ab1", "started_at": NOW, "ended_at": None,
            "canonical_action_hash": sha256_uri(self.action),
        }
        self.basis = {
            "schema": "cara.authority-basis/v0.2", "authority_basis_id": "cara:authority-basis:t:ab1",
            "mode": "SINGLE", "grant_ids": ["cara:grant:t:g1"], "authority_root_ids": ["cara:root:t:r1"],
            "threshold": None, "proof_hash": "sha256:bbbb", "revocation_snapshot_id": "cara:revstate:t:rs1",
            "policy_version": "p1", "evaluated_at": NOW, "signature": dict(SIG),
        }
        self.request = {
            "schema": "cara.authorization-request/v0.2", "request_id": "cara:request:t:q1",
            "activity_id": "cara:activity:t:a1", "subject": AGENT_A, "candidate_grant_ids": ["cara:grant:t:g1"],
            "resource_id": "cara:resource:t:db", "canonical_action_hash": sha256_uri(self.action),
            "state_hash": sha256_uri(self.state), "composition_state_id": None, "attestation_refs": [],
            "policy_information_source_ids": ["cara:pis:t:state"], "requested_at": NOW, "nonce": "nonce-1234",
            "signature": dict(SIG),
        }
        self.policy = {"critical_policy_information_source_ids": ["cara:pis:t:state"]}

    def use(self, grant_ids, mode="SINGLE", threshold=None, subject=None):
        """Point basis and request at the given grant ids."""
        self.basis["grant_ids"] = list(grant_ids)
        self.basis["mode"] = mode
        self.basis["threshold"] = threshold
        self.request["candidate_grant_ids"] = list(grant_ids)
        if subject:
            self.request["subject"] = subject
            self.activity["actor_id"] = subject
        return self

    def run(self, current_state=None):
        return self.engine.authorize(
            self.request, self.activity, self.basis, self.grants, self.revocations, self.policy,
            self.state if current_state is None else current_state,
            action=self.action, pep_id=self.pep, now=self.now,
        )


@pytest.fixture
def case(engine):
    return Case(engine)


def codes(result):
    return {f.code for f in result.findings}
