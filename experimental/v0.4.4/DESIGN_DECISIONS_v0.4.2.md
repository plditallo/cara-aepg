# CARA/AEPG v0.4.2 Experimental Design Decisions

## Status
Experimental. These changes are candidates for a future normative AEPG/CARA v0.4 specification; they are not novelty claims.

## DD-1 — Constraint-to-parameter binding
Grant constraints may bind to canonical-action parameters through issuer-controlled metadata: `binds_to`, `parameter_type`, and `unit`. The authorization engine evaluates the **commanded** parameter against the grant before authorization.

Binding metadata is authority semantics and MUST NOT change through delegation. Missing bound parameters, incompatible types, missing/incompatible units, or unresolved comparator semantics fail closed.

For physical effects, the signed receipt carries the authorized runtime envelope. The actuator-adjacent controller compares independently **measured** physical values against that envelope. Thus command authorization and runtime physical assurance are separate checks.

## DD-2 — Tier 3 revocation freshness and RELEASE
Receipt TTL alone is insufficient. A Tier 3 physical effect is released only when the actuator-adjacent enforcement boundary holds an authenticated revocation-epoch heartbeat no older than deployment parameter Δ.

Experimental Δ: **0.5 seconds**.

The receipt binds the revocation epoch observed at authorization. At RELEASE:
- invalid or missing heartbeat → deny;
- heartbeat age > Δ → deny;
- heartbeat epoch newer than receipt epoch → deny/re-authorize;
- otherwise continue with state/action/runtime-envelope checks.

`RELEASE` means permission for the physical effect to begin. `COMMIT` remains exclusively the durable AuthorityConsumption accounting transition after acknowledgment.

This is an application of complete mediation to a TOCTOU boundary, not a CARA novelty claim.

## DD-3 — Revocation during motion
Revocation terminates ordinary agent authority but does not imply an unconditional mechanical freeze. Control transfers to a trusted safe-state mechanism that selects a bounded recovery transition appropriate to the physical context. The simulator includes illustrative transitions only; it does not establish real-robot safety.

## DD-4 — Multi-grant consumption
Consumable authority remains implemented only for `SINGLE` AuthorityBasis. `ANY`, `ALL`, and `THRESHOLD` fail closed.

The unresolved question is an authority question: **who may select the grants whose budgets are consumed?** An agent-selected consumption set could deliberately exhaust a scarce human co-signer grant. Any future design must identify the allocation authority, prove the selected set independently satisfies the AuthorityBasis mode, and bind the selected set into the receipt.

## DD-5 — Research framing
Constraint binding, complete mediation, epoch freshness, and consumption allocation are specification/security engineering. They stay out of the novelty section.

The strongest implemented authority result remains: revocation of an upstream planner invalidates authority at a downstream physical arm that the planner did not directly command.
