"""Pipeline runner: composes the stages and produces a versioned result."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from vectis.core.logging import get_logger
from vectis.data.connectors.base import RawFrame
from vectis.data.pipeline import steps
from vectis.data.pipeline.schema import FEATURE_NAMES, LABEL

log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Output of a pipeline run: engineered features + provenance."""

    region_key: str
    features: pd.DataFrame
    source: str
    raw_hash: str
    feature_hash: str
    has_label: bool
    steps: list[dict[str, Any]] = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        """Stable version id combining raw + feature hashes."""
        return f"{self.raw_hash}.{self.feature_hash}"


def _hash_frame(df: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()[:16]


def run_pipeline(raw: RawFrame, *, require_label: bool = False) -> PipelineResult:
    """Run validate → clean → engineer, logging and timing each stage."""
    log_steps: list[dict[str, Any]] = []

    def _record(name: str, df: pd.DataFrame) -> None:
        log_steps.append({"step": name, "rows": len(df), "cols": df.shape[1]})
        log.info("pipeline.step", step=name, rows=len(df), cols=df.shape[1])

    validated = steps.validate(raw.frame, require_label=require_label)
    _record("validate", validated)

    cleaned = steps.clean(validated)
    _record("clean", cleaned)

    features = steps.engineer_features(cleaned)
    _record("feature_engineer", features)

    result = PipelineResult(
        region_key=raw.region.key,
        features=features,
        source=raw.source,
        raw_hash=raw.content_hash,
        feature_hash=_hash_frame(features[FEATURE_NAMES]),
        has_label=LABEL in features.columns,
        steps=log_steps,
    )
    log.info(
        "pipeline.complete",
        region=raw.region.key,
        version=result.dataset_version,
        n_cells=len(features),
    )
    return result
