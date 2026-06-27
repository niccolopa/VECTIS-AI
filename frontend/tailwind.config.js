/** @type {import('tailwindcss').Config} */
// "Matrix meets Palantir Gotham" tactical design system. Pure-black, monospaced,
// neon-green/cyan. Tokens stay few and semantic so the whole console restyles from
// here (components reference bg/surface/text/accent/border, not raw hexes).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#000000", // app background — pure black
        surface: "#020806", // panels / cards
        "surface-2": "#010403", // insets
        "surface-3": "#04120c", // hover / raised
        border: "#0d3b2a", // dim neon contour
        "border-strong": "#16a34a", // active neon contour
        text: "#39ff14", // neon green
        muted: "#1fae57",
        "muted-2": "#0f7a44",
        accent: "#00ffd5", // neon cyan
        "accent-dim": "#0b6b63",
        // Risk bands — single source of truth shared with the map ramp (utils/risk.ts).
        risk: {
          low: "#22c55e",
          moderate: "#eab308",
          high: "#f59e0b",
          severe: "#ef4444",
        },
      },
      fontFamily: {
        // Strictly monospaced everywhere — `sans` aliases the mono stack so existing
        // font-sans usages become terminal-style without touching every component.
        sans: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        xl: "0.75rem",
      },
      boxShadow: {
        glow: "0 0 8px rgba(57,255,20,0.45), 0 0 2px rgba(57,255,20,0.6)",
        "glow-cyan": "0 0 8px rgba(0,255,213,0.5), 0 0 2px rgba(0,255,213,0.7)",
      },
    },
  },
  plugins: [],
};
