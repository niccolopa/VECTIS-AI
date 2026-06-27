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
