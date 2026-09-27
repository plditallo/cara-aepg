# AEPG Technical Specification v0.3

**Authority–Execution–Provenance Graph for CARA**  
**Status:** Draft technical specification  
**Date:** September 27, 2026  
**Supersedes:** AEPG Technical Specification v0.2  
**Implementation evidence:** AEPG Reference Implementation v0.2, 74 passing tests.

## 1. Revision purpose

v0.3 incorporates defects discovered by executable and adversarial testing. It preserves the v0.2 architecture while closing semantic gaps in delegation, identity binding, lineage closure, dependency revocation, side-effect ordering, and comparator ownership.

## 2. Retained architecture

AEPG retains immutable signed authoritative facts, reconstructable mutable projections, Activity-centered provenance, AuthorityBasis, separation of provenance roots from authority roots, stateful authorization, bounded governance, prospective revocation, Tier 3 receipts, and local-policy supremacy.

## 3. Complete authority lineage

Every delegated grant used for Tier 2/3 authorization MUST resolve through a complete authenticated ancestor chain to a RootAuthority. A missing ancestor, cycle, configured-depth violation, invalid ancestor, expired ancestor, or revoked dependency makes the lineage unresolved. Unresolved Tier 2/3 lineage MUST fail closed.

A delegated grant MUST be issued by the authenticated subject/holder of its immediate parent unless a separately specified delegation mechanism explicitly permits another issuer.

## 4. Identity congruence

For a protected Activity:

```text
AuthorizationRequest.subject == Activity.actor_id
```

Every grant used by AuthorityBasis MUST authorize the relevant subject under the basis semantics. Scope alone is insufficient.

AuthorityBasis grants MUST be included in, or validly resolved from, the request's candidate grant set.

## 5. Comparator ownership

A child grant MUST NOT select, replace, or version-shift the comparator used to prove attenuation of an inherited constraint. Comparator semantics are controlled by the parent constraint or authoritative Constraint Registry.

```text
child.comparator_id      == parent.comparator_id
child.comparator_version == parent.comparator_version
```

unless a registered migration rule explicitly permits otherwise. Mismatch is `UNRESOLVED` and MUST deny delegation.

## 6. New child constraints

A child constraint absent from its parent MUST NOT automatically be treated as narrowing. It is valid only if the Constraint Registry defines introduction of that constraint as intrinsically narrowing or a registered proof establishes attenuation. Otherwise delegation MUST fail closed.

## 7. Side-effect lattice

`side_effect_class` is an authority constraint. The baseline ordered registry is:

```text
read_only < ephemeral < persistent < external < privileged < physical < irreversible
```

A child MUST NOT move upward. Unknown classes are `UNRESOLVED` and fail closed. Deployments MAY register a different versioned lattice.

## 8. Explicit security dependencies

AuthorityGrant MUST identify `policy_version` and MAY/SHOULD identify additional security dependencies. v0.3 schema supports:

```yaml
security_dependencies:
  - type: key
    id: key-issuer-17
  - type: policy
    id: policy-v7
  - type: attestation_authority
    id: attestor-prod-2
  - type: trust_relationship
    id: federation-partner-A
```

The verified signing key is an implied security dependency whether or not redundantly declared.

## 9. Revocation targets

Revocation evaluation MUST support grant, root, subject, issuer, key, policy, attestation authority, trust relationship, credential, and session where applicable.

Revoking a subject invalidates grants whose subject is that identity and descendant authority depending upon them.

Revoking a signing key invalidates grants whose verified signatures depend on that key, subject to authenticated recovery/reissuance.

## 10. Revocation-relative independence

Different grant IDs do not establish independence. A surviving path is independent only if it avoids every dependency invalidated by the relevant revocation cause.

## 11. Trusted evaluation context

Security-critical action/resource semantics MUST come from the authorization transaction, not mutable convenience fields in policy.

The evaluator receives trusted context containing: trusted evaluation time, exact PEP identifier, canonical action object and hash, resource identifier, and authorization deadline.

The canonical action object's hash MUST equal the hashes bound by the AuthorizationRequest and Activity.

## 12. Time

Grant/ancestor validity, decision validity, revocation effectiveness, and replay windows MUST use an authenticated/trusted evaluation time. Required but indeterminate time fails closed for Tier 3.

## 13. AuthorityBasis sufficiency

Sufficiency requires named grants to resolve; complete lineage; subject binding; temporal validity; current security dependencies; scope coverage; and authority roots supported by actual valid grant paths. Provenance roots never satisfy authority merely by contributing information.

## 14. Tier 3 binding

Tier 3 ALLOW MUST bind subject, PEP audience, AuthorityBasis, canonical action, resource, request hash, state hash, policy version, revocation snapshot, required attestation, validity interval, nonce, and decision ID.

## 15. Added security properties

**SP-17 Comparator Integrity:** a delegate cannot choose the semantics used to judge its own attenuation.

**SP-18 Lineage Closure:** protected authorization cannot rely on unresolved, cyclic, missing, expired, or invalid ancestry.

**SP-19 Identity Congruence:** request subject, Activity actor, and grant-subject relationships are explicitly validated.

**SP-20 Dependency Revocation:** revocation of a declared or cryptographically implied security dependency invalidates dependent authority.

**SP-21 Side-Effect Monotonicity:** delegation cannot increase the registered consequence class.

## 16. Test requirements

Conformance suites SHOULD include positive and negative controls for subject/actor mismatch, grant subject mismatch, PEP audience mismatch, basis/request grant mismatch, missing/cyclic/expired ancestors, revoked parent/root/subject/issuer/key, comparator substitution/version change, side-effect escalation/unknown class, new unregistered child constraints, action/resource/state binding, all AuthorityBasis modes, and bounded-evaluation failure.

Positive controls SHOULD accompany attack tests so an implementation that simply denies every request cannot pass.

## End of AEPG Technical Specification v0.3
