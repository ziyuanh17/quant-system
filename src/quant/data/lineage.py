from pathlib import Path

from quant.models.ingestion import DatasetMetadata
from quant.models.validation import ValidationReport


def write_validation_report(
    report: ValidationReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n")
    return path


def write_dataset_metadata(
    metadata: DatasetMetadata,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(metadata.model_dump_json(indent=2) + "\n")
    return path
