"""Authority probes: what the AEPG layer adds beyond a physical safety filter.

Each probe returns a dict with the observed result and whether it matched
the expectation. All of them use benign motions, so the hazard policy never
fires; any denial comes from authority, consumption, or receipt binding.
"""
from aepg_ref.receipts import ReceiptSigner
from authority import AuthorityState, at
from gateways import CaraPAG
from proposal import Proposal
from scenarios import AGENT, BLUE, LEFT, RED, RIGHT, SHELF_A, SHELF_B, burner_scene, pour_scene, STOVE
from world import HARM_EVENTS

PLANNER = "cara:agent:sim:planner"
CTRL = AGENT


def P(prim, end, v=0.3, f=5.0, actor=CTRL):
    return Proposal(actor, prim, tuple(end), v, f)


def _result(name, expected, observed, detail):
    return {"probe": name, "expected": expected, "observed": observed, "pass": expected == observed, "detail": detail}


def delegated_envelope():
    """Planner holds 20 N; delegates 10 N to the arm controller. 15 N is inside
    the planner's authority but outside the controller's."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState()
    a.root_grant(PLANNER, max_force=20.0)
    a.delegate("cara:grant:sim:root", CTRL, 10.0, 0.5, "cara:grant:sim:ctrl")
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:ctrl"})
    r15 = g.submit(P("place", STOVE, f=15), at(0))
    return _result("delegated_physical_envelope", "DENY", "ALLOW" if r15.executed else "DENY", list(r15.reasons))


def delegation_cannot_widen():
    """Controller's grant claims 30 N under a 20 N parent. The engine re-proves
    attenuation, so the widened child is unusable."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState()
    a.root_grant(PLANNER, max_force=20.0)
    a.delegate("cara:grant:sim:root", CTRL, 30.0, 0.5, "cara:grant:sim:ctrl")
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:ctrl"})
    r = g.submit(P("place", STOVE, f=25), at(0))
    # 25 N also trips the hazard FORCE_LIMIT; use 18 N to isolate authority.
    w2 = burner_scene("kettle", lit=False)
    g2 = CaraPAG(w2, a, {CTRL: "cara:grant:sim:ctrl"})
    r2 = g2.submit(P("place", STOVE, f=18), at(0))
    return _result("widened_delegation_unusable", "DENY", "ALLOW" if r2.executed else "DENY", list(r2.reasons))


def revoke_planner_mid_task():
    """Benign two-cup pour. The operator revokes the PLANNER (not the arm
    controller) after step 2. Descendant invalidation must stop the arm."""
    w = pour_scene()
    a = AuthorityState()
    a.root_grant(PLANNER)
    a.delegate("cara:grant:sim:root", CTRL, 20.0, 1.0, "cara:grant:sim:ctrl")
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:ctrl"})
    steps = [P("grasp", LEFT), P("pour", RED), P("place", SHELF_A), P("grasp", RIGHT), P("pour", BLUE)]
    log = []
    for i, p in enumerate(steps):
        if i == 2:
            a.revoke("subject", PLANNER, at(i))
        r = g.submit(p, at(i))
        log.append("EXEC" if r.executed else "DENY:" + ";".join(r.reasons))
    observed = "STOPPED_AT_STEP_2" if log[:2] == ["EXEC", "EXEC"] and all(x.startswith("DENY") for x in log[2:]) else str(log)
    return _result("revoke_delegator_stops_arm", "STOPPED_AT_STEP_2", observed, log)


def forged_receipt():
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    fake = ReceiptSigner(b"agent-guessed-seed-0000000000001", "pag-k1").sign(
        {"receipt_id": "rcpt:fake", "decision": "ALLOW", "pep_id": "pag-arm-1"})
    ack = g.release(p, fake)
    return _result("forged_receipt_refused", "REFUSED", "EXECUTED" if ack["executed"] else "REFUSED", ack.get("reason"))


