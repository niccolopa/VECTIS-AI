/** @type {import('tailwindcss').Config} */
// Enterprise dark design system. Tokens are intentionally few and semantic so the
// whole console stays visually consistent (Palantir-style: dense, calm, data-first).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e14", // app background
        surface: "#11161f", // panels / cards
        "surface-2": "#0d121a", // insets
        "surface-3": "#161d28", // hover / raised
        border: "#1e2733",
        "border-strong": "#2a3645",
        text: "#e6edf3",
        muted: "#9aa4b2",
        "muted-2": "#6b7685",
        accent: "#4f8cff",
        "accent-dim": "#2a4a7f",
        // Risk bands — single source of truth shared with the map ramp (utils/risk.ts).
        risk: {
          low: "#22c55e",
          moderate: "#eab308",
          high: "#f59e0b",
          severe: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        xl: "0.75rem",
      },
    },
  },
  plugins: [],
};
