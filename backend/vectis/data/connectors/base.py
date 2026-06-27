"""Connector interface and the raw data envelope it returns."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from vectis.data.regions import Region


@dataclass
class RawFrame:
    """Raw observations for a region plus provenance metadata.

    The ``content_hash`` makes ingestion reproducible and auditable: identical
    inputs always yield the same hash, which we thread through the pipeline and
    record in the model card and report trace.
    """

    region: Region
    frame: pd.DataFrame
    source: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        digest = hashlib.sha256(
            pd.util.hash_pandas_object(self.frame, index=True).values.tobytes()
        ).hexdigest()
        return digest[:16]


class Connector(ABC):
    """A source of raw observations for a region.

    Implementations must return a :class:`RawFrame` whose dataframe contains at
    least the columns in ``vectis.data.pipeline.schema.RAW_COLUMNS``.
    """

    name: str = "connector"

    @abstractmethod
    def fetch(self, region: Region, window_days: int = 30) -> RawFrame:
        """Fetch raw observations for ``region`` over the trailing window."""
        raise NotImplementedError
