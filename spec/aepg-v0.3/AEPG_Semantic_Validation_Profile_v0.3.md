# AEPG Semantic Validation Profile v0.3

**Parent:** AEPG Technical Specification v0.3  
**Supersedes:** v0.2

## New and normalized rules

### AEPG-AUTH-012 — Grant Subject Binding
Grants used for authorization MUST bind to the authorized subject.  
Failure: `GRANT_SUBJECT_MISMATCH`. Maps `AEPG-REF-GRANT-001`.

### AEPG-AUTH-013 — PEP Audience Applicability
Exercised authority MUST permit the target enforcement audience where audience is security-relevant.  
Failure: `PEP_AUDIENCE_MISMATCH`. Maps `AEPG-REF-GRANT-002`.

### AEPG-AUTH-014 — Grant Temporal Validity
Every exercised grant and required ancestor MUST be valid at trusted evaluation time.  
Failures: `GRANT_NOT_YET_VALID`, `GRANT_EXPIRED`, `VALIDITY_INDETERMINATE`. Maps `AEPG-REF-GRANT-003` and `AEPG-REF-TIME`.

### AEPG-AUTH-015 — Complete Authority Lineage
Every delegated grant MUST resolve through a complete, acyclic, bounded authenticated ancestor chain.  
Failures: `LINEAGE_UNRESOLVED`, `LINEAGE_CYCLE`, `LINEAGE_DEPTH_EXCEEDED`. Maps `AEPG-REF-LINEAGE`.

### AEPG-AUTH-016 — Delegating Issuer Is Parent Holder
A child grant MUST be issued by the parent subject unless an explicit alternative delegation mechanism applies.  
Failure: `DELEGATING_ISSUER_NOT_PARENT_HOLDER`.

### AEPG-AUTH-017 — Comparator Ownership
A child MUST NOT replace or version-shift the parent/registry comparator.  
Failure: `CONSTRAINT_COMPARATOR_CHANGED`.

### AEPG-AUTH-018 — New Constraint Introduction
A child-only constraint requires a registered proof that its introduction narrows authority.  
Failure: `NEW_CONSTRAINT_NOT_PROVEN_NARROWING`.

### AEPG-AUTH-019 — Side-Effect Monotonicity
Child side-effect class MUST be equivalent or lower under the registered lattice.  
Failures: `SIDE_EFFECT_CLASS_EXPANDED`, `SIDE_EFFECT_CLASS_UNRESOLVED`.

### AEPG-BIND-001 — Subject/Actor Congruence
AuthorizationRequest.subject MUST equal Activity.actor_id.  
Failure: `SUBJECT_ACTOR_MISMATCH`. Maps `AEPG-REF-BIND-001`.

### AEPG-BIND-002 — Basis/Request Grant Congruence
AuthorityBasis grants MUST be included in or validly resolved from request candidate grants.  
Failure: `BASIS_GRANT_NOT_REQUESTED`. Maps `AEPG-REF-BIND-002`.

### AEPG-BIND-003 — Canonical Action Object Integrity
Trusted canonical action MUST hash to the action hash bound by request and Activity.  
Failure: `CANONICAL_ACTION_HASH_MISMATCH`.

### AEPG-BIND-004 — Resource Congruence
Trusted resource identifier MUST equal the resource bound by the authorization transaction.  
Failure: `RESOURCE_BINDING_MISMATCH`.

### AEPG-REV-006 — Subject Revocation
Revoked/suspended subject invalidates authority issued to that subject and dependent descendants.  
Failure: `REVOKED_SUBJECT_AUTHORITY_USED`.

### AEPG-REV-007 — Signing-Key Revocation
Revoked/suspended signing key invalidates authority whose verified signature depends on it.  
Failure: `REVOKED_SIGNING_KEY_AUTHORITY_USED`.

### AEPG-REV-008 — Declared Dependency Revocation
Revoked policy, attestation authority, or trust relationship invalidates a grant declaring that dependency.  
Failure: `REVOKED_SECURITY_DEPENDENCY_USED`.

## Retained rules
All v0.2 LIFE, AUTH-001–011, ACT, PROV, DEC, FLOW, COMP, PHYS, REV-001–005, EVID, GRAPH, ROOT, FED, PIS, and CD rules remain applicable unless refined above.

## Evaluation order
Schema → lifecycle → signature/key → trusted time → subject/actor → complete lineage → temporal validity → dependency revocation → comparator integrity → attenuation → AuthorityBasis → action/resource/PEP/state → flow → composition → physical → bounded evaluation → decision → PEP → receipt → effect → acknowledgment/evidence.

## End of AEPG Semantic Validation Profile v0.3
