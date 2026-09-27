# AEPG v0.2 → v0.3 Migration Guide

## Breaking schema changes
`AuthorityGrant` now requires `policy_version` and `security_dependencies`. Declared constraints require `comparator_id` and `comparator_version`. A new `EvaluationContext` schema formalizes trusted evaluation time, PEP, canonical action, resource, and deadline.

## Behavioral changes
1. Child comparator substitution is prohibited.
2. Child-only constraints fail closed unless registered as narrowing.
3. Complete ancestor chains are required.
4. Delegated grant issuer must be parent holder unless explicitly authorized otherwise.
5. Request subject must equal Activity actor.
6. Grant subject and PEP audience are enforced.
7. Subject and signing-key revocation are authority dependencies.
8. Policy, attestation-authority, and trust-relationship revocation can match schema-valid grant dependencies.
9. Side-effect classes use a registered ordered lattice.
10. Trusted evaluation time is explicit.

## Provisional rule mappings
- `AEPG-REF-GRANT-001` → `AEPG-AUTH-012`
- `AEPG-REF-GRANT-002` → `AEPG-AUTH-013`
- `AEPG-REF-GRANT-003` → `AEPG-AUTH-014`
- `AEPG-REF-LINEAGE` → `AEPG-AUTH-015`
- `AEPG-REF-TIME` → `AEPG-AUTH-014`
- `AEPG-REF-BIND-001` → `AEPG-BIND-001`
- `AEPG-REF-BIND-002` → `AEPG-BIND-002`
