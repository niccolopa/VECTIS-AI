"""Data engineering layer: region registry, connectors, and the processing pipeline."""

from vectis.data.regions import REGIONS, Region, get_region

__all__ = ["REGIONS", "Region", "get_region"]
