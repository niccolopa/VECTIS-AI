# Data Pipeline & Connectors

The pipeline turns raw observations into a validated, versioned feature matrix the ML
layer can trust. Each stage is a pure, independently testable function.

```
RawFrame ──► validate ──► clean ──► engineer_features ──► PipelineResult
            (schema +     (impute,    (derive model        (features +
             ranges)       dedup)      feature vector)       content hash)
```

Code: `backend/vectis/data/pipeline/` · feature definitions: `pipeline/schema.py`.

## Stages

1. **Validate** (`steps.validate`) — assert required columns exist, values are within
   plausible physical ranges, and land-cover categories are known. Fails fast with
   `DataValidationError`.
2. **Clean** (`steps.clean`) — drop duplicate cells, impute missing numerics with column
   medians.
3. **Feature-engineer** (`steps.engineer_features`) — derive the model feature vector
   (e.g. `vegetation_stress = 1 − NDVI`, `fuel_flammability` from land cover) and
   guarantee finiteness.

## Versioning / reproducibility

`run_pipeline` returns a `PipelineResult` carrying a `dataset_version` =
`raw_hash.feature_hash`, both SHA-256 content hashes. Identical inputs always produce the
same version, which is recorded in the **model card** and every report's trace. This is
how a result becomes auditable and reproducible.

## Feature schema (single source of truth)

`pipeline/schema.py` defines each model feature once — name, human label, description,
unit, and expected risk direction — via `FeatureSpec`. The sample generator, the
pipeline, the ML layer, and the human-readable drivers in reports all import from here,
so they cannot drift apart.

Current wildfire features: temperature anomaly, vegetation stress, drought index,
relative humidity, wind speed, terrain slope, fuel flammability, historical fire count.

## Connectors

A `Connector` (`data/connectors/base.py`) returns a `RawFrame` with at least the columns
in `RAW_COLUMNS`.

- **`SampleConnector`** (default) — reads the bundled, reproducible Liguria dataset from
  `data/samples/california/cells.csv`. This is why VECTIS runs fully offline.
- **Live stubs** (`connectors/live.py`) — `FirmsConnector` (NASA FIRMS active fire),
  `Era5Connector` (Copernicus ERA5 weather), `CopernicusLandConnector` (NDVI/land cover).
  They implement the interface and raise until configured with credentials.

### The bundled sample

`backend/vectis/scripts/generate_sample.py` synthesizes a physically-plausible Liguria
grid (elevation rises inland, hotter/drier inland, etc.) with a `had_fire` label drawn as
a noisy function of the drivers — so the ML layer learns a real, explainable signal. It
is **deterministic** (fixed seed) and **not** real satellite data.

```bash
make seed         # or: python -m vectis.scripts.generate_sample
```

## Adding a dataset / region

1. Add a `Region` to `data/regions.py` (bbox + grid resolution).
2. Provide data: extend the sample generator, or implement a `Connector` mapping your
   source onto `RAW_COLUMNS` at the region's grid resolution.
3. If you add features, define them in `schema.py` (`FeatureSpec`) so they flow through
   ML and into report drivers automatically.
4. `make seed && make train` then run an analysis.
