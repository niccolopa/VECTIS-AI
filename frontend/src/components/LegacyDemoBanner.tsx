import { Link } from "react-router-dom";

// Fences the V1 legacy surfaces (Risk Intelligence + Reports) off from the V4
// global system. This is the original Session-1 reactive pipeline: a logistic
// regression trained on a fixed 240-cell California sample, narrated by a
// 6-agent board with SHAP explainability. It shares no state with the live H3
// grid, the real FIRMS/USGS/GDACS feeds, or the tiering engine — so a new user
// must never read a California-only Case Study as global capability.
export function LegacyDemoBanner() {
  return (
    <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
      <span className="font-semibold uppercase tracking-wide">V1 Legacy Demo · California Case Study.</span>{" "}
      A self-contained historical demo of VECTIS's original reactive pipeline — a
      logistic-regression model trained on a fixed 240-cell California sample,
      narrated by a 6-agent board with SHAP explainability. It is{" "}
      <span className="font-semibold">architecturally distinct</span> from the
      planet-scale system: it does not touch the live H3 grid, the real
      FIRMS/USGS/GDACS feeds, or the tiering engine, and only scores California.
      For live global analysis, use the{" "}
      <Link to="/terminal" className="underline hover:text-amber-100">
        Global Terminal
      </Link>
      .
    </div>
  );
}
