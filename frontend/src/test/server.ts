// MSW request-mocking server: realistic backend responses for tests, so the UI
// is exercised against the real API contract without a live backend.
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import {
  healthFixture,
  regionFixture,
  reportFixture,
  summaryFixture,
} from "@/test/fixtures";

export const handlers = [
  http.get("/health", () => HttpResponse.json(healthFixture)),
  http.get("/api/v1/regions", () => HttpResponse.json([regionFixture])),
  http.get("/api/v1/analyses", () => HttpResponse.json([summaryFixture])),
  http.get("/api/v1/analyses/:id", ({ params }) =>
    HttpResponse.json({ ...reportFixture, id: String(params.id) }),
  ),
  http.post("/api/v1/analyses", () => HttpResponse.json(reportFixture, { status: 201 })),
  // Default connector status: a mixed live state (banner absent). Tests that care
  // about the all-synthetic banner or specific badges override this via server.use().
  http.get("/api/v1/connectors", () =>
    HttpResponse.json({
      connectors: [
        { source: "nasa_firms", label: "Fire", data_source: "synthetic_fallback" },
        { source: "usgs_quake", label: "Quake", data_source: "live" },
        { source: "gdacs", label: "Multi-hazard", data_source: "live" },
        { source: "weather_api", label: "Weather", data_source: "live" },
      ],
      all_synthetic: false,
      any_live: true,
    }),
  ),
  http.get("/api/v1/models/:region", () =>
    HttpResponse.json({
      model_name: "logistic_regression",
      region: "liguria",
      dataset_version: "v1",
      feature_names: [],
      metrics: { roc_auc: 0.907 },
      candidates: {},
      created_at: reportFixture.generated_at,
      seed: 42,
      notes: "",
    }),
  ),
];

export const server = setupServer(...handlers);
