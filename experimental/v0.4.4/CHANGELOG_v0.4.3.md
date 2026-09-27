# CARA/AEPG v0.4.3 Experimental Branch: Changelog

Corrects the v0.4.2 mechanisms that were implemented in name but not in behavior. Each item has a test marked "v0.4.2 regression".

## Fixed

1. **Unbound constraints failed open.** `evaluate_bound_constraints` skipped any constraint without `binds_to`, so a 10 N grant authorized a 15 N command, reserved budget, and issued a receipt. Unbound constraints are now `UNBOUND_CONSTRAINT` and deny at the engine.
2. **Heartbeat age was always zero.** The gateway minted a heartbeat synchronously before every release. The revocation service is now a separate component on its own (optionally skewed) clock, reachable only through a `Network` with cadence, delay, jitter, and loss. Normal runs see heartbeat ages of 0 to cadence plus delay.
3. **Anything holding the epoch key could forge freshness.** Heartbeats and receipts are now Ed25519. The revocation service and the PEP hold private keys; the actuator holds only verifiers. A forged heartbeat is rejected and counted.
4. **Global epoch caused false stops.** Any revocation anywhere, including future-dated ones, stopped every arm. Heartbeats now carry the set of revoked authority dependencies effective at heartbeat time. Receipts carry their lineage's dependency set (grant, root, subject, issuer, signing key). Release proceeds only if the two sets do not intersect. Unrelated and not-yet-effective revocations no longer stop anything.
5. **"Measured" force was a pre-motion prediction.** Motions now execute over 50 ms control ticks. The world reports per-tick force and velocity (free-space and contact phases, object stiffness, arm calibration gain). The actuator checks measured force and velocity against the receipt's runtime envelope at every tick. The effect applies only if the final tick completes.
6. **Measured velocity limit was never read.** Now checked every tick.
7. **Revocation during motion was untestable.** The revocation-heartbeat check also runs every tick. A revocation mid-motion stops the arm before the effect.
8. **Safe-state context came from the caller.** `SafeStateController.select()` takes only the perception snapshot, the primitive, and the gripper position. It chooses from a fixed maneuver set (`RETRACT_TO_MOTION_START`, `UPRIGHT_AND_HOLD`, `HOLD_POSITION`, `STOP`) under its own standing authority. A pour is never completed.
9. **Stopped motions spent budget.** A motion that ended in safe state did not produce its effect, so its reservation is aborted and the budget released.
10. `.pytest_cache` directories removed from the archive.

## Removed

- `EpochAuthority`, the global epoch, and `revocation_epoch` on receipts and `Tier3PEP.authorize()`.
- `World.measured_force()`.

## Added

- `aepg_ref/signing.py`: Ed25519 `Signer` / `Verifier`.
- `aepg_ref/revocation_heartbeat.py`: `RevocationService`, `HeartbeatState`, `check_release`.
- `pag-experiment/delta_sweep.py`: the revocation-freshness experiment (see pag-experiment/README.md).
- New probes: revocation during motion, revocation after effect, unrelated revocation (no false stop), signing-key revocation, dropped heartbeats.

## Tests

- Reference implementation: 120 passed (was 101).
- PAG experiment: 82 passed (was 73).
- Mutation checks: reverting the per-tick revocation check, measured force, measured velocity, dependency intersection, effective-time filtering, the unbound-constraint denial, the perception-based safe-state rule, or budget release on stop each breaks 1 to 5 tests.
