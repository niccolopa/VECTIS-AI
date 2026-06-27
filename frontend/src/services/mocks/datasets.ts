// ⚠️ MOCK DATA — there is no backend /datasets endpoint yet.
// This is a STATIC catalog describing the data connectors that actually exist in
// the backend (backend/vectis/data/connectors/). It is clearly separated here so
// it is obvious what is real vs. placeholder. Replace with a real endpoint when
// the backend exposes one (see Session 5 tasks).

export interface DatasetEntry {
  key: string;
  name: string;
  provider: string;
  category: "fire" | "weather" | "vegetation" | "terrain" | "bundled";
  status: "active" | "planned";
  description: string;
  docsUrl?: string;
}

export const MOCK_DATASETS: DatasetEntry[] = [
  {
    key: "sample",
    name: "Bundled Liguria Sample",
    provider: "VECTIS",
    category: "bundled",
    status: "active",
    description:
      "Deterministic, version-controlled sample grid (240 cells) used for offline, reproducible analysis.",
  },
  {
    key: "firms",
    name: "Active Fire Detections",
    provider: "NASA FIRMS (MODIS/VIIRS)",
    category: "fire",
    status: "planned",
    description: "Near-real-time thermal anomaly / active fire detections.",
    docsUrl: "https://firms.modaps.eosdis.nasa.gov/api/",
  },
  {
    key: "era5",
    name: "ERA5 Reanalysis",
    provider: "Copernicus ERA5",
    category: "weather",
    status: "planned",
    description: "Temperature, humidity, and wind reanalysis fields.",
    docsUrl: "https://cds.climate.copernicus.eu/",
  },
  {
    key: "copernicus",
    name: "Land Monitoring (NDVI / Land Cover)",
    provider: "Copernicus Land",
    category: "vegetation",
    status: "planned",
    description: "Vegetation greenness (NDVI) and land-cover classification.",
    docsUrl: "https://land.copernicus.eu/",
  },
];

export const DATASETS_ARE_MOCK = true;
