# CARA/AEPG v0.4.4 Experimental Branch

This is **not** a normative specification release. It corrects the v0.4.2 mechanisms that existed in name but not in behavior (see `CHANGELOG_v0.4.4.md`), and runs the revocation-freshness experiment those mechanisms were meant to enable.

1. **Unbound constraints fail closed.** A constraint without `binds_to` cannot authorize anything.
2. **Measured means measured.** Motions run over 50 ms control ticks; the actuator checks per-tick measured force and velocity against the receipt's runtime envelope, and the effect applies only if the motion completes.
3. **Revocation freshness is real.** A separate revocation service on its own clock publishes Ed25519-signed heartbeats over a network with cadence, delay, jitter, and loss. The actuator holds only public keys. Revocation state is per authority dependency rather than a global epoch, so unrelated and future-dated revocations no longer stop anything.
4. **Safe state comes from perception.** The safe-state controller picks from a fixed maneuver set using its own view of the world, never completes an interrupted task, and releases the reserved budget.
5. **Multi-grant consumption remains fail closed.**

## Headline result

`pag-experiment/delta_sweep.py`, 54 network configurations × 40 seeds: typical stale-authority exposure is about half the heartbeat cadence plus delay; under packet loss the worst case approaches Δ. Revocations landing in the final approach of a motion are not caught in time, at a rate tracking (cadence + delay) / motion duration (0 to 12.5% here). Δ set tighter than the network can sustain stops nearly every benign run. Details and candidate normative text in `DESIGN_DECISIONS_v0.4.4.md`.

## Test status

- Reference implementation: **120 passed**
- PAG experiment: **82 passed**
- Combined: **202 passed**

Simulation and reference-implementation results only. Not evidence of real-robot safety.

## Run

```bash
cd reference-implementation && python -m pytest -q
cd ../pag-experiment && python -m pytest -q && python run_experiment.py && python delta_sweep.py
```

Requires `jsonschema`, `referencing`, `cryptography`, and `pytest`.


## v0.4.4 DD-6
Adds a clock-free pre-contact freshness gate keyed to signed heartbeat sequence numbers, configurable contact duration, and a comparative DD-6 sweep. See `DESIGN_DECISIONS_v0.4.4.md` and `DD6_EXPERIMENT_REPORT.md`.
