# DD-6 window measurement (register rows D1-D6)

Corrects the v0.4.4 DD-6 sweep, which sampled revocation times over the ungated
motion duration and so never sampled the tail of gated motions.

- `dd6_window_measurement.py` scans the revocation time in 25 ms steps across each
  motion's actual duration and reports the vulnerable window in seconds, with the
  start phase swept over one heartbeat cadence. Deterministic (no jitter, no loss).
- `dd6_window_measurement.csv` is its output: 98 configurations (2 networks x
  7 contact durations x start phases x 2 protocols).

Result: the gated window equals ceil_tick((contact mod cadence) + delay) in 49/49
gated configurations. Averaged over contact durations it matches the periodic
protocol's mean (0.200 s vs 0.200 s at 0.25 s cadence / 0.1 s delay).

Run from the v0.4.4 `pag-experiment` directory:

    python /path/to/dd6_window_measurement.py

Runtime about 90 s on 4 cores.
