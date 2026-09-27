"""Simulated actuator trust boundary (v0.4.3).

Governed mode:
  RELEASE   Before the first tick: receipt signature (public key only),
            audience, replay, expiry, revocation heartbeat freshness and
            dependency check, world-state binding, exact-motion binding, and
            a runtime envelope present in the receipt.
  MOTION    At every control tick: the same heartbeat check, plus the
            MEASURED force and velocity the world reports for that tick
            against the receipt's runtime envelope. Any failure hands control
            to the SafeStateController and the effect never completes.
  EFFECT    Only if every tick passes is the primitive's effect applied.

The actuator holds verifiers, never signing keys.
"""
from math import dist

from aepg_ref.canonical import sha256_uri
from aepg_ref.revocation_heartbeat import HeartbeatState, check_release
from aepg_ref.timeutil import parse_ts
from authority import PEP_ID, canonical_action, at_seconds, seconds_of


class SafeStateController:
    """Standing safety authority, independent of any agent grant.

    It chooses from a fixed set of pre-verified maneuvers using the actuator's
    own perception of the world, never caller-supplied context. None of the
    maneuvers continues the interrupted task: a pour is never completed.
    """
    BODY_RADIUS = 0.35
    MANEUVERS = ("RETRACT_TO_MOTION_START", "UPRIGHT_AND_HOLD", "HOLD_POSITION", "STOP")

    def select(self, snapshot, primitive, gripper_pos):
        held = snapshot["objects"].get(snapshot["held"]) if snapshot["held"] else None
        if held and "sharp" in held["props"]:
            for o in snapshot["objects"].values():
                if "body" in o["props"] and dist(tuple(o["pos"]), gripper_pos) <= self.BODY_RADIUS:
                    return "RETRACT_TO_MOTION_START"
        if primitive == "pour":
            return "UPRIGHT_AND_HOLD"
        if held:
            return "HOLD_POSITION"
        return "STOP"

    def perform(self, world, maneuver, start):
        if maneuver == "RETRACT_TO_MOTION_START":
            world.move_gripper(start)
        # UPRIGHT_AND_HOLD / HOLD_POSITION / STOP leave the arm where it is.
        return maneuver


