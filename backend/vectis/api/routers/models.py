"""Models resource — expose the trained model card for a region.

Surfaces full provenance (which model, on what data version, with what metrics)
so consumers can audit the basis of any prediction.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vectis.core.exceptions import ModelNotTrainedError
from vectis.models.registry import ModelRegistry

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("/{region}")
def get_model_card(region: str) -> dict:
    try:
        _, card = ModelRegistry().load(region)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return card.as_dict()
