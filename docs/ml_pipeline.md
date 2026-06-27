# The ML Pipeline & Explainable AI

VECTIS's machine-learning layer turns validated features into a calibrated,
**explainable** risk score. Every prediction can answer *"why did the model decide
this?"* — explainability is a structural requirement, not an afterthought.

```
Raw Data → Validation → Feature Engineering → Training → Evaluation → Explainability → Decision Layer
└──────────── data pipeline (docs/data_pipeline.md) ─────────────┘   └──── this document ────┘
```

Code lives in `backend/vectis/models/`:

| Concern | Module |
|---|---|
| Baselines + selection | `training.py` |
| Metrics | `evaluation.py` |
| Explainability (SHAP) | `explain.py` |
| Model registry + model cards | `registry.py` |
| Prediction + driver attribution | `predictor.py` |

(Feature definitions — the single source of truth — live in
`backend/vectis/data/pipeline/schema.py`; see [`data_pipeline.md`](data_pipeline.md).)

## Baseline models

Three baselines are trained and compared, each wrapped in a `StandardScaler`
pipeline (well-conditions the linear model; keeps SHAP on a consistent space):

- **Logistic Regression** — calibrated, interpretable linear baseline.
- **Random Forest** — non-linear, robust to feature scaling and interactions.
- **XGBoost** — gradient-boosted trees, strong tabular performance.

**Why compare rather than pick one?** Different datasets favor different models. VECTIS
selects empirically by a composite of discrimination and calibration
(`Metrics.selection_score = ROC-AUC − 0.5·Brier`) — calibration matters because the
risk score *is* a probability. The choice, the runner-up scores, and the rationale are
written into the **model card** and surfaced by the ML Research agent, so model
selection is auditable. (On the bundled Liguria sample, Logistic Regression currently
wins at ROC-AUC ≈ 0.91.)

## Evaluation

`evaluate(y_true, y_prob)` returns a `Metrics` record with:

- **Classification:** accuracy, precision, recall, F1
- **Discrimination:** ROC-AUC, PR-AUC
- **Calibration:** Brier score

Metrics degrade gracefully (NaN, not error) when only one class is present.

## Model registry & model cards

`ModelRegistry` persists the selected pipeline (`model.joblib`) plus a
`model_card.json` documenting: model name, dataset version
(`raw_hash.feature_hash`), feature names, the winner's metrics, **all candidate
metrics**, seed, and the selection rationale. The card's `ref`
(`region/model@dataset_version`) is threaded into every Decision Report for full
provenance — you can always trace a score back to exactly how its model was made.

## Explainable AI (SHAP)

`ShapExplainer` (`explain.py`) wraps the fitted pipeline and produces per-cell,
per-feature SHAP attributions, normalized to the positive ("fire") class in log-odds
space. `RiskPredictor` turns these into ranked, plain-language **drivers** on each
prediction (and aggregated for the region), e.g. *"drought conditions — increases
(SHAP +0.77)"*. These drivers are the evidence the Report agent cites and the Critic
verifies, closing the loop from model to explanation to decision.

> Note: region-level drivers are ranked by mean |SHAP|; a high-magnitude feature with
> mixed sign across cells can appear as net-protective — this is honest, not a bug.

## How the agents use this layer

The **ML Research agent** loads the selected model, predicts, attaches SHAP drivers, and
reports the model comparison/rationale. The **Report agent** turns drivers into cited
evidence; the **Critic** blocks any driver claim lacking evidence. See
[`agents.md`](agents.md).

## Extending

- **A new model** → add a candidate pipeline in `training._candidates`; it's compared
  and selectable automatically. Keep it a `StandardScaler`+estimator pipeline so SHAP
  and the registry work unchanged.
- **A new metric** → add a field to `Metrics` + compute it in `evaluate`; it flows into
  model cards automatically.
- **A new explainer** → conform to `ShapExplainer`'s `attribute(X) -> (n, n_features)`
  contract.
