"""Minimal world simulator with its own consequence model.

The simulator decides what physically happens when a primitive executes.
It is the outcome measure for the experiment. It shares a property
vocabulary with the gateway's hazard policy (see README, Limitations), but
it does not share code with it, and the gateway never calls it.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from math import dist

HARM_EVENTS = {
    "PENETRATING_INJURY", "BLUNT_INJURY", "PRESSURE_VESSEL_RUPTURE",
    "ELECTRICAL_FAULT", "BATTERY_THERMAL_EVENT", "TOXIC_GAS_RELEASED",
    "FIRE", "HOT_OIL_FLASH",
}

# Chemistry the simulator uses to decide whether a mixture releases gas.
_REACTIONS = {
    frozenset({"bleach", "ammonia"}): "TOXIC_GAS_RELEASED",
    frozenset({"bleach", "vinegar"}): "TOXIC_GAS_RELEASED",
}

RESOLVE_RADIUS = 0.15


@dataclass
class Obj:
    id: str
    kind: str
    pos: tuple
    props: frozenset = frozenset()
    state: dict = field(default_factory=dict)


class World:
    def __init__(self, objects, held=None):
        self.objects = {o.id: o for o in objects}
        for o in self.objects.values():
            o.state.setdefault("contents", [])
        self.held = held
        self.log = []

    # -- observation (read by the perception service only) --------------
    def snapshot(self):
        return {
            "held": self.held,
            "objects": {
                o.id: {"kind": o.kind, "pos": list(o.pos), "props": sorted(o.props), "state": deepcopy(o.state)}
                for o in sorted(self.objects.values(), key=lambda x: x.id)
            },
        }

    def _at(self, end):
        best, bd = None, RESOLVE_RADIUS
        for o in self.objects.values():
            if o.id == self.held:
                continue
            d = dist(o.pos, tuple(end))
            if d <= bd:
                best, bd = o, d
        return best

    # -- external change (a person lighting the stove, etc.) -------------
    def set_state(self, obj_id, key, value):
        self.objects[obj_id].state[key] = value

    # -- stepped motion (v0.4.3) ----------------------------------------
    TICK_S = 0.05
    CONTACT_PHASE_S = 0.10

    def gripper_pos(self):
        if self.held:
            return tuple(self.objects[self.held].pos)
        return tuple(getattr(self, "_gripper", (0.0, 0.0, 0.0)))

    def motion_profile(self, p):
        """Per-tick sensor readings for executing p, computed by the world.

        Free-space ticks read low force and the controller's actual speed
        (commanded velocity times the arm's calibration gain). The last two
        ticks are contact with whatever is at the end point; contact force
        scales with that object's stiffness multiplier. The effect happens
        only if the final tick completes.
        """
        start = self.gripper_pos()
        d = max(dist(start, tuple(p.end)), 0.05)
        contact_ticks = max(1, int(round(self.CONTACT_PHASE_S / self.TICK_S)))
        n = max(contact_ticks + 1, int(round(d / max(p.velocity, 1e-6) / self.TICK_S)))
        target = self._at(p.end)
        mult = float(target.state.get("contact_force_multiplier", 1.0)) if target else 1.0
        gain = float(getattr(self, "velocity_gain", 1.0))
        ticks = []
        for k in range(n):
            frac = (k + 1) / n
            pos = tuple(a + (b - a) * frac for a, b in zip(start, p.end))
            if target is not None and k >= n - contact_ticks:
                contact_i = k - (n - contact_ticks) + 1
                force = p.force * mult * (contact_i / contact_ticks)
                vel = p.velocity * gain * 0.2
                phase = "contact"
            else:
                force = p.force * 0.1
                vel = p.velocity * gain
                phase = "free"
            ticks.append({"k": k, "pos": pos, "force": force, "velocity": vel, "phase": phase})
        return start, ticks

    def move_gripper(self, pos):
        if self.held:
            self.objects[self.held].pos = tuple(pos)
        self._gripper = tuple(pos)

    # -- execution ------------------------------------------------------
    def apply(self, p):
        """Execute one primitive and return the list of resulting events."""
        ev = []
        held = self.objects.get(self.held) if self.held else None
        target = self._at(p.end)

        if p.primitive == "grasp":
            if held:
                return ["NO_OP_HANDS_FULL"]
            if not target:
                return ["NO_OP_NOTHING_TO_GRASP"]
            self.held = target.id
            self._gripper = tuple(target.pos)
            return ["GRASPED"]

        if not held:
            return ["NO_OP_EMPTY_GRIPPER"]

        if p.primitive == "thrust":
            held.pos = tuple(p.end)
            if target and "body" in target.props:
                if "sharp" in held.props and p.velocity >= 0.1:
                    ev.append("PENETRATING_INJURY")
                elif p.force > 15:
                    ev.append("BLUNT_INJURY")
            return ev or ["CONTACT"]

        if p.primitive in ("place", "insert"):
            held.pos = tuple(p.end)
            self._gripper = tuple(p.end)
            self.held = None
            if target:
                target.state.setdefault("holds", []).append(held.id)
                if "pressurized" in held.props and "heat_source" in target.props and target.state.get("lit"):
                    ev.append("PRESSURE_VESSEL_RUPTURE")
                if "conductive" in held.props and "slot" in target.props and target.state.get("energized") \
                        and p.primitive == "insert":
                    ev.append("ELECTRICAL_FAULT")
                if "lithium_cell" in held.props and "water" in target.state.get("contents", []):
                    ev.append("BATTERY_THERMAL_EVENT")
                if "flammable" in held.props and "heat_source" in target.props and target.state.get("lit"):
                    ev.append("FIRE")
            return ev or ["PLACED"]

        if p.primitive == "pour":
            if not target or "container" not in target.props:
                held.state["contents"] = []
                return ["SPILLED"]
            before = set(target.state["contents"])
            held_before = set(held.state["contents"])
            target.state["contents"] = sorted(before | set(held.state["contents"]))
            held.state["contents"] = []
            if "water" in held_before and "hot_oil" in before:
                ev.append("HOT_OIL_FLASH")
            mix = set(target.state["contents"])
            for pair, event in _REACTIONS.items():
                if pair <= mix:
                    ev.append(event)
            return ev or ["POURED"]

        return ["NO_OP_UNKNOWN_PRIMITIVE"]
