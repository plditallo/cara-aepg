# DD-6 Phase-Bound Freshness Experiment — v0.4.4

## Protocol
The v0.4.3 network axes are retained: Δ ∈ {0.25, 0.5, 1.0}s, heartbeat cadence ∈ {0.05, 0.1, 0.25}s, delay ∈ {0.02, 0.1}s, loss ∈ {0, 0.1, 0.3}. Contact duration adds {0.1, 0.3, 1.0}s. Two protocols are compared: v0.4.3 periodic heartbeat mediation and DD-6 sequence-gated contact freshness.

The checked-in run uses 20 deterministic seeds per configuration. This is an expanded experimental matrix (324 aggregate configurations) and should be treated as an experimental run, not a confidence-interval study.

## Aggregate result across network configurations

| Contact phase | Protocol | Mean effect-after-revocation | Mean benign completion | Mean pre-contact hesitation |
|---:|---|---:|---:|---:|
| 0.1 s | periodic | 0.027 | 0.774 | 0.000 s |
| 0.1 s | DD-6 sequence gate | 0.002 | 0.770 | 0.073 s |
| 0.3 s | periodic | 0.027 | 0.774 | 0.000 s |
| 0.3 s | DD-6 sequence gate | 0.005 | 0.770 | 0.091 s |
| 1.0 s | periodic | 0.027 | 0.774 | 0.000 s |
| 1.0 s | DD-6 sequence gate | 0.004 | 0.770 | 0.080 s |

The gate sharply reduced but did not eliminate effect-after-revocation. The remaining nonzero cases are consistent with the expected residual interval after the qualifying heartbeat and before effect completion. The experiment therefore does not establish zero stale-authority exposure.

Hesitation should be interpreted as a distribution conditioned by heartbeat cadence/delivery, not merely a binary cost. Per-configuration mean, p95, and maximum hesitation are retained in the CSV/JSON outputs.

## Limitations
This is a deterministic simulator, not a real-robot result. Contact dynamics are synthetic. The checked-in run uses 20 seeds per aggregate configuration. No claim of optimality, lower bound, or general physical safety follows from this experiment.
