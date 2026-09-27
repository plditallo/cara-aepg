# CARA/AEPG v0.4.4 Experimental Design Decisions

Supersedes v0.4.3 where they differ. Experimental; none of these items is asserted as a novelty contribution.

## DD-1 Constraint binding
Unchanged from v0.4.3. Commanded parameters are bound and checked by the authorization engine; measured values are checked independently at the actuator boundary. `binds_to`, type, unit, and comparator semantics are issuer-controlled and immutable through delegation. Missing or incompatible bindings are UNRESOLVED and fail closed.

## DD-2 Revocation freshness — corrected
Tier 3 release and continuation require authenticated revocation state no older than Δ and no revoked dependency in the receipt lineage. The revocation service and actuator are separate trust/clock domains; signed heartbeats traverse the simulated lossy network.

The v0.4.3 sweep supports the sharper interpretation:

> worst-case stale-authority exposure ≈ min(Δ, longest gap between delivered heartbeats) + one control tick.

Δ is a cap only when delivery gaps are long enough to reach it. Without long loss runs, the delivered-heartbeat gap controls exposure. Δ that is tighter than the network can reliably satisfy causes availability failure.

The previously described final-approach exposure is **residual exposure under periodic heartbeat mediation without an additional phase-bound freshness requirement**, not a proven irreducible lower bound.

## DD-3 Revocation during motion
Unchanged. Loss of authority or runtime-envelope violation transfers control to the perception-driven safe-state controller under standing safety authority; it does not mechanically freeze the arm or complete the interrupted task.

## DD-4 Multi-grant consumption
Unchanged. Consumable ANY/ALL/THRESHOLD authority remains fail-closed pending an authorized allocation model.

## DD-5 Research framing
Constraint binding, complete mediation, heartbeat freshness, safe-state transfer, and consumption allocation are specification/security engineering. They are not CARA novelty claims. Lease and bounded-staleness precedents must be cited when discussing temporal freshness.

## DD-6 Phase-bound freshness experiment
Implemented experimentally as a **clock-free sequence gate**.

At the transition into the contact phase, the actuator records the highest verified revocation-heartbeat sequence number seen. Contact is not admitted until the actuator receives a valid heartbeat with a strictly higher sequence number. No service timestamp is compared with actuator phase-start time.

The wait remains subject to ordinary Δ freshness and dependency-revocation checks. Missing/stale/revoking heartbeats therefore transfer to safe state rather than allowing contact.

The experiment compares periodic mediation with this sequence gate over the frozen v0.4.3 network axes (Δ, cadence, delay, loss) and adds contact duration = 0.1, 0.3, and 1.0 seconds. It measures effect-after-revocation, exposure, benign completion/availability stops, and pre-contact hesitation distribution.

This gate is expected to shrink, not eliminate, the residual window: revocation may still become effective after the qualifying heartbeat is issued and before contact/effect completion.
