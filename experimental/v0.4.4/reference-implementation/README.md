# AEPG Reference Implementation v0.4.1.dev0 (experimental)

A deliberately small executable reference core for **AEPG Technical Specification v0.2**.

## Implemented

- Draft 2020-12 schema validation of every decision input: request, Activity, AuthorityBasis, each grant, and each revocation record.
- Deterministic canonical JSON hashing, with the request and Activity bound to the hash of the actual canonical action object.
- Per-grant usability: subject binding, PEP audience binding, action/resource scope, validity window at a trusted evaluation time.
- Full lineage evaluation: every ancestor is resolved, its validity checked, and attenuation re-proven on every link at authorization time.
- Descendant invalidation: revoking any grant, root, subject, issuer, or signing key on a lineage invalidates the leaf.
- REVOKE / SUSPEND / RESUME semantics, effective-time ordering, and REVOKE that RESUME cannot undo.
- Constraint attenuation driven by the parent's constraints and the parent's comparator.
- Ordered side-effect classes and delegation-rights attenuation.
- `SINGLE`, `ANY`, `ALL`, and `THRESHOLD` AuthorityBasis evaluation over usable grants only.
- Provenance-root / authority-root separation.
- State-hash binding, critical PolicyInformationSource presence, bounded lineage depth.

## Experimental (v0.4.1)

- `consumption.py`: durable AuthorityConsumption after CapLease (confirmed budgets, prepare/commit/abort, idempotent commit, crash recovery).
- `pep.py`, `receipts.py`, `evidence.py`: Tier 3 PEP with signed receipts and a hash-chained evidence log.

## Deliberately not implemented yet

This is not production security software. It does not implement cryptographic signature verification, durable (on-disk) storage for the consumption ledger, key lifecycle, attestation verification, persistent VPL/Merkle evidence, network PEP adapters, distributed revocation propagation, a policy language, full composition semantics, or physical PAG control.

Because signatures are not verified, a caller can still supply a forged grant that is internally consistent. Re-proving attenuation at authorization time limits what a forged *child* can claim, but nothing here detects a forged *root* grant. See "Known gaps" in CHANGELOG.md.

## API

```python
engine.authorize(request, activity, basis, grants, revocations, policy, current_state,
                 action=canonical_action, pep_id="pep-db", now="2026-09-27T18:00:00Z")
```

`grants` must include every ancestor of every grant the basis names. `now` defaults to the system clock and is never read from the request.

## Run

```bash
python -m pip install -e .[test]
pytest -q
python examples/demo.py
```

## Security rule

Schema validity is not authorization. Every check fails closed: missing ancestors, unparseable timestamps, unknown comparators, unknown side-effect classes, and malformed revocation records all produce DENY.
