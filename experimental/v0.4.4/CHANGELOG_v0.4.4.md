# v0.4.4 Experimental Changelog

- Corrected DD-2: stale-authority exposure is governed by `min(Δ, longest delivered-heartbeat gap) + one control tick`; removed the unproved “irreducible” wording.
- Implemented DD-6 pre-contact freshness using signed monotonic heartbeat sequence numbers rather than cross-clock timestamps.
- Added configurable contact-phase duration (0.1/0.3/1.0 s) to the simulator.
- Added pre-contact hesitation instrumentation.
- Added five DD-6 regression tests, including cross-clock skew and fail-safe heartbeat loss.
- Added `dd6_sweep.py`, `dd6_sweep.csv`, and `dd6_sweep.json` comparing periodic mediation with the sequence gate across the network matrix and contact-duration axis.
- No phase-dependent Δ policy was introduced.
