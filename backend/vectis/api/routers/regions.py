"""Regions resource — list available analysis regions and their extent."""

from __future__ import annotations

from fastapi import APIRouter

from vectis.data.regions import REGIONS, Region

router = APIRouter(prefix="/api/v1/regions", tags=["regions"])


def _serialize(region: Region) -> dict:
    bb = region.bbox
    return {
        "key": region.key,
        "label": region.label,
        "country": region.country,
        "grid": {"rows": region.rows, "cols": region.cols, "cells": region.n_cells},
        "bbox": {"min_lat": bb.min_lat, "min_lon": bb.min_lon,
                 "max_lat": bb.max_lat, "max_lon": bb.max_lon},
        "center": {"lat": (bb.min_lat + bb.max_lat) / 2,
                   "lon": (bb.min_lon + bb.max_lon) / 2},
    }


@router.get("")
def list_regions() -> list[dict]:
    return [_serialize(r) for r in REGIONS.values()]
