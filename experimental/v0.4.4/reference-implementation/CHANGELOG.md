# Changelog

## 0.4.1.dev0 (2026-09-27, experimental branch)

### AuthorityConsumption rewritten

Each of these was exploitable against the v0.4 experimental ledger. Each has a test in `tests/test_authority_consumption.py` marked "v0.4 regression".

1. **Concurrent semantic replay.** The semantic key was claimed only at commit, and `commit()` never checked it, so two in-flight records for the same authority both committed. Budget is now reserved at prepare, counting in-flight units.
2. **Budgets above 1 were dead.** A record went to COMMITTED after one use with no path back. Budget now lives on an `AuthoritySlot` and each use is a separate `Reservation`.
3. **Agent-minted confirmations.** `confirmation_hash` was any string, so a new string meant new authority. Confirmations are now MAC-verified by a `ConfirmationAuthority` whose key the agent never holds, and each opens exactly one slot.
4. **Revocation was a caller boolean.** `commit()` now requires a `reauthorize()` callable. The PEP backs it with a fresh engine evaluation, and any exception fails closed.
5. **Unknown ids raised `KeyError`.** They now raise `ConsumptionError`.

Also added: idempotent commit, abort that releases the unit, and snapshot/restore to test crash recovery between prepare and commit.

### New modules

- `receipts.py`: signed pre-action receipts (HMAC reference; production needs asymmetric keys).
- `evidence.py`: hash-chained append-only evidence log with verification that detects edits, deletions, and reordering.
- `pep.py`: `Tier3PEP` tying engine, ledger, receipts, and evidence together, including `EFFECT_AFTER_AUTHORITY_LOSS` when revocation lands between receipt and commit.

### Known gaps

- Tier 3 consumption requires a SINGLE AuthorityBasis. Which grant's budget an ANY/ALL/THRESHOLD basis should spend is undefined, so those fail closed.
- The engine does not evaluate grant constraint values against request parameters. The PAG experiment enforces the physical envelope itself. A general constraint-to-parameter binding belongs in the engine and the spec.

## 0.2.0 (2026-09-27)

### Security fixes

Each of these returned ALLOW or accepted a delegation under 0.1.0. Each has a regression test in `tests/test_adversarial.py` (marked "v0.1 regression").

1. **Subject not bound.** A grant issued to one agent authorized a different agent. The request subject was also never compared with the Activity actor.
2. **Validity not checked at authorization.** A grant expired in 2020 still produced ALLOW. Timestamps were also compared as strings, so values with UTC offsets compared incorrectly.
3. **No descendant invalidation.** Revoking a parent grant left its children usable, because revocation only looked at the leaf grant's own fields.
4. **Subject revocation ignored.** Revoking an agent (`target_type: "subject"`) had no effect.
5. **Constraints could be dropped.** Attenuation iterated the child's constraints, so a child that omitted the parent's budget constraint passed.
6. **Child chose its comparator.** A child could compare its budget with `numeric-min` against a parent's `numeric-max` and pass with a larger value.
7. **Side-effect class not attenuated.** A child could escalate from `persistent` to `irreversible`.
8. **Audience not checked.** A grant scoped to one PEP was accepted at another.
9. **Action hash not tied to the checked action.** The action and resource checked against grants came from the caller's `policy` dict; the request and Activity hashes only had to match each other.
10. **Grants and revocations not schema-validated.** Unsigned grants were accepted; malformed revocation records were silently ignored.

### Behaviour changes

- `authorize()` now requires keyword arguments `action` (the canonical action object) and `pep_id`, and accepts `now`. `policy["action_name"]` and `policy["resource_name"]` are no longer read.
- `grants` must contain every ancestor of a named grant. A missing ancestor is DENY (`LINEAGE_UNRESOLVED`).
- A delegated grant must be issued by the subject of its parent, stay under the parent's root, and name the parent in `parent_grant_id`.
- A parent with `remaining_depth: 0` can no longer delegate (0.1.0 accepted a depth-0 child).
- `ANY` and `THRESHOLD` count only fully usable grants. 0.1.0 denied an `ANY` basis if any named grant lacked scope, even when another covered the request.
- `THRESHOLD` requires an integer threshold between 1 and the number of named grants.
- Grant signing `key_id` is now a revocation dependency, so revoking a key invalidates every grant it signed.
- Per-grant problems are reported as soft findings; the hard finding is the basis-level result. This keeps `ANY`/`THRESHOLD` correct while still explaining every denial.

### Finding identifiers

New checks without a matching rule in the v0.2 Semantic Validation Profile use provisional `AEPG-REF-*` rule IDs. They should be mapped to the v0.1 `AUTH-001..008` rules (not included in the current archive) or given new profile rules.

### Known gaps (spec-level, not fixed here)

- The grant schema has no field for policy version or other security dependencies, so revocation by `policy`, `attestation_authority`, or `trust_relationship` cannot match any grant. 0.1.0 read a `security_dependencies` field that `additionalProperties: false` forbids.
- The grant schema has no rate-limit, aggregate-budget, or state-precondition fields. Specification section 9 requires them to attenuate. They can be expressed as registered constraints, which are now attenuated correctly.
- A constraint type present on a child but absent on the parent is rejected. That is conservative; if constraint types are always restrictive, adding one should count as narrowing. The spec should say which.
- Side-effect class ordering is a default in `comparators.py`. The spec should register it.
- Without signature verification, a forged root grant is indistinguishable from a real one.
