# CARA/AEPG v0.4.3 Experimental Design Decisions

Supersedes DESIGN_DECISIONS_v0.4.2.md where they differ. Experimental; not novelty claims.

## DD-1: Constraint-to-parameter binding (revised)
Unchanged from v0.4.2, plus: **a constraint without `binds_to` cannot authorize anything.** An engine that cannot bind a constraint to the action cannot enforce it, so it fails closed (`UNBOUND_CONSTRAINT`). A future constraint-type registry may declare default bindings; until then every constraint must carry one.

Commanded parameters are checked by the engine before authorization. Measured values are checked by the actuator at every control tick during motion. These are different checks on different numbers.

## DD-2: Revocation freshness (revised)
A Tier 3 effect is released, and continues, only while the actuator-adjacent boundary holds a verified heartbeat no older than Δ whose revoked-dependency set does not intersect the receipt's authority dependencies.

- The revocation service alone holds the heartbeat signing key (asymmetric). Enforcement points hold only the public key.
- Revocation state is **per dependency** (grant, root, subject, issuer, signing key), not a global epoch. Only revocations effective at heartbeat time are listed.
- The check runs at release and at every control tick.

**Measured result (pag-experiment/delta_sweep.py):** typical stale-authority exposure is about half the heartbeat cadence plus the delay. With no loss, worst-case exposure is about cadence + delay + one tick. **Under loss, worst-case exposure approaches Δ**, because the arm legitimately continues on the last good heartbeat until it expires. So:

- **Δ is the worst-case exposure bound**, and should be chosen as such.
- Δ must exceed cadence + delay with margin for the number of consecutive losses to tolerate, or availability collapses (Δ = 0.25 s with 0.25 s cadence and 0.1 s delay stopped 100% of benign runs).
- A revocation landing within roughly the last cadence + delay of a motion does not stop the effect. Across this sweep that happened in 0 to 12.5% of revoked runs, tracking (cadence + delay) / motion duration. This is the irreducible exposure of heartbeat-based mediation; the only levers are faster cadence, lower delay, or a pre-contact freshness gate (below).

Candidate normative text: *A Tier 3 enforcement point MUST NOT release or continue a physical effect unless it holds authenticated revocation state no older than Δ that does not revoke any dependency of the authorizing lineage. Deployments MUST declare Δ, heartbeat cadence, and maximum tolerated consecutive heartbeat loss, and MUST treat Δ as the worst-case stale-authority exposure.*

## DD-3: Revocation during motion (revised)
Revocation, a stale heartbeat, or an envelope violation mid-motion transfers control to a safe-state controller that acts under its own standing authority, not the revoked grant. It selects from a fixed, pre-verified maneuver set using the actuator's own perception. It never completes the interrupted task. The effect is not applied, the reservation is aborted, and budget is released.

## DD-4: Multi-grant consumption
Unchanged. ANY/ALL/THRESHOLD fail closed.

## DD-5: Research framing
Unchanged. Everything in this branch is security and specification engineering.

## DD-6: Open question raised by the sweep
**Pre-contact freshness gate.** Most of the residual exposure comes from revocations that land during the final approach. A rule requiring a heartbeat issued after the start of the contact phase (not merely within Δ) before contact begins would move the stop point before contact in most cases, at the cost of occasional hesitation before contact. Worth testing before proposing.
