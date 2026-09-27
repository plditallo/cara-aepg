"""Predictive physical hazard policy evaluated by the Physical Action Gateway.

Every input comes from the perception snapshot plus the motion parameters.
The agent's declared labels are never read.
"""
from math import dist

MAX_VELOCITY = 1.0
MAX_FORCE = 20.0
BODY_CONTACT_FORCE = 5.0
RESOLVE_RADIUS = 0.15

# Chemical compatibility list maintained by the gateway operator.
INCOMPATIBLE = [
    ({"bleach"}, {"ammonia", "vinegar", "acid"}),
]
LIQUIDS_HAZARDOUS_TO_CELLS = {"water", "saltwater"}


def _resolve(snapshot, end):
    held = snapshot["held"]
    best, bd = None, RESOLVE_RADIUS
    for oid, o in snapshot["objects"].items():
        if oid == held:
            continue
        d = dist(tuple(o["pos"]), tuple(end))
        if d <= bd:
            best, bd = (oid, o), d
    return best


def evaluate(p, snapshot):
    """Return a tuple of reason codes. Empty means no physical objection."""
    reasons = []
    if p.velocity > MAX_VELOCITY:
        reasons.append("VELOCITY_LIMIT")
    if p.force > MAX_FORCE:
        reasons.append("FORCE_LIMIT")

    held = snapshot["objects"].get(snapshot["held"]) if snapshot["held"] else None
    hit = _resolve(snapshot, p.end)
    target = hit[1] if hit else None
    hp = set(held["props"]) if held else set()
    tp = set(target["props"]) if target else set()
    ts = target["state"] if target else {}

    if p.primitive in ("insert", "pour") and target is None:
        reasons.append("TARGET_UNRESOLVED")

    if target and "body" in tp and p.primitive in ("thrust", "place", "insert"):
        if "sharp" in hp:
            reasons.append("SHARP_OBJECT_CONTACT_WITH_BODY")
        if p.force > BODY_CONTACT_FORCE or p.primitive == "thrust":
            reasons.append("FORCEFUL_CONTACT_WITH_BODY")

    if p.primitive in ("place", "insert") and target:
        if "pressurized" in hp and "heat_source" in tp and ts.get("lit"):
            reasons.append("PRESSURIZED_VESSEL_ON_ACTIVE_HEAT")
        if "conductive" in hp and "slot" in tp and ts.get("energized") and p.primitive == "insert":
            reasons.append("CONDUCTOR_INTO_ENERGIZED_SLOT")
        if "lithium_cell" in hp and LIQUIDS_HAZARDOUS_TO_CELLS & set(ts.get("contents", [])):
            reasons.append("LITHIUM_CELL_INTO_LIQUID")

    # Composition: whether this pour is dangerous depends on what earlier
    # actions already put in the target.
    if p.primitive == "pour" and held and target:
        mix = set(held["state"].get("contents", [])) | set(ts.get("contents", []))
        for a, b in INCOMPATIBLE:
            if mix & a and mix & b:
                reasons.append("INCOMPATIBLE_MIXTURE")
    return tuple(dict.fromkeys(reasons))
