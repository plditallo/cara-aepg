# CHANGELOG — AEPG v0.3

## v0.3 — September 27, 2026
Specification revision driven by AEPG Reference Implementation v0.2 adversarial testing, with 74 passing tests.

### Formalized security fixes
- Parent/registry owns comparator semantics.
- Subject revocation invalidates subject-bound authority.
- AuthorizationRequest subject is bound to Activity actor.
- Grant signing key is a revocation dependency.
- Complete ancestor lineage is required.
- Delegated issuer must be parent holder unless explicitly authorized otherwise.
- Side-effect attenuation uses a registered ordered lattice.
- Child-only constraint introduction requires registered narrowing semantics.
- Grant subject and PEP audience are normative checks.
- Trusted evaluation time/action/resource/PEP context is explicit.

### Schema fixes
- Added `policy_version` and `security_dependencies` to AuthorityGrant.
- Made comparator ID/version mandatory for declared constraints.
- Added EvaluationContext.
- Added Constraint Registry and Side-Effect Class Registry.

### Rule normalization
Provisional `AEPG-REF-*` findings are mapped to normative AUTH/BIND rules in Semantic Validation Profile v0.3.
