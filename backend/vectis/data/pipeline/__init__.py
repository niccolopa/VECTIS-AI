"""The VECTIS data pipeline.

Raw data → validation → cleaning → feature engineering, with each stage logged
and the resulting dataset content-hashed for reproducibility/versioning.
"""

from vectis.data.pipeline.runner import PipelineResult, run_pipeline
from vectis.data.pipeline.schema import LABEL, MODEL_FEATURES, RAW_COLUMNS, FeatureSpec

__all__ = [
    "run_pipeline",
    "PipelineResult",
    "FeatureSpec",
    "MODEL_FEATURES",
    "RAW_COLUMNS",
    "LABEL",
]
