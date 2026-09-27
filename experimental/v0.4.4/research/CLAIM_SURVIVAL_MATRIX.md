# CARA Prior-Art Claim Survival Matrix — v0.4.2 Experimental Branch

| CARA/AEPG concept | Closest prior art identified | Current treatment |
|---|---|---|
| Authorization structure vs execution/provenance | AuthGraph | Established prior art; not a CARA novelty claim |
| Authenticated/scoped agent delegation | South et al. | Established prior art |
| Recursive delegation and attenuation | Overlaying Governance | Established prior art, including formal attenuation |
| Untrusted-model external authorization | CaMeL; Progent; Delegation Without Trust; AIDP | Established prior art |
| Multi-agent/sub-agent confinement and revocation propagation | Delegation Without Trust; AIDP | Strong prior art; no broad CARA novelty claim |
| Revocation-sensitive authorization history | ResidualAuth | Established/formalized |
| Durable authorization consumption / semantic replay | CapLease | Established; AuthorityConsumption is an integration requirement |
| Cross-domain constrained/revocable delegation | AIDP | Standards-track prior art |
| Physical hazard gating | RoboGuard and related robot-safety work | Established prior-art territory; hazard gating itself is not claimed |
| Constraint-to-parameter binding | Authorization engineering | Specification hygiene, not contribution |
| Effect-time revocation freshness / complete mediation | Complete mediation + TOCTOU security engineering | Specification hygiene, not contribution |
| Unified authority lineage reaching a downstream physical enforcement boundary | No direct matching result established in this review | **Provisional research question only** |
| Upstream revocation invalidating downstream actuator authority | Implemented in v0.4.1/v0.4.2 simulation | Experimental result; not by itself a novelty claim |
| Same authority model spanning delegation, consumption, release, evidence and physical safe-state transfer | No direct matching system established in this review | **Provisional integration question; search continues** |

“Provisional” means only that this review has not established direct prior art. It is not a claim of novelty.

## Evaluation discipline
Hazard-policy completeness and authority-enforcement correctness are scored separately. The author-written hazard suite cannot establish general physical safety. Externally authored held-out hazards are required before making generalization claims.
