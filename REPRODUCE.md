# Reproducing the results

These steps rerun every test and every script that produced a number in the paper. They were last run on Windows with Python 3.12 in a clean virtual environment, and every reported value reproduced. The regenerated result files matched the archived files exactly.

Runtime: under five minutes in total.

## 1. Set up the environment

Requires Python 3.10 or later. From the repository root:

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest "jsonschema>=4.18" "referencing>=0.30" "cryptography>=42"
```

**macOS or Linux**

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install pytest "jsonschema>=4.18" "referencing>=0.30" "cryptography>=42"
```

For the exact package versions used in the last reproduction, install from `requirements-lock.txt` instead.

The reference implementation is run in place rather than installed. (At the tagged version its `pyproject.toml` cannot be installed as-is; this is fixed in a later packaging commit and does not affect behavior.)

The commands below use Windows paths. On macOS or Linux, replace `..\..\..\.venv\Scripts\python.exe` with `../../../.venv/bin/python`, use forward slashes, and set the path variable with `export PYTHONPATH=...` using `:` as the separator.

## 2. Run the test suites

```powershell
cd experimental\v0.4.4\reference-implementation
..\..\..\.venv\Scripts\python.exe -m pytest -q
```

Expected: `120 passed`.

```powershell
cd ..\pag-experiment
$env:PYTHONPATH = "..\reference-implementation"
..\..\..\.venv\Scripts\python.exe -m pytest -q
```

Expected: `87 passed`.

## 3. Hazard experiment and authority probes

From `experimental\v0.4.4\pag-experiment`, with `PYTHONPATH` set as above:

```powershell
..\..\..\.venv\Scripts\python.exe run_experiment.py
```

Writes `results.json`. Expected values (paper Tables 2 and 3):

| Gate | RoboHarm | Relabeled | Reversed order | Author-held-out | Benign completed |
| --- | --- | --- | --- | --- | --- |
| No gate | 5/5 harmed | 5/5 | 1/1 | 2/2 | 7/7 |
| Label gate | 4/5 | 5/5 | 1/1 | 2/2 | 7/7 |
| CARA PAG | 0/5 | 0/5 | 0/1 | 2/2 | 7/7 |

Also expected: `label_validation` 20/20, `cara_evidence_chains_valid` 20/20, and all 15 authority probes with `"pass": true`.

## 4. Revocation freshness sweep

```powershell
..\..\..\.venv\Scripts\python.exe delta_sweep.py
```

54 configurations × 40 seeds, about 45 seconds. Writes `delta_sweep.csv` and `delta_sweep.json`. Values that define the paper's findings (Table 4):

| Δ | Cadence | Delay | Loss | Expected |
| --- | --- | --- | --- | --- |
| any | 0.05 | 0.02 | 0 | mean exposure 0.076 s |
| 1.0 | 0.25 | 0.1 | 0 | mean exposure 0.281 s |
| 0.25, 0.5, 1.0 | 0.05 | 0.02 | 0.1 | max exposure 0.248 s for all three |
| 0.5 | 0.25 | 0.02 or 0.1 | 0.1 or 0.3 | max exposure 0.547 s |
| 1.0 | 0.25 | 0.02 or 0.1 | 0.3 | max exposure 0.993 s |
| 0.25 | 0.25 | 0.1 | 0 / 0.1 / 0.3 | stopped 1.0 / 0.85 / 0.6; refused 0 / 0.15 / 0.4 |

## 5. DD-6 phase-start window scan

From `experimental\v0.4.4\pag-experiment`:

```powershell
$env:PYTHONPATH = ".;..\reference-implementation"
..\..\..\.venv\Scripts\python.exe ..\..\..\measurements\dd6-window-scan\dd6_window_measurement.py
```

About 90 seconds. Expected (Table 5): on the 0.25 s cadence / 0.1 s delay network, periodic mean 0.200 s, gated mean 0.200 s, hesitation 0.150 s; on the 0.1 s / 0.02 s network, periodic mean 0.075 s, gated mean 0.057 s (0.050 s for six contact durations, 0.100 s for 1.15 s), hesitation 0.075 s. Every gated value matches its `predicted` value.

## 6. Confirm nothing changed

From the repository root:

```powershell
git status
```

Expected: `nothing to commit, working tree clean`. The scripts rewrite their result files; a clean tree means the rewritten files are identical to the committed record.

Do not run `dd6_sweep.py`. It produces the withdrawn result described in `experimental/v0.4.4/pag-experiment/WITHDRAWN.md`.