class Actuator:
    def __init__(self, world, receipt_verifier=None, heartbeat_verifier=None, max_revocation_age_s=0.5,
                 safe_state=None, precontact_sequence_gate=False):
        self.world = world
        self.receipt_verifier = receipt_verifier
        self.heartbeats = HeartbeatState(heartbeat_verifier) if heartbeat_verifier else None
        self.max_age = max_revocation_age_s
        self.safe_state = safe_state or SafeStateController()
        self.precontact_sequence_gate = precontact_sequence_gate
        self.used_receipts = set()
        self.executed = []
        self.safe_state_log = []

    @property
    def governed(self):
        return self.receipt_verifier is not None

    def receive_heartbeat(self, hb):
        return self.heartbeats.receive(hb) if self.heartbeats else False

    # ------------------------------------------------------------------
    def execute(self, p, receipt=None, now=None, tick_hook=None):
        """Returns an ack. tick_hook(t_seconds) lets the harness deliver
        network messages as simulated time passes."""
        if not self.governed:
            events = self.world.apply(p)
            self.executed.append(p)
            return {"receipt_id": None, "executed": True, "completed": True, "reason": None, "outcome": events}

        t0 = seconds_of(now)
        if tick_hook:
            tick_hook(t0)
        reason = self._release_check(p, receipt, at_seconds(t0))
        if reason:
            return {"receipt_id": (receipt or {}).get("receipt_id"), "executed": False, "completed": False,
                    "reason": reason, "outcome": [], "t_end": t0}
        self.used_receipts.add(receipt["receipt_id"])

        limits = receipt["release_limits"]
        deps = receipt["authority_dependencies"]
        start, ticks = self.world.motion_profile(p)
        t = t0
        contact_gate_done = False
        hesitation_s = 0.0
        for tick in ticks:
            # DD-6: clock-free phase-bound freshness. At final approach/contact
            # boundary, remember the highest verified heartbeat sequence already
            # seen and require a strictly newer one before admitting contact.
            if self.precontact_sequence_gate and tick["phase"] == "contact" and not contact_gate_done:
                phase_seq = self.heartbeats.latest["seq"] if self.heartbeats.latest else -1
                while True:
                    t += self.world.TICK_S
                    hesitation_s += self.world.TICK_S
                    if tick_hook:
                        tick_hook(t)
                    stop = check_release(self.heartbeats, at_seconds(t), self.max_age, deps)
                    if stop:
                        snap = self.world.snapshot()
                        maneuver = self.safe_state.select(snap, p.primitive, self.world.gripper_pos())
                        self.safe_state.perform(self.world, maneuver, start)
                        self.safe_state_log.append((stop, maneuver))
                        return {"receipt_id": receipt["receipt_id"], "executed": True, "completed": False,
                                "reason": stop, "safe_state": maneuver, "stopped_at_tick": tick["k"],
                                "ticks_total": len(ticks), "outcome": ["SAFE_STATE:" + maneuver],
                                "t_end": t, "precontact_hesitation_s": hesitation_s}
                    if self.heartbeats.latest and self.heartbeats.latest["seq"] > phase_seq:
                        contact_gate_done = True
                        break
            t += self.world.TICK_S
            if tick_hook:
                tick_hook(t)
            stop = check_release(self.heartbeats, at_seconds(t), self.max_age, deps)
            if not stop and tick["force"] > limits["max_measured_force_n"]:
                stop = "MEASURED_FORCE_LIMIT_EXCEEDED"
            if not stop and tick["velocity"] > limits["max_measured_velocity_mps"]:
                stop = "MEASURED_VELOCITY_LIMIT_EXCEEDED"
            if stop:
                snap = self.world.snapshot()
                maneuver = self.safe_state.select(snap, p.primitive, tick["pos"])
                self.world.move_gripper(tick["pos"])
                self.safe_state.perform(self.world, maneuver, start)
                self.safe_state_log.append((stop, maneuver))
                return {"receipt_id": receipt["receipt_id"], "executed": True, "completed": False,
                        "reason": stop, "safe_state": maneuver, "stopped_at_tick": tick["k"],
                        "ticks_total": len(ticks), "outcome": ["SAFE_STATE:" + maneuver], "t_end": t}
            self.world.move_gripper(tick["pos"])
        events = self.world.apply(p)
        self.executed.append(p)
        return {"receipt_id": receipt["receipt_id"], "executed": True, "completed": True, "reason": None,
                "outcome": events, "t_end": t, "precontact_hesitation_s": hesitation_s}

    def _release_check(self, p, receipt, now):
        if not receipt or not self.receipt_verifier.verify(receipt):
            return "RECEIPT_INVALID"
        if receipt.get("decision") != "ALLOW" or receipt.get("pep_id") != PEP_ID:
            return "RECEIPT_NOT_FOR_THIS_ACTUATOR"
        if receipt["receipt_id"] in self.used_receipts:
            return "RECEIPT_REPLAYED"
        if parse_ts(now) > parse_ts(receipt["expires_at"]):
            return "RECEIPT_EXPIRED"
        if self.heartbeats is None:
            return "REVOCATION_STATE_UNAVAILABLE"
        hb = check_release(self.heartbeats, now, self.max_age, receipt.get("authority_dependencies") or [])
        if hb:
            return hb
        lim = receipt.get("release_limits") or {}
        if not isinstance(lim.get("max_measured_force_n"), (int, float)) or \
                not isinstance(lim.get("max_measured_velocity_mps"), (int, float)):
            return "RUNTIME_ENVELOPE_UNRESOLVED"
        current = sha256_uri(self.world.snapshot())
        if receipt["state_hash"] != current:
            return "BOUND_STATE_CHANGED"
        if receipt["canonical_action_hash"] != sha256_uri(canonical_action(p, current)):
            return "ACTION_NOT_BOUND_BY_RECEIPT"
        return None
