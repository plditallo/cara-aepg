# Withdrawn: dd6_sweep.py, dd6_sweep.csv, and dd6_sweep.json

**Do not cite results from these three files.**

The first DD-6 sweep reported effects after revocation falling from 2.7% without the phase-start gate to between 0.2% and 0.5% with it. That result is withdrawn (evidence register row D1).

The sweep drew revocation times over the ungated motion's duration. The phase-start gate lengthens motions by 0.05 to 0.15 s, so the gated motions' vulnerable tails were never sampled, and the gate looked far more effective than it is.

The corrected measurement is in `measurements/dd6-window-scan/`. It scans revocation time across each protocol's actual motion duration and finds that the gate makes the residual window predictable but does not reduce its average size (0.200 s with and without the gate on the slower network).

All three files stay in place, unmodified, because register row D1 cites them as the source of the withdrawn result. Keeping them lets anyone check the error.
