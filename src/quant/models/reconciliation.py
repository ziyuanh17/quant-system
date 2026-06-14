"""Define domain models for provider reconciliation results."""

from quant.models.base import FrozenModel
from quant.models.validation import ValidationIssue, ValidationSeverity


class ReconciliationDifference(FrozenModel):
    """Single field-level difference between two provider datasets."""

    date: str
    field: str
    left_value: float
    right_value: float
    absolute_difference: float
    relative_difference: float | None = None


class ProviderReconciliationReport(FrozenModel):
    """Audit report for comparing normalized data from two providers."""

    left_dataset: str
    right_dataset: str
    symbol: str
    left_rows: int
    right_rows: int
    overlap_rows: int
    left_only_dates: tuple[str, ...]
    right_only_dates: tuple[str, ...]
    close_differences: tuple[ReconciliationDifference, ...]
    volume_differences: tuple[ReconciliationDifference, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(
            issue.severity == ValidationSeverity.ERROR
            for issue in self.issues
        )

    @property
    def issue_count(self) -> int:
        return len(self.issues)
