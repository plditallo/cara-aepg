from copy import deepcopy
import pytest
from aepg_ref import AEPGEngine
from aepg_ref.attenuation import prove_attenuation
from aepg_ref.comparators import ComparatorRegistry, DEFAULT_SIDE_EFFECT_ORDER


def bound_constraint(value=10, path='physical.commanded_force', unit='N'):
    return {'type':'max_force_n','value':value,'comparator_id':'numeric-max/v1','comparator_version':'1',
            'binds_to':path,'parameter_type':'number','unit':unit}

def grant(gid='g1',parent=None,issuer='operator',subject='agent',value=10):
    return {'grant_id':gid,'issuer':issuer,'subject':subject,'root_id':'r','parent_grant_id':parent,
            'audience':['pep'],'resources':['arm'],'actions':['actuate'],'constraints':[bound_constraint(value)],
            'side_effect_class':'irreversible','delegation':{'allowed':True,'remaining_depth':2,'max_children':4},
            'validity':{'not_before':'2026-01-01T00:00:00Z','expires_at':'2027-01-01T00:00:00Z'}}

def test_child_cannot_retarget_constraint_binding():
    p=grant(subject='parent'); c=grant('g2','g1','parent','child',8)
    c['constraints'][0]['binds_to']='physical.commanded_velocity'
    fs=prove_attenuation(c,p,ComparatorRegistry.default(),DEFAULT_SIDE_EFFECT_ORDER)
    assert any('binding metadata binds_to' in f.message for f in fs)

def test_child_cannot_change_constraint_unit():
    p=grant(subject='parent'); c=grant('g2','g1','parent','child',8); c['constraints'][0]['unit']='lbf'
    fs=prove_attenuation(c,p,ComparatorRegistry.default(),DEFAULT_SIDE_EFFECT_ORDER)
    assert any('binding metadata unit' in f.message for f in fs)
