"""DD-6 phase-bound freshness experiment (v0.4.4).

Frozen v0.4.3 network matrix plus one new axis: contact duration.
Compare periodic-heartbeat mediation alone against a clock-free pre-contact gate
that records the highest heartbeat sequence at contact-phase start and requires
strictly higher sequence before contact is admitted.
"""
import csv, itertools, json, random, statistics, sys, multiprocessing
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(HERE.parent/'reference-implementation'))
from authority import AuthorityState, at
from gateways import CaraPAG
from probes import P, CTRL
from scenarios import burner_scene, STOVE

DELTAS=[0.25,0.5,1.0]; CADENCES=[0.05,0.1,0.25]; DELAYS=[0.02,0.1]; LOSSES=[0.0,0.1,0.3]
CONTACT_DURATIONS=[0.1,0.3,1.0]; SEEDS=20; PROTOCOLS=[False,True]

def one_run(delta,cadence,delay,loss,contact_s,seed,revoke,gate):
    rng=random.Random(seed*7919+1)
    w=burner_scene('kettle',lit=False); w.CONTACT_PHASE_S=contact_s
    a=AuthorityState(); a.root_grant(CTRL)
    g=CaraPAG(w,a,{CTRL:'cara:grant:sim:root'},max_revocation_age_s=delta,
              precontact_sequence_gate=gate,
              network=dict(cadence_s=cadence,delay_s=delay,jitter_s=delay/2,loss=loss,seed=seed))
    g.advance(1.0)
    p=P('place',STOVE,v=0.15); _,receipt,_=g.authorize(p)
    if receipt is None:
        return {'released':False,'completed':False,'reason':'AUTH_DENIED','hesitation':0.0}
    t0=g.t; ticks=w.motion_profile(p)[1]; duration=len(ticks)*w.TICK_S
    t_rev=t0+rng.uniform(0.1,duration); fired={'v':False}
    def hook(t):
        if revoke and not fired['v'] and t>=t_rev:
            a.revoke('grant','cara:grant:sim:root',at(t_rev)); fired['v']=True
        g.advance(t)
    ack=g.actuator.execute(p,receipt,at(t0),tick_hook=hook)
    return {'released':ack['executed'],'completed':ack.get('completed',False),'reason':ack.get('reason'),
            't_end':ack.get('t_end',t0),'t_rev':t_rev if revoke else None,
            'hesitation':ack.get('precontact_hesitation_s',0.0),'duration':duration}

def aggregate(args):
    gate,contact_s,delta,cadence,delay,loss=args
    rev=[one_run(delta,cadence,delay,loss,contact_s,s,True,gate) for s in range(SEEDS)]
    base=[one_run(delta,cadence,delay,loss,contact_s,s,False,gate) for s in range(SEEDS)]
    started=[r for r in rev if r['released']]
    exp=[max(0,r['t_end']-r['t_rev']) for r in started if r.get('t_rev') is not None]
    hes=[r['hesitation'] for r in base if r['released']]
    return {
      'protocol':'dd6_seq_gate' if gate else 'v0.4.3_periodic', 'contact_s':contact_s,
      'delta_s':delta,'cadence_s':cadence,'delay_s':delay,'loss':loss,
      'effect_after_rev':round(sum(r['completed'] and r['t_end']>r['t_rev'] for r in started)/max(1,len(started)),3),
      'exposure_mean_s':round(statistics.mean(exp),3) if exp else None,
      'exposure_max_s':round(max(exp),3) if exp else None,
      'availability_stop':round(sum(r['released'] and not r['completed'] for r in base)/SEEDS,3),
      'benign_completion':round(sum(r['completed'] for r in base)/SEEDS,3),
      'hesitation_mean_s':round(statistics.mean(hes),3) if hes else None,
      'hesitation_p95_s':round(sorted(hes)[max(0,int(.95*len(hes))-1)],3) if hes else None,
      'hesitation_max_s':round(max(hes),3) if hes else None,
    }

def main():
    tasks=list(itertools.product(PROTOCOLS,CONTACT_DURATIONS,DELTAS,CADENCES,DELAYS,LOSSES))
    with multiprocessing.Pool(processes=min(4,multiprocessing.cpu_count())) as pool:
        rows=pool.map(aggregate,tasks)
    with open(HERE/'dd6_sweep.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    (HERE/'dd6_sweep.json').write_text(json.dumps(rows,indent=2))
    return rows

if __name__=='__main__':
    import time
    t=time.time(); rows=main(); print(f'{len(rows)} configurations in {time.time()-t:.1f}s')
    for c in CONTACT_DURATIONS:
      for protocol in ('v0.4.3_periodic','dd6_seq_gate'):
        rr=[r for r in rows if r['contact_s']==c and r['protocol']==protocol]
        print(c,protocol,'mean effect_after_rev',round(statistics.mean(r['effect_after_rev'] for r in rr),3),
              'mean benign_completion',round(statistics.mean(r['benign_completion'] for r in rr),3),
              'mean hesitation',round(statistics.mean(r['hesitation_mean_s'] or 0 for r in rr),3))
