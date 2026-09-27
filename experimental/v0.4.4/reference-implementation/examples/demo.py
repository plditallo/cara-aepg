"""Minimal AEPG v0.2 authorization cycle: one delegated grant, then its parent is revoked."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from aepg_ref import AEPGEngine
from aepg_ref.canonical import sha256_uri

engine = AEPGEngine(ROOT / "schemas")
sig = {"key_id": "demo-key-1", "algorithm": "EdDSA", "value": "sig"}
now = "2026-09-27T18:00:00Z"
pep = "demo-pep"
state = {"door": "closed", "human_distance_m": 3.0}
action = {"operation": "tool.write", "action": "write", "resource": "report"}

parent = {"schema": "cara.authority-grant/v0.2", "grant_id": "cara:grant:demo:g1", "issuer": "cara:principal:demo:p1",
          "subject": "cara:agent:demo:agent1", "root_id": "cara:root:demo:r1", "parent_grant_id": None,
          "audience": [pep], "resources": ["report"], "actions": ["write"], "constraints": [],
          "side_effect_class": "persistent", "delegation": {"allowed": True, "remaining_depth": 2, "max_children": 3},
          "validity": {"not_before": "2026-09-27T17:00:00Z", "expires_at": "2026-09-27T19:00:00Z"},
          "revocation_epoch": 1, "issued_at": "2026-09-27T17:00:00Z", "signature": sig}
child = dict(parent, grant_id="cara:grant:demo:g2", issuer=parent["subject"], subject="cara:agent:demo:agent2",
             parent_grant_id=parent["grant_id"], delegation={"allowed": False, "remaining_depth": 0, "max_children": 0})

activity = {"schema": "cara.activity/v0.2", "activity_id": "cara:activity:demo:a1", "actor_id": child["subject"], "tier": 3,
            "operation": action["operation"], "provenance_root_ids": ["cara:root:demo:r1", "cara:root:demo:research"],
            "authority_basis_id": "cara:authority-basis:demo:ab1", "started_at": now, "ended_at": None,
            "canonical_action_hash": sha256_uri(action)}
basis = {"schema": "cara.authority-basis/v0.2", "authority_basis_id": "cara:authority-basis:demo:ab1", "mode": "SINGLE",
         "grant_ids": [child["grant_id"]], "authority_root_ids": ["cara:root:demo:r1"], "threshold": None,
         "proof_hash": "sha256:bbbb", "revocation_snapshot_id": "cara:revstate:demo:rs1", "policy_version": "p1",
         "evaluated_at": now, "signature": sig}
request = {"schema": "cara.authorization-request/v0.2", "request_id": "cara:request:demo:q1",
           "activity_id": activity["activity_id"], "subject": child["subject"], "candidate_grant_ids": [child["grant_id"]],
           "resource_id": "cara:resource:demo:report", "canonical_action_hash": sha256_uri(action),
           "state_hash": sha256_uri(state), "composition_state_id": None, "attestation_refs": [],
           "policy_information_source_ids": ["cara:pis:demo:state"], "requested_at": now, "nonce": "nonce-1234",
           "signature": sig}
policy = {"critical_policy_information_source_ids": ["cara:pis:demo:state"]}
revoke_parent = {"schema": "cara.revocation/v0.2", "revocation_id": "cara:revocation:demo:rv1",
                 "issuer": "cara:principal:demo:p1", "target_type": "grant", "target_id": parent["grant_id"],
                 "operation": "REVOKE", "reason_code": "demo", "effective_at": "2026-09-27T17:30:00Z",
                 "new_epoch": 2, "dependency_classes": ["grant"], "signature": sig}

for label, revocations in (("before revocation", []), ("after parent revoked", [revoke_parent])):
    result = engine.authorize(request, activity, basis, [parent, child], revocations, policy, state,
                              action=action, pep_id=pep, now=now)
    print(f"{label}: {result.decision}")
    for f in result.findings:
        print(f"  {'HARD' if f.hard else 'note'} {f.rule_id} {f.code}: {f.message}")
