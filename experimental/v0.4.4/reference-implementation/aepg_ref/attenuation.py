"""Delegation attenuation (AEPG Technical Specification v0.2, sections 8-9).

Every check here fails closed: anything that cannot be shown to be
STRICTLY_NARROWER or EQUIVALENT produces a hard finding.
"""
from .comparators import GOOD, Relation, set_subset, ordered_class, DEFAULT_SIDE_EFFECT_ORDER
from .models import ValidationFinding
from .timeutil import parse_ts

RULE = "AEPG-AUTH-009"
CODE = "CONSTRAINT_NOT_PROVEN_ATTENUATED"


def _finding(message, **details):
    return ValidationFinding(RULE, CODE, message, details=details)


def _constraint_map(grant, findings, label):
    out = {}
    for c in grant.get("constraints", []):
        if c["type"] in out:
            findings.append(_finding(f"{label} declares constraint {c['type']} more than once",
                                     field="constraints", relation=Relation.UNRESOLVED.value))
            continue
        out[c["type"]] = c
    return out


def prove_attenuation(child, parent, registry, side_effect_order=DEFAULT_SIDE_EFFECT_ORDER):
    findings = []

    # Lineage identity. A child must name this parent, stay under the same
    # root, and be issued by the agent that holds the parent grant.
    if child.get("parent_grant_id") != parent["grant_id"]:
        findings.append(_finding("child does not name this grant as its parent", field="parent_grant_id"))
    if child["root_id"] != parent["root_id"]:
        findings.append(_finding("child root differs from parent root", field="root_id"))
    if child["issuer"] != parent["subject"]:
        findings.append(_finding("child was not issued by the holder of the parent grant", field="issuer",
                                 child_issuer=child["issuer"], parent_subject=parent["subject"]))

    # Scope sets.
    for field in ("resources", "actions", "audience"):
        rel = set_subset(child.get(field, []), parent.get(field, []))
        if rel not in GOOD:
            findings.append(_finding(f"{field} relation is {rel.value}", field=field, relation=rel.value))

    # Validity interval.
    try:
        cnb, cexp = parse_ts(child["validity"]["not_before"]), parse_ts(child["validity"]["expires_at"])
        pnb, pexp = parse_ts(parent["validity"]["not_before"]), parse_ts(parent["validity"]["expires_at"])
        if cnb < pnb or cexp > pexp:
            findings.append(_finding("child validity expands parent validity", field="validity"))
        if cexp <= cnb:
            findings.append(_finding("child validity interval is empty or inverted", field="validity"))
    except (ValueError, KeyError) as exc:
        findings.append(_finding(f"validity could not be evaluated: {exc}", field="validity",
                                 relation=Relation.UNRESOLVED.value))

    # Delegation rights.
    cd, pd = child["delegation"], parent["delegation"]
    if not pd["allowed"]:
        findings.append(_finding("parent grant does not permit delegation", field="delegation.allowed"))
    if pd["remaining_depth"] < 1:
        findings.append(_finding("parent grant has no remaining delegation depth", field="delegation.remaining_depth"))
    elif cd["remaining_depth"] > pd["remaining_depth"] - 1:
        findings.append(_finding("delegation depth is not attenuated", field="delegation.remaining_depth"))
    if cd["allowed"] and not pd["allowed"]:
        findings.append(_finding("delegation permission expanded", field="delegation.allowed"))
    if "max_children" in pd:
        if "max_children" not in cd:
            findings.append(_finding("child drops parent's max_children limit", field="delegation.max_children"))
        elif cd["max_children"] > pd["max_children"]:
            findings.append(_finding("child max_children exceeds parent", field="delegation.max_children"))

    # Side-effect class.
    rel = ordered_class(side_effect_order)(child["side_effect_class"], parent["side_effect_class"])
    if rel not in GOOD:
        findings.append(_finding(f"side_effect_class relation is {rel.value}", field="side_effect_class",
                                 relation=rel.value, child=child["side_effect_class"],
                                 parent=parent["side_effect_class"]))

    # Registered constraints. Iterate the PARENT's constraints so that a
    # child cannot shed a limit by omitting it, and always compare with the
    # PARENT's comparator so that a child cannot choose its own semantics.
    pmap = _constraint_map(parent, findings, "parent")
    cmap = _constraint_map(child, findings, "child")
    for ctype, pc in pmap.items():
        cc = cmap.get(ctype)
        if cc is None:
            findings.append(_finding(f"child drops parent constraint {ctype}", field="constraints",
                                     constraint=ctype, relation=Relation.BROADER.value))
            continue
        cid = pc.get("comparator_id")
        for meta in ("binds_to", "parameter_type", "unit"):
            if cc.get(meta) != pc.get(meta):
                findings.append(_finding(f"child changes binding metadata {meta} for {ctype}", field="constraints",
                                         constraint=ctype, metadata=meta, parent=pc.get(meta), child=cc.get(meta)))
        if cc.get("comparator_id", cid) != cid or cc.get("comparator_version", pc.get("comparator_version")) != pc.get("comparator_version"):
            findings.append(_finding(f"child changes the comparator for {ctype}", field="constraints",
                                     constraint=ctype, parent_comparator=cid,
                                     child_comparator=cc.get("comparator_id")))
            continue
        rel = registry.compare(cid, cc["value"], pc["value"])
        if rel not in GOOD:
            findings.append(_finding(f"constraint {ctype} relation is {rel.value}", field="constraints",
                                     constraint=ctype, relation=rel.value, comparator=cid))
    for ctype in cmap.keys() - pmap.keys():
        # Conservative: a constraint type the parent never declared has no
        # parent value to compare against, so it cannot be proven narrower.
        findings.append(_finding(f"parent lacks constraint {ctype}", field="constraints",
                                 constraint=ctype, relation=Relation.UNRESOLVED.value))
    return findings
