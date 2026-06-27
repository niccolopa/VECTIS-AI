"""Domain exceptions.

A small, explicit hierarchy so the API layer can map failures to meaningful
HTTP responses without leaking internals.
"""

from __future__ import annotations


class VectisError(Exception):
    """Base class for all VECTIS domain errors."""

    status_code: int = 500
    code: str = "vectis_error"


class RegionNotFoundError(VectisError):
    status_code = 404
    code = "region_not_found"


class DataValidationError(VectisError):
    """Raised when raw or processed data fails validation."""

    status_code = 422
    code = "data_validation_error"


class ModelNotTrainedError(VectisError):
    """Raised when a prediction is requested but no model artifact exists."""

    status_code = 409
    code = "model_not_trained"


class AgentError(VectisError):
    """Raised when an agent cannot complete its step."""

    status_code = 500
    code = "agent_error"


class LLMProviderError(VectisError):
    status_code = 502
    code = "llm_provider_error"
