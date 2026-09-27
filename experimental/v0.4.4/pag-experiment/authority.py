"""AEPG objects for arm actuation: grants, delegation, revocation, requests."""
import itertools
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from aepg_ref import AEPGEngine
from aepg_ref.canonical import sha256_uri
from aepg_ref.timeutil import parse_ts
from aepg_ref.revocation_heartbeat import RevocationService
from perception import PIS_ID

ROOT = Path(__file__).resolve().parents[1] / "reference-implementation"
SIG = {"key_id": "operator-key-1", "algorithm": "EdDSA", "value": "sig"}
PEP_ID = "pag-arm-1"
RESOURCE = "arm-1"
ACTION = "actuate"
OPERATOR = "cara:principal:sim:operator"
ROOT_ID = "cara:root:sim:r1"
T0 = "2026-09-27T18:00:00+00:00"

_seq = itertools.count(1)


from functools import lru_cache


@lru_cache(maxsize=1)
def engine():
    return AEPGEngine(ROOT / "schemas")


def at(seconds):
    return (parse_ts(T0) + timedelta(seconds=seconds)).isoformat()


at_seconds = at


def seconds_of(ts):
    return (parse_ts(ts) - parse_ts(T0)).total_seconds()


def envelope(max_force, max_velocity):
    return [
        {"type": "max_force_n", "value": max_force, "comparator_id": "numeric-max/v1", "comparator_version": "1",
         "binds_to": "physical.commanded_force", "parameter_type": "number", "unit": "N"},
        {"type": "max_velocity_mps", "value": max_velocity, "comparator_id": "numeric-max/v1", "comparator_version": "1",
         "binds_to": "physical.commanded_velocity", "parameter_type": "number", "unit": "m/s"},
    ]


def canonical_action(p, world_hash):
    """What gets hashed and bound. Declared labels are deliberately excluded."""
    return {
        "operation": f"arm.{p.primitive}", "action": ACTION, "resource": RESOURCE,
        "primitive": p.primitive, "end": [round(x, 4) for x in p.end],
        "velocity": p.velocity, "force": p.force,
        "physical": {"commanded_force": p.force, "commanded_force_unit": "N",
                     "commanded_velocity": p.velocity, "commanded_velocity_unit": "m/s"},
        "world_state_hash": world_hash,
    }


class AuthorityState:
    def __init__(self):
        self.grants = {}
        self.revocations = []
        # The revocation service is the only holder of the heartbeat signing key.
        self.revocation_service = RevocationService(b"sim-revocation-service-seed-0001")

    def root_grant(self, subject, max_force=20.0, max_velocity=1.0, depth=2, gid="cara:grant:sim:root"):
        g = {
            "schema": "cara.authority-grant/v0.2", "grant_id": gid, "issuer": OPERATOR, "subject": subject,
            "root_id": ROOT_ID, "parent_grant_id": None, "audience": [PEP_ID], "resources": [RESOURCE],
            "actions": [ACTION], "constraints": envelope(max_force, max_velocity), "side_effect_class": "irreversible",
            "delegation": {"allowed": depth > 0, "remaining_depth": depth, "max_children": 4},
            "validity": {"not_before": "2026-09-27T17:00:00Z", "expires_at": "2026-09-27T20:00:00Z"},
            "revocation_epoch": 1, "issued_at": "2026-09-27T17:00:00Z", "signature": dict(SIG),
        }
        self.grants[gid] = g
        return g

    def delegate(self, parent_id, subject, max_force, max_velocity, gid):
        p = self.grants[parent_id]
        c = deepcopy(p)
        c.update(grant_id=gid, subject=subject, issuer=p["subject"], parent_grant_id=parent_id,
                 constraints=envelope(max_force, max_velocity))
        c["delegation"] = dict(p["delegation"], remaining_depth=p["delegation"]["remaining_depth"] - 1,
                               allowed=p["delegation"]["remaining_depth"] - 1 > 0)
        self.grants[gid] = c
        return c

    def revoke(self, target_type, target_id, effective_at):
        self.revocation_service.record(target_type, target_id, "REVOKE", effective_at)
        self.revocations.append({
            "schema": "cara.revocation/v0.2", "revocation_id": f"cara:revocation:sim:{next(_seq)}",
            "issuer": OPERATOR, "target_type": target_type, "target_id": target_id, "operation": "REVOKE",
            "reason_code": "operator", "effective_at": effective_at, "new_epoch": len(self.revocations) + 2,
            "dependency_classes": [], "signature": dict(SIG),
        })

    def physical_envelope(self, grant_id):
        g = self.grants.get(grant_id)
        if not g:
            return None
        c = {x["type"]: x["value"] for x in g["constraints"]}
        return c.get("max_force_n"), c.get("max_velocity_mps")

    def build(self, p, grant_id, snapshot, world_hash, now):
        n = next(_seq)
        action = canonical_action(p, world_hash)
        ah = sha256_uri(action)
        activity = {
            "schema": "cara.activity/v0.2", "activity_id": f"cara:activity:sim:{n}", "actor_id": p.actor, "tier": 3,
            "operation": action["operation"], "provenance_root_ids": [ROOT_ID],
            "authority_basis_id": f"cara:authority-basis:sim:{n}", "started_at": now, "ended_at": None,
            "canonical_action_hash": ah,
        }
        basis = {
            "schema": "cara.authority-basis/v0.2", "authority_basis_id": activity["authority_basis_id"],
            "mode": "SINGLE", "grant_ids": [grant_id], "authority_root_ids": [ROOT_ID], "threshold": None,
            "proof_hash": "sha256:00", "revocation_snapshot_id": f"cara:revstate:sim:{len(self.revocations)}",
            "policy_version": "pag-sim-1", "evaluated_at": now, "signature": dict(SIG),
        }
        request = {
            "schema": "cara.authorization-request/v0.2", "request_id": f"cara:request:sim:{n}",
            "activity_id": activity["activity_id"], "subject": p.actor, "candidate_grant_ids": [grant_id],
            "resource_id": "cara:resource:sim:arm-1", "canonical_action_hash": ah, "state_hash": world_hash,
            "composition_state_id": None, "attestation_refs": [], "policy_information_source_ids": [PIS_ID],
            "requested_at": now, "nonce": f"nonce-{n:08d}", "signature": dict(SIG),
        }
        policy = {"critical_policy_information_source_ids": [PIS_ID]}
        return dict(request=request, activity=activity, basis=basis, grants=list(self.grants.values()),
                    revocations=list(self.revocations), policy=policy, current_state=snapshot, action=action)
