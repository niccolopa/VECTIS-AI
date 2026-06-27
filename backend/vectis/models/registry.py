"""Model registry and model cards.

Trained models are persisted to disk as a self-describing bundle: the fitted
sklearn pipeline (``model.joblib``) plus a ``model_card.json`` documenting how
it was trained, on what data version, and how it scored. The model card ref is
threaded into every Decision Report for full provenance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from vectis.core.config import get_settings
from vectis.core.exceptions import ModelNotTrainedError


@dataclass
class ModelCard:
    """Documentation + provenance for a trained model."""

    model_name: str
    region: str
    dataset_version: str
    feature_names: list[str]
    metrics: dict[str, float]
    candidates: dict[str, dict[str, float]] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    seed: int = 42
    notes: str = ""

    @property
    def ref(self) -> str:
        """Short, stable reference id used in reports."""
        return f"{self.region}/{self.model_name}@{self.dataset_version}"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """Filesystem-backed store of trained models, one slot per region."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (get_settings().artifacts_dir / "models")

    def _dir(self, region: str) -> Path:
        return self.root / region

    def save(self, region: str, pipeline: Any, card: ModelCard) -> Path:
        d = self._dir(region)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, d / "model.joblib")
        (d / "model_card.json").write_text(json.dumps(card.as_dict(), indent=2))
        return d

    def exists(self, region: str) -> bool:
        return (self._dir(region) / "model.joblib").exists()

    def load(self, region: str) -> tuple[Any, ModelCard]:
        d = self._dir(region)
        if not (d / "model.joblib").exists():
            raise ModelNotTrainedError(
                f"No trained model for region '{region}'. Run `make train`."
            )
        pipeline = joblib.load(d / "model.joblib")
        card = ModelCard(**json.loads((d / "model_card.json").read_text()))
        return pipeline, card
