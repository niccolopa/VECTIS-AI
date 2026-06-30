"""Train and persist the climate-risk model for a region.

Pulls sample data through the pipeline, trains the baseline zoo, selects the
best model, and writes the artifact + model card to the registry.

Run: ``python -m vectis.scripts.train`` (or ``make train``).
"""

from __future__ import annotations

import sys

from vectis.core.logging import get_logger
from vectis.data.connectors import get_connector
from vectis.data.pipeline.runner import run_pipeline
from vectis.data.regions import get_region
from vectis.models.training import train
from vectis.scripts.generate_sample import generate

log = get_logger(__name__)


def train_region(region_key: str = "california") -> None:
    region = get_region(region_key)
    connector = get_connector("sample")
    try:
        raw = connector.fetch(region)
    except Exception:
        log.info("train.seeding_sample", region=region_key)
        generate(region)
        raw = connector.fetch(region)

    result = run_pipeline(raw, require_label=True)
    outcome = train(result)

    print(f"\nBest model: {outcome.best_name}  (ref: {outcome.card.ref})")
    print("Candidate metrics:")
    for name, metrics in outcome.all_metrics.items():
        m = metrics.as_dict()
        print(f"  {name:20s} roc_auc={m['roc_auc']:.3f}  pr_auc={m['pr_auc']:.3f}  "
              f"brier={m['brier']:.3f}  f1={m['f1']:.3f}")


def main() -> None:
    region = sys.argv[1] if len(sys.argv) > 1 else "california"
    train_region(region)


if __name__ == "__main__":
    main()
