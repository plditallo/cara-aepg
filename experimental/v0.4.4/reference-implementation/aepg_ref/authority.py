"""Per-grant usability and AuthorityBasis sufficiency (AEPG-AUTH-010/011)."""
from dataclasses import dataclass
from datetime import datetime
from .attenuation import prove_attenuation
from .models import ValidationFinding
from .revocation import LineageError, lineage, lineage_dependencies
from .timeutil import parse_ts


@dataclass(frozen=True)
class GrantContext:
    subject: str
    pep_id: str
    now: datetime
    action: str
    resource: str
    grants_by_id: dict
    revoked: set
    suspended: set
    registry: object
    side_effect_order: tuple
    max_lineage_depth: int


def _soft(rule, code, message, **details):
    # Per-grant problems are recorded as soft findings. Whether they deny the
    # request depends on the AuthorityBasis mode, evaluated afterwards.
    return ValidationFinding(rule, code, message, hard=False, details=details)


def grant_findings(grant, ctx: GrantContext):
    """Return every reason this grant cannot support the request. Empty = usable."""
    gid = grant["grant_id"]
    out = []

    if grant["subject"] != ctx.subject:
        out.append(_soft("AEPG-REF-GRANT-001", "GRANT_SUBJECT_MISMATCH",
                         "grant is held by a different subject", grant_id=gid,
                         grant_subject=grant["subject"], requester=ctx.subject))

    if ctx.pep_id not in grant["audience"]:
        out.append(_soft("AEPG-REF-GRANT-002", "PEP_AUDIENCE_MISMATCH",
                         "grant audience does not include this PEP", grant_id=gid, pep=ctx.pep_id))

    if ctx.action not in grant["actions"] or ctx.resource not in grant["resources"]:
        out.append(_soft("AEPG-AUTH-011", "GRANT_SCOPE_INSUFFICIENT",
                         "grant does not cover the bound action/resource", grant_id=gid,
                         action=ctx.action, resource=ctx.resource))

    try:
        chain = lineage(grant, ctx.grants_by_id, ctx.max_lineage_depth)
    except LineageError as exc:
        rule = "AEPG-GRAPH-001" if exc.code == "AUTHORIZATION_EVALUATION_BOUND_EXCEEDED" else "AEPG-REF-LINEAGE"
        out.append(_soft(rule, exc.code, str(exc), grant_id=gid))
        return out

    # Every grant on the path must be inside its validity window now.
    for g in chain:
        try:
            nb, exp = parse_ts(g["validity"]["not_before"]), parse_ts(g["validity"]["expires_at"])
        except ValueError as exc:
            out.append(_soft("AEPG-REF-GRANT-003", "VALIDITY_INDETERMINATE", str(exc), grant_id=g["grant_id"]))
            continue
        if ctx.now < nb:
            out.append(_soft("AEPG-REF-GRANT-003", "GRANT_NOT_YET_VALID",
                             "grant on lineage is not yet valid", grant_id=g["grant_id"]))
        if ctx.now >= exp:
            out.append(_soft("AEPG-REF-GRANT-003", "GRANT_EXPIRED",
                             "grant on lineage has expired", grant_id=g["grant_id"]))

    # Re-prove attenuation on every link. Issuance-time checks are not
    # trusted because this core does not yet verify signatures.
    for child, parent in zip(chain, chain[1:]):
        for f in prove_attenuation(child, parent, ctx.registry, ctx.side_effect_order):
            out.append(_soft(f.rule_id, f.code, f"link {child['grant_id']} -> {parent['grant_id']}: {f.message}",
                             grant_id=gid, **f.details))

    # Revocation is evaluated over the whole path, so revoking any ancestor
    # grant, its subject, issuer, root, or signing key invalidates the leaf.
    deps = lineage_dependencies(chain)
    hit_revoked = sorted(deps & ctx.revoked)
    hit_suspended = sorted(deps & ctx.suspended)
    if hit_revoked:
        out.append(_soft("AEPG-AUTH-010", "AUTHORITY_REVOKED",
                         "a dependency on this grant's lineage is revoked", grant_id=gid,
                         dependencies=[f"{t}:{i}" for t, i in hit_revoked]))
    if hit_suspended:
        out.append(_soft("AEPG-ROOT-002", "AUTHORITY_SUSPENDED",
                         "a dependency on this grant's lineage is suspended", grant_id=gid,
                         dependencies=[f"{t}:{i}" for t, i in hit_suspended]))
    return out


def evaluate_basis(basis, ctx: GrantContext):
    """Return (ok, usable_grants, findings)."""
    findings = []
    usable = []
    for gid in basis["grant_ids"]:
        grant = ctx.grants_by_id.get(gid)
        if grant is None:
            findings.append(_soft("AEPG-AUTH-011", "GRANT_NOT_FOUND", "named grant was not supplied", grant_id=gid))
            continue
        gf = grant_findings(grant, ctx)
        findings.extend(gf)
        if not gf:
            usable.append(grant)

    n_named, n_usable = len(basis["grant_ids"]), len(usable)
    mode = basis["mode"]
    threshold = basis.get("threshold")
    if mode == "SINGLE":
        ok = n_named == 1 and n_usable == 1
    elif mode == "ANY":
        ok = n_usable >= 1
    elif mode == "ALL":
        ok = n_usable == n_named
    elif mode == "THRESHOLD":
        valid_threshold = isinstance(threshold, int) and not isinstance(threshold, bool) and 1 <= threshold <= n_named
        if not valid_threshold:
            findings.append(ValidationFinding("AEPG-AUTH-011", "AUTHORITY_BASIS_INSUFFICIENT",
                                              "THRESHOLD mode requires an integer threshold between 1 and the number of grants",
                                              details={"threshold": threshold}))
        ok = valid_threshold and n_usable >= threshold
    else:
        ok = False

    if not ok:
        findings.append(ValidationFinding("AEPG-AUTH-011", "AUTHORITY_BASIS_INSUFFICIENT",
                                          f"{mode} AuthorityBasis is not satisfied",
                                          details={"usable_grants": [g["grant_id"] for g in usable],
                                                   "threshold": threshold}))
    return ok, usable, findings
