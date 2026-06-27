# `data/` — data staging & lineage

This directory holds **data on disk** at each stage of the VECTIS pipeline. The
*logic* that moves data between stages lives in code
(`backend/vectis/data/pipeline/`); these folders are where artifacts land, so
runs are inspectable and reproducible.

```
Raw Data → Validation → Cleaning → Feature Engineering → ML-Ready → Decision Layer
```

| Folder | Purpose | Tracked in git? |
|---|---|---|
| `raw/` | Immutable source extracts exactly as fetched from a connector. Never edited in place. | No (generated) |
| `validation/` | Validation reports / rejected-row logs from the validate stage. | No (generated) |
| `processed/` | Cleaned + feature-engineered, ML-ready tables (keyed by dataset version hash). | No (generated) |
| `pipelines/` | Pipeline run manifests (which connector, window, dataset version, timestamps). | No (generated) |
| `schemas/` | Exported, versioned data-contract snapshots (the feature schema as JSON) for diffing across runs. | Yes (small) |
| `samples/` | Bundled, version-controlled **sample datasets** (e.g. `samples/liguria/cells.csv`) so VECTIS runs fully offline. | **Yes** |

## Conventions

- **Reproducibility:** every processed artifact is identified by the pipeline's
  `dataset_version` (`raw_hash.feature_hash`, see `pipeline/runner.py`). The same
  inputs always produce the same hash.
- **Immutability of `raw/`:** treat raw extracts as read-only. Re-derive
  `processed/` from `raw/` rather than mutating files.
- **Git policy:** only `samples/` and `schemas/` are tracked. `raw/`,
  `processed/`, `validation/`, and `pipelines/` are runtime outputs ignored by
  git (see `.gitignore`); `.gitkeep` preserves the empty structure.

## How this maps to the code

- Connectors (`backend/vectis/data/connectors/`) populate `raw/` (the bundled
  `SampleConnector` reads from `samples/`).
- `pipeline/steps.py` performs validate → clean → feature-engineer.
- `pipeline/runner.py` orchestrates the stages and stamps the dataset version
  that names artifacts under `processed/` and manifests under `pipelines/`.

See [`../docs/data_pipeline.md`](../docs/data_pipeline.md) for the full pipeline
contract and how to add a dataset or connector.
