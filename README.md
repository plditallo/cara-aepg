# CARA / AEPG: External Authority Enforcement from Delegation to Physical Action

This repository holds the specifications, code, and data behind the working paper *External Authority Enforcement from Delegation to Physical Action: An Architecture and Simulation Study* (DiTallo, 2026). [SSRN link to be added]

CARA (Causal Authority and Runtime Accountability) is an architecture that keeps authorization, revocation, consumption, and evidence outside an AI agent. AEPG (the Authority–Execution–Provenance Graph) is its authority and provenance model. The experiments run a reference authorization engine and a deterministic simulator of a Physical Action Gateway at a robot arm's trust boundary.

**All physical results are from simulation.** Nothing here supports a claim about real-robot safety.

## Layout

| Folder | Contents | Cited in the paper as |
| --- | --- | --- |
| `spec/` | CARA Architecture Specification v0.3; AEPG v0.3 release (technical specification, semantic validation profile, schemas, registries, changelog, migration guide) | DiTallo (2026a, 2026b, 2026c) |
| `experimental/v0.4.4/` | The experimental branch that produced every result: `reference-implementation/`, `pag-experiment/`, `research/`, changelogs, design decisions, test reports | DiTallo (2026e) |
| `measurements/dd6-window-scan/` | The corrected DD-6 phase-start window measurement | Register rows D2 to D5 |
| `paper/` | Evidence and claims register | DiTallo (2026d) |

The v0.3 specifications are the normative baseline. The v0.4.4 branch adds experimental mechanisms (the revocation heartbeat, per-dependency revocation, the phase-start gate) that are not yet normative. No normative v0.4 has been released.

## Reading the evidence register

Every claim in the paper maps to a row in the evidence and claims register. The register's source notation maps onto this repository as follows:

| Register notation | Repository path |
| --- | --- |
| `v044:<path>` | `experimental/v0.4.4/<path>` |
| `v043:<path>` | Earlier branch; the cited tests are retained in `experimental/v0.4.4/reference-implementation/tests/` |
| `scan:<file>` | `measurements/dd6-window-scan/<file>` |

### Authority probes

The register cites probes by function name in `pag-experiment/probes.py`. `run_experiment.py` prints each result under a descriptive label instead:

| Register row | Function in `probes.py` | Label in `run_experiment.py` output |
| --- | --- | --- |
| A1 | `revoke_planner_mid_task` | `revoke_delegator_stops_arm` |
| A2 | `revocation_during_motion` | `revocation_during_motion_stops_before_effect` |
| A3 | `delegated_envelope` | `delegated_physical_envelope` |
| A4 | `delegation_cannot_widen` | `widened_delegation_unusable` |
| A5 | `signing_key_revocation_stops_arm` | `signing_key_revocation_stops_arm` |
| A6 | `unrelated_revocation_no_false_stop` | `unrelated_revocation_no_false_stop` |
| A7 | `forged_receipt` | `forged_receipt_refused` |
| A7 | `self_made_decision` | `unsigned_decision_refused` |
| A7 | `receipt_replay` | `receipt_replay_refused` |
| A7 | `receipt_for_other_motion` | `receipt_bound_to_motion` |
| A7 | `expired_receipt` | `expired_receipt_refused` |
| A8 | `toctou_stove_lit_after_authorization` | `state_change_after_authorization` |
| A10 | `budget_exhaustion` | `confirmed_budget_enforced` |
| A11 | `dropped_heartbeats_fail_safe` | `dropped_heartbeats_fail_safe` |
| A12 | `revocation_after_effect` | `revocation_after_effect_is_recorded` |

## Reproducing the results

See [REPRODUCE.md](REPRODUCE.md). On a clean Python 3.12 environment the full record reproduces in a few minutes: 207 tests, the hazard experiment and probes, the 54-configuration freshness sweep, and the DD-6 window scan.

## Withdrawn material

`experimental/v0.4.4/pag-experiment/dd6_sweep.py, dd6_sweep.csv, and dd6_sweep.json produced a DD-6 result that was later withdrawn because of a sampling error. They are kept for the audit trail and must not be cited. See [WITHDRAWN.md](experimental/v0.4.4/pag-experiment/WITHDRAWN.md).

## Versions

The tag `ssrn-2026-09` marks the exact state that matches the paper. Later commits may fix packaging or add experiments; they do not change the tagged record.

## Citing

Use the citation file in this repository (GitHub shows a "Cite this repository" button) or the Zenodo DOI for the tagged release. [DOI to be added]

## Disclosure

The code, analysis, and documentation were produced with substantial assistance from AI systems. The author directed the research and is responsible for all claims.

## License

[To be added: code license and documentation license]