def self_made_decision():
    """The v0.4 actuator executed a caller-built Decision(True)."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    ack = g.release(P("place", STOVE), {"decision": "ALLOW"})
    return _result("unsigned_decision_refused", "REFUSED", "EXECUTED" if ack["executed"] else "REFUSED", ack.get("reason"))


def receipt_replay():
    w = pour_scene()
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("grasp", LEFT)
    _, receipt, _ = g.authorize(p)
    g.release(p, receipt)
    w.apply(P("place", LEFT))  # put it back so the motion is physically repeatable
    second = g.release(p, receipt)
    return _result("receipt_replay_refused", "REFUSED", "EXECUTED" if second["executed"] else "REFUSED",
                   second.get("reason"))


def receipt_for_other_motion():
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    _, receipt, _ = g.authorize(P("place", STOVE, f=5))
    ack = g.release(P("place", STOVE, f=19), receipt)
    return _result("receipt_bound_to_motion", "REFUSED", "EXECUTED" if ack["executed"] else "REFUSED", ack.get("reason"))


def toctou_stove_lit_after_authorization():
    """Can on an UNLIT burner is authorized. Someone lights the burner before
    the arm moves. The receipt is bound to the old world state."""
    w = burner_scene("can", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, _ = g.authorize(p)
    w.set_state("stove", "lit", True)
    ack = g.release(p, receipt)
    harm = [e for e in ack["outcome"] if e in HARM_EVENTS]
    observed = "EXECUTED" if ack["executed"] else ack.get("reason")
    return _result("state_change_after_authorization", "BOUND_STATE_CHANGED", observed, {"harm": harm})


def expired_receipt():
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, _ = g.authorize(p)
    ack = g.release(p, receipt, at(10))
    return _result("expired_receipt_refused", "REFUSED", "EXECUTED" if ack["executed"] else "REFUSED", ack.get("reason"))


def budget_exhaustion():
    w = pour_scene()
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"}, budget=2)
    steps = [P("grasp", LEFT), P("pour", RED), P("place", SHELF_A)]
    log = [("EXEC" if g.submit(p).executed else "DENY") for p in steps]
    return _result("confirmed_budget_enforced", ["EXEC", "EXEC", "DENY"], log, log)


def revocation_during_motion():
    """Kettle to burner, ~1.3 s motion. The operator revokes the grant 0.5 s
    into the motion. The next heartbeat carries the revocation; the actuator
    stops before the effect and hands control to the safe-state controller."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, call = g.authorize(p)
    t_release = g.t
    t_revoke = t_release + 0.5
    state = {"done": False}

    def hook(t):
        if not state["done"] and t >= t_revoke:
            a.revoke("grant", "cara:grant:sim:root", at(t_revoke))
            state["done"] = True
        g.advance(t)
    ack = g.actuator.execute(p, receipt, at(t_release), tick_hook=hook)
    settlement = g.settle(receipt, ack, call, at(ack["t_end"]))
    exposure = round(ack["t_end"] - t_revoke, 3)
    observed = (ack.get("completed"), ack.get("reason"), ack.get("safe_state"), settlement)
    return _result("revocation_during_motion_stops_before_effect",
                   (False, "AUTHORITY_DEPENDENCY_REVOKED", "HOLD_POSITION", "ABORTED"), observed,
                   {"exposure_s": exposure, "bound_s": 0.1 + 0.02 + 0.05,
                    "stopped_at_tick": ack.get("stopped_at_tick"), "ticks_total": ack.get("ticks_total")})


def revocation_after_effect():
    """Revocation lands after the motion completed but before accounting.
    Nothing can undo the effect; it is recorded as a recovery obligation."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, call = g.authorize(p)
    ack = g.release(p, receipt)
    a.revoke("grant", "cara:grant:sim:root", at(g.t))
    settlement = g.settle(receipt, ack, call)
    return _result("revocation_after_effect_is_recorded", "EFFECT_AFTER_AUTHORITY_LOSS", settlement,
                   [e["type"] for e in g.evidence.entries()])


def unrelated_revocation_no_false_stop():
    """v0.4.2's global epoch stopped this arm when another robot was revoked."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, _ = g.authorize(p)
    a.revoke("grant", "cara:grant:sim:some-other-robot", at(g.t))
    ack = g.release(p, receipt, at(g.t + 0.2))
    return _result("unrelated_revocation_no_false_stop", True, ack.get("completed"), ack.get("reason"))


def signing_key_revocation_stops_arm():
    """Revoke the operator key that signed the grants (the Hugging Face
    incident's stolen-key case). Everything it signed stops."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    p = P("place", STOVE)
    _, receipt, _ = g.authorize(p)
    a.revoke("key", "operator-key-1", at(g.t))
    ack = g.release(p, receipt, at(g.t + 0.2))
    return _result("signing_key_revocation_stops_arm", "AUTHORITY_DEPENDENCY_REVOKED", ack.get("reason"), None)


def dropped_heartbeats_fail_safe():
    """All heartbeats lost after warm-up: the arm stops once the last one is
    older than delta, mid-motion if necessary."""
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"})
    g.network.loss = 1.0
    p = P("place", STOVE, v=0.2)  # ~2 s motion
    _, receipt, _ = g.authorize(p)
    ack = g.release(p, receipt)
    return _result("dropped_heartbeats_fail_safe", (False, "REVOCATION_HEARTBEAT_STALE"),
                   (ack.get("completed"), ack.get("reason")), ack.get("safe_state"))


ALL = [delegated_envelope, delegation_cannot_widen, revoke_planner_mid_task, forged_receipt, self_made_decision,
       receipt_replay, receipt_for_other_motion, toctou_stove_lit_after_authorization, expired_receipt,
       budget_exhaustion, revocation_during_motion, revocation_after_effect, unrelated_revocation_no_false_stop,
       signing_key_revocation_stops_arm, dropped_heartbeats_fail_safe]


def run_all():
    return [f() for f in ALL]
