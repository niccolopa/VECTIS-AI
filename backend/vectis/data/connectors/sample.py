"""Bundled sample connector — reads the deterministic Liguria dataset from disk.

This is the default data source and the reason VECTIS runs end-to-end with no
external credentials. The dataset is produced by
``vectis.scripts.generate_sample`` and lives under ``data/samples/<region>/``.
"""

from __future__ import annotations

import pandas as pd

from vectis.core.config import get_settings
from vectis.core.exceptions import DataValidationError
from vectis.data.connectors.base import Connector, RawFrame
from vectis.data.regions import Region


class SampleConnector(Connector):
    """Reads bundled, version-controlled sample observations."""

    name = "sample"

    def fetch(self, region: Region, window_days: int = 30) -> RawFrame:
        path = get_settings().sample_dir / region.key / "cells.csv"
        if not path.exists():
            raise DataValidationError(
                f"Sample data for region '{region.key}' not found at {path}. "
                "Run `python -m vectis.scripts.generate_sample` (or `make seed`)."
            )
        frame = pd.read_csv(path)
        return RawFrame(
            region=region,
            frame=frame,
            source=f"sample:{path.name}",
            meta={"path": str(path), "window_days": window_days, "rows": len(frame)},
        )
