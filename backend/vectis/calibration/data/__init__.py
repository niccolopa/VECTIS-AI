"""Historical data acquisition — real FIRMS fire labels + real ERA5 weather.

Re-runnable pipeline, not a notebook: ``python -m vectis.calibration.data.build
--region california --start 2020-06-01 --end 2020-10-31`` re-fetches any region/window
(see :mod:`vectis.calibration.data.build`).

Sources and credentials
-----------------------
- **NASA FIRMS archive** (:mod:`.firms_archive`): the area-CSV API's *standard processing*
  products serve the historical archive. Requires a free MAP_KEY in
  ``VECTIS_FIRMS_API_KEY`` — obtain one at https://firms.modaps.eosdis.nasa.gov/api/map_key/
  (or route through the Session-31 Sluice gateway, which holds the key).
- **ERA5 reanalysis** (:mod:`.era5`): fetched via Open-Meteo's **keyless** historical
  archive API (``/v1/era5``), which serves the ERA5 dataset — the same choice Session 29
  made for live weather, so the whole pipeline needs exactly one credential (FIRMS).
  Direct Copernicus CDS access (``cdsapi``, already in the ``live`` extra) is the
  alternative for bulk gridded pulls; it would need a CDS account key in
  ``VECTIS_CDS_API_KEY`` plus NetCDF parsing — deliberately not built until a use case
  outgrows the per-point API.
"""
