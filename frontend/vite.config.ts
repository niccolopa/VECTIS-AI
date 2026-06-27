/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// The dev server proxies /api and /health to the backend so the frontend has no
// hard-coded host in development. In production the API base URL is provided via
// VITE_API_BASE_URL (see src/services/apiClient.ts).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
    css: false,
    // MapLibre needs WebGL (unavailable in jsdom); stub the bare module for the
    // test env only (exact match so the CSS subpath import still resolves).
    alias: [
      { find: /^maplibre-gl$/, replacement: path.resolve(__dirname, "src/test/maplibreStub.ts") },
    ],
  },
});
