"""Corrected DD-6 measurement (register rows D1-D6).

Replaces the effect-after-revocation rate in v0.4.4 dd6_sweep.py, which
sampled revocation times over the UNGATED motion duration and so excluded
the tail of every gated motion (gated motions are longer by the hesitation).

Method: for a fixed configuration, run the motion once without revocation to
get its actual duration, then run it again with the revocation at every
25 ms offset across that actual duration. The vulnerable window (seconds) is
the total length of revocation offsets for which the effect still completed.
Predicted gated window: ceil_tick((contact mod cadence) + delay).
The start phase relative to the heartbeat schedule is swept over one cadence
in 0.05 s steps. Jitter and loss are zero so the result is deterministic.

Run from the v0.4.4 pag-experiment directory:
    python /path/to/dd6_window_measurement.py
Writes dd6_window_measurement.csv next to this script.
"""
import csv, os, statistics, sys
from multiprocessing import Pool
sys.path.insert(0, '.'); sys.path.insert(0, '../reference-implementation')
from authority import AuthorityState, at
from gateways import CaraPAG
from probes import P, CTRL
from scenarios import burner_scene, STOVE

STEP = 0.025
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dd6_window_measurement.csv')


def run(cad, delay, contact, phase, gate, r_off):
    w = burner_scene('kettle', lit=False); w.CONTACT_PHASE_S = contact
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: 'cara:grant:sim:root'}, max_revocation_age_s=1.0, precontact_sequence_gate=gate,
                network=dict(cadence_s=cad, delay_s=delay, jitter_s=0.0, loss=0.0, seed=0))
    g.advance(1.0 + phase); p = P('place', STOVE, v=0.15); _, rc, _ = g.authorize(p); t0 = g.t; f = {'v': 0}

    def hook(t):
        if r_off is not None and not f['v'] and t >= t0 + r_off:
            a.revoke('grant', 'cara:grant:sim:root', at(t0 + r_off)); f['v'] = 1
        g.advance(t)
    ack = g.actuator.execute(p, rc, at(t0), tick_hook=hook)
    return ack.get('completed', False), ack['t_end'] - t0, ack.get('precontact_hesitation_s', 0.0)


def measure(args):
    cad, delay, contact, phase, gate = args
    ok, end, hes = run(cad, delay, contact, phase, gate, None)
    offs = [i * STEP for i in range(1, int(end / STEP) + 1)]
    window = sum(run(cad, delay, contact, phase, gate, o)[0] for o in offs) * STEP
    return {'cadence_s': cad, 'delay_s': delay, 'contact_s': contact, 'start_phase_s': round(phase, 3),
            'protocol': 'dd6_phase_start_gate' if gate else 'periodic', 'motion_s': round(end, 3),
            'vulnerable_window_s': round(window, 3), 'hesitation_s': round(hes, 3),
            'predicted_gated_window_s': predicted(cad, delay, contact) if gate else ''}


def predicted(cad, delay, contact, tick=0.05):
    # (contact duration mod heartbeat cadence) + delay, rounded up to the control tick.
    m = contact % cad
    if m < 1e-9 or cad - m < 1e-9:
        m = 0.0
    import math
    return round(math.ceil(round((m + delay) / tick, 6)) * tick, 3)


if __name__ == '__main__':
    tasks = []
    for cad, delay in ((0.25, 0.1), (0.1, 0.02)):
        phases = [i * 0.05 for i in range(int(round(cad / 0.05)))]
        for contact in (0.1, 0.3, 0.4, 0.6, 0.9, 1.0, 1.15):
            for ph in phases:
                for gate in (False, True):
                    tasks.append((cad, delay, contact, ph, gate))
    with Pool(4) as pool:
        rows = pool.map(measure, tasks)
    with open(OUT, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    for cad, delay in ((0.25, 0.1), (0.1, 0.02)):
        print(f'cadence {cad}s delay {delay}s')
        for contact in (0.1, 0.3, 0.4, 0.6, 0.9, 1.0, 1.15):
            per = [r['vulnerable_window_s'] for r in rows if (r['cadence_s'], r['delay_s'], r['contact_s'], r['protocol']) == (cad, delay, contact, 'periodic')]
            gat = [r for r in rows if (r['cadence_s'], r['delay_s'], r['contact_s'], r['protocol']) == (cad, delay, contact, 'dd6_phase_start_gate')]
            gw = [r['vulnerable_window_s'] for r in gat]
            print(f'  contact {contact:>4}: periodic mean {statistics.mean(per):.3f} [{min(per):.3f}-{max(per):.3f}]'
                  f' | gated mean {statistics.mean(gw):.3f} [{min(gw):.3f}-{max(gw):.3f}] predicted {gat[0]["predicted_gated_window_s"]}'
                  f' | hesitation mean {statistics.mean(r["hesitation_s"] for r in gat):.3f}')
