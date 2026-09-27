from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ValidationFinding:
    rule_id: str
    code: str
    message: str
    hard: bool = True
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DecisionResult:
    decision: str
    findings: tuple[ValidationFinding, ...]
    authority_basis: dict | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"
