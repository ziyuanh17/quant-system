from pathlib import Path

import pandas as pd

from quant.models.features import FeatureArtifactPaths


def write_feature_artifact(
    features: pd.DataFrame,
    output_dir: Path,
    symbol: str,
) -> FeatureArtifactPaths:
    """Write feature output as an artifact behind a tiny boundary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{symbol}.csv"

    # CSV is the first implementation; callers should depend on this function
    # rather than writing files directly so Parquet can be introduced later.
    features.to_csv(path, index=False)
    return FeatureArtifactPaths(features_path=str(path))
