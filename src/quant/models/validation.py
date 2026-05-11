from enum import StrEnum

from quant.models.base import FrozenModel


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(FrozenModel):
    code: str
    severity: ValidationSeverity
    message: str
    row: int | None = None
    field: str | None = None


class ValidationReport(FrozenModel):
    dataset: str
    symbol: str
    rows: int
    passed: bool
    issues: tuple[ValidationIssue, ...]

    @property
    def issue_count(self) -> int:
        return len(self.issues)
