"""Bind grant constraints to canonical-action parameters.

Binding metadata is authority semantics. Missing paths, type mismatches, unit
mismatches, or unregistered comparators are UNRESOLVED and fail closed.
"""
from .models import ValidationFinding
from .comparators import GOOD

RULE='AEPG-REF-BIND-003'

def _get_path(obj,path):
    cur=obj
    for part in path.split('.'):
        if not isinstance(cur,dict) or part not in cur:
            raise KeyError(path)
        cur=cur[part]
    return cur

def _type_ok(v,t):
    if t=='number': return isinstance(v,(int,float)) and not isinstance(v,bool)
    if t=='integer': return isinstance(v,int) and not isinstance(v,bool)
    if t=='string': return isinstance(v,str)
    if t=='boolean': return isinstance(v,bool)
    return False

def evaluate_bound_constraints(grants, action, registry):
    findings=[]
    for g in grants:
        for c in g.get('constraints',[]):
            path=c.get('binds_to')
            if path is None:
                # v0.4.3: a constraint the engine cannot bind to the action cannot
                # be enforced, so it cannot authorize anything. Fail closed.
                findings.append(ValidationFinding(RULE, 'UNBOUND_CONSTRAINT',
                    f"constraint {c['type']!r} has no binds_to and cannot be enforced",
                    details={'grant_id': g['grant_id'], 'constraint': c['type']}))
                continue
            try: value=_get_path(action,path)
            except KeyError:
                findings.append(ValidationFinding(RULE,'BOUND_PARAMETER_UNRESOLVED',
                    f"bound action parameter {path!r} is absent",details={'grant_id':g['grant_id'],'constraint':c['type']}))
                continue
            typ=c.get('parameter_type')
            if not typ or not _type_ok(value,typ):
                findings.append(ValidationFinding(RULE,'BOUND_PARAMETER_TYPE_MISMATCH',
                    f"bound action parameter {path!r} does not match declared type",details={'expected_type':typ}))
                continue
            # Units are explicit authority semantics. Canonical action declares a sibling <field>_unit.
            unit=c.get('unit')
            if unit:
                leaf=path.split('.')[-1]
                parent='.'.join(path.split('.')[:-1])
                upath=(parent+'.' if parent else '')+leaf+'_unit'
                try: actual_unit=_get_path(action,upath)
                except KeyError: actual_unit=None
                if actual_unit != unit:
                    findings.append(ValidationFinding(RULE,'BOUND_PARAMETER_UNIT_MISMATCH',
                        f"bound action parameter {path!r} unit is unresolved or incompatible",
                        details={'expected_unit':unit,'actual_unit':actual_unit}))
                    continue
            cid=c.get('comparator_id')
            rel=registry.compare(cid,value,c['value'])
            if rel not in GOOD:
                findings.append(ValidationFinding(RULE,'BOUND_PARAMETER_OUTSIDE_GRANT',
                    f"action parameter {path!r} is not within grant constraint {c['type']}",
                    details={'requested':value,'authorized':c['value'],'relation':rel.value}))
    return findings
