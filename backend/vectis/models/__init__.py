"""Machine-learning layer: training, evaluation, explainability, registry, prediction.

Every prediction is accompanied by SHAP-based driver attributions so the system
can always answer "why did the model decide this?".
"""

from vectis.models.predictor import RiskPredictor
from vectis.models.registry import ModelCard, ModelRegistry

__all__ = ["RiskPredictor", "ModelRegistry", "ModelCard"]
