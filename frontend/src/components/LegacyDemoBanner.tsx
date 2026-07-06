import { Link } from "react-router-dom";

// Fences the archived V1 surfaces (California Case Study + Reports) off from the
// V4 global system. Kept as the project's origin artifact — the one surface that
// demonstrates the original trained-ML-model + real-SHAP pipeline, a genuinely
// different capability from the Global Terminal's closed-form attribution. It
// shares no state with the live H3 grid, the real FIRMS/USGS/GDACS feeds, or the
// tiering engine — a new user must never read it as global capability.
export function LegacyDemoBanner() {
  return (
    <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
      <span className="font-semibold uppercase tracking-wide">Origin Demo · V1 Archive · California Case Study.</span>{" "}
      The preserved original VECTIS pipeline — a logistic-regression model trained on
      a fixed 240-cell California sample, narrated by a 6-agent board with real SHAP
      explainability (the only surface with a trained ML model; the Global Terminal's
      driver attribution is closed-form). It is{" "}
      <span className="font-semibold">archival and architecturally distinct</span>{" "}
      from the planet-scale system: it does not touch the live H3 grid, the real
      FIRMS/USGS/GDACS feeds, or the tiering engine, and only scores California. The
      primary experience is the{" "}
      <Link to="/terminal" className="underline hover:text-amber-100">
        Global Terminal
      </Link>
      .
    </div>
  );
}
