"""Revocation-freshness sweep (v0.4.3).

For each network configuration and delta, run a long benign motion (kettle to
burner, ~3.35 s) many times with a revocation landing at a random moment during
the motion, and the same motion with no revocation at all.

Metrics
  exposure_s        time from the revocation taking effect to the arm stopping
                    (safe state) or finishing. Lower is better.
  effect_after_rev  fraction of revoked runs where the effect completed anyway.
  availability_stop fraction of NON-revoked runs that stopped anyway because
                    heartbeats went stale (the cost of a tight delta).
  release_refused   fraction of runs that could not even start.
"""
import csv
import itertools
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "reference-implementation"))

from authority import AuthorityState, at  # noqa: E402
from gateways import CaraPAG  # noqa: E402
from probes import P, CTRL  # noqa: E402
from scenarios import burner_scene, STOVE  # noqa: E402

DELTAS = [0.25, 0.5, 1.0]
CADENCES = [0.05, 0.1, 0.25]
DELAYS = [0.02, 0.1]
LOSSES = [0.0, 0.1, 0.3]
SEEDS = 40


def one_run(delta, cadence, delay, loss, seed, revoke):
    rng = random.Random(seed * 7919 + 1)
    w = burner_scene("kettle", lit=False)
    a = AuthorityState(); a.root_grant(CTRL)
    g = CaraPAG(w, a, {CTRL: "cara:grant:sim:root"}, max_revocation_age_s=delta,
                network=dict(cadence_s=cadence, delay_s=delay, jitter_s=delay / 2, loss=loss, seed=seed))
    g.advance(1.0)  # longer warm-up so slow cadences have delivered something
    p = P("place", STOVE, v=0.15)
    _, receipt, call = g.authorize(p)
    t0 = g.t
    duration = len(w.motion_profile(p)[1]) * w.TICK_S
    # Sample across the whole motion, including its final moments.
    t_rev = t0 + rng.uniform(0.1, duration)
    fired = {"v": False}

    def hook(t):
        if revoke and not fired["v"] and t >= t_rev:
            a.revoke("grant", "cara:grant:sim:root", at(t_rev)); fired["v"] = True
        g.advance(t)
    ack = g.actuator.execute(p, receipt, at(t0), tick_hook=hook)
    return {
        "released": ack["executed"], "completed": ack.get("completed", False), "reason": ack.get("reason"),
        "t_end": ack.get("t_end", t0), "t_rev": t_rev if revoke else None,
    }


def main():
    rows = []
    for delta, cadence, delay, loss in itertools.product(DELTAS, CADENCES, DELAYS, LOSSES):
        rev = [one_run(delta, cadence, delay, loss, s, True) for s in range(SEEDS)]
        base = [one_run(delta, cadence, delay, loss, s, False) for s in range(SEEDS)]
        started = [r for r in rev if r["released"]]
        exposures = [max(0.0, r["t_end"] - r["t_rev"]) for r in started if r["t_end"] >= r["t_rev"]]
        rows.append({
            "delta_s": delta, "cadence_s": cadence, "delay_s": delay, "loss": loss,
            "release_refused": round(sum(not r["released"] for r in rev + base) / (2 * SEEDS), 3),
            "effect_after_rev": round(sum(r["completed"] and r["t_end"] > r["t_rev"] for r in started)
                                      / max(1, len(started)), 3),
            "exposure_mean_s": round(statistics.mean(exposures), 3) if exposures else None,
            "exposure_max_s": round(max(exposures), 3) if exposures else None,
            "availability_stop": round(sum(r["released"] and not r["completed"] for r in base) / SEEDS, 3),
            "theoretical_bound_s": round(cadence + delay * 1.5 + 0.05, 3),
        })
    with open(HERE / "delta_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    (HERE / "delta_sweep.json").write_text(json.dumps(rows, indent=2))
    return rows


if __name__ == "__main__":
    import time
    t = time.time(); rows = main()
    print(f"{len(rows)} configurations x {SEEDS} seeds x 2 in {time.time()-t:.1f}s")
    print(f"{'delta':>5} {'cad':>5} {'delay':>5} {'loss':>4} | {'refused':>7} {'eff_after':>9} {'exp_mean':>8} {'exp_max':>7} {'bound':>5} | {'avail_stop':>10}")
    for r in rows:
        print(f"{r['delta_s']:>5} {r['cadence_s']:>5} {r['delay_s']:>5} {r['loss']:>4} | {r['release_refused']:>7} "
              f"{r['effect_after_rev']:>9} {str(r['exposure_mean_s']):>8} {str(r['exposure_max_s']):>7} "
              f"{r['theoretical_bound_s']:>5} | {r['availability_stop']:>10}")
