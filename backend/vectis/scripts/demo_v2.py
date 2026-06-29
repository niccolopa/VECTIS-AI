"""VECTIS V2 — end-to-end Liguria wildfire intelligence demo.

Drives the *entire* V2 pipeline from one script, offline and deterministic:

    Simulated weather alert  →  RealTimeUpdater  →  Liguria RegionTwin transition
    →  Monte Carlo (100k scenarios)  →  Bayesian posterior update
    →  LangGraph Analysis Board  →  Decision Intelligence Report

Run it:  ``python -m vectis.scripts.demo_v2``  (or ``python scripts/run_demo_liguria.py``).

No API key, no network, ~1 second. The console output *is* the product here, so it
is rendered as a tactical intelligence terminal (neon, boxed panels). All numbers
come from the deterministic engine; the LLM (mock by default) only writes prose —
the Math Firewall holds end to end.
"""

from __future__ import annotations

import contextlib
import sys
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

from vectis.agents.board.schemas import DecisionIntelligenceReport
from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider
from vectis.core.schemas import RiskBand
from vectis.digital_twin.entities.region import RegionState, RegionTwin
from vectis.digital_twin.schemas import RiskState
from vectis.digital_twin.state.manager import StateManager
from vectis.simulation.schemas import SimulationConfig
from vectis.streaming.events import WeatherAlert
from vectis.streaming.updater import RealTimeUpdater

WIDTH = 76

# ── ANSI theme (VECTIS neon / enterprise tactical) ───────────────────────────
_RESET = "\033[0m"
_C = {
    "green": "\033[38;5;46m",
    "cyan": "\033[38;5;51m",
    "dim": "\033[38;5;240m",
    "bold": "\033[1m",
    "red": "\033[38;5;196m",
    "orange": "\033[38;5;208m",
    "yellow": "\033[38;5;226m",
    "white": "\033[38;5;255m",
}
_BAND_COLOR = {
    RiskBand.LOW: "green",
    RiskBand.MODERATE: "yellow",
    RiskBand.HIGH: "orange",
    RiskBand.SEVERE: "red",
}


@dataclass
class DemoResult:
    """What the demo computed — returned for assertions/programmatic use."""

    baseline: RiskState
    final: RiskState
    report: DecisionIntelligenceReport
    iterations: int


class Console:
    """Tiny stdlib renderer: ANSI theming + boxed panels (no dependencies)."""

    def __init__(self, out: TextIO, color: bool) -> None:
        self.out = out
        self.color = color

    def c(self, text: str, *names: str) -> str:
        if not self.color:
            return text
        return "".join(_C[n] for n in names) + text + _RESET

    def line(self, text: str = "") -> None:
        print(text, file=self.out)

    def info(self, tag: str, msg: str, tag_color: str = "cyan") -> None:
        self.line(f"  {self.c(f'[{tag}]', tag_color, 'bold')} {self.c(msg, 'dim')}")

    def phase(self, n: int, title: str) -> None:
        label = self.c(f"━━[ PHASE {n} · {title} ]", "green", "bold")
        tail = self.c("━" * max(0, WIDTH - len(f"━━[ PHASE {n} · {title} ]")), "green")
        self.line()
        self.line(label + tail)

    def panel(self, title: str, body: str, color: str = "cyan") -> None:
        top = self.c("╭─ ", color) + self.c(title, color, "bold") + self.c(
            " " + "─" * max(0, WIDTH - len(title) - 5) + "╮", color)
        self.line(top)
        for raw in body.splitlines() or [""]:
            for wrapped in (textwrap.wrap(raw, WIDTH - 4) or [""]):
                pad = " " * (WIDTH - 4 - len(wrapped))
                self.line(self.c("│ ", color) + self.c(wrapped + pad, "white") + self.c(" │", color))
        self.line(self.c("╰" + "─" * (WIDTH - 2) + "╯", color))

    def bar(self, frac: float, width: int = 22) -> str:
        filled = round(max(0.0, min(1.0, frac)) * width)
        return self.c("█" * filled, "green") + self.c("░" * (width - filled), "dim")


def _banner(con: Console) -> None:
    title = "VECTIS // DECISION INTELLIGENCE PLATFORM"
    con.line()
    con.line(con.c("▓" * WIDTH, "green"))
    con.line(con.c("▓▓", "green") + con.c(title.center(WIDTH - 4), "cyan", "bold") + con.c("▓▓", "green"))
    con.line(con.c("▓" * WIDTH, "green"))
    con.line(con.c("  CLASSIFICATION: VECTIS // FOR DECISION SUPPORT".ljust(WIDTH), "dim"))
    con.line(con.c(f"  GENERATED: {datetime.now(UTC):%Y-%m-%d %H:%M:%SZ}  ·  THEATER: LIGURIA, IT"
                   .ljust(WIDTH), "dim"))


def _risk_block(con: Console, title: str, rs: RiskState) -> None:
    band_color = _BAND_COLOR[rs.band]
    head = (f"{title}: {con.c(f'{rs.risk:5.1f}/100', band_color, 'bold')}  "
            f"[{con.c(rs.band.value.upper(), band_color, 'bold')}]   "
            f"confidence {con.c(f'{rs.confidence * 100:4.1f}%', 'cyan')}")
    con.line("  " + head)
    for sid, prob in sorted(rs.scenario_priors.items(), key=lambda kv: -kv[1]):
        con.line(f"    {sid:<14} {con.bar(prob)} {con.c(f'{prob * 100:5.1f}%', 'white')}")


def _calm_baseline() -> RegionState:
    """A quiet, in-season baseline for Liguria — elevated watch, not alarm."""
    return RegionState(
        temperature_anomaly=0.3, humidity_level=65.0,
        vegetation_stress=18.0, recent_fire_history=0.0,
    )


# Human label + unit per observed variable, for the SIGINT display.
_VAR_DISPLAY = {
    "temp_anomaly_c": ("heatwave", "temperature anomaly", "°C"),
    "rainfall_anomaly_pct": ("drought", "rainfall anomaly", "%"),
}


def _alerts() -> list[WeatherAlert]:
    """An incoming severe heatwave followed by a drought confirmation."""
    return [
        WeatherAlert(source="ARPAL Regional Authority", region="liguria",
                     variable="temp_anomaly_c", value=4.5, severity="critical"),
        WeatherAlert(source="Copernicus EMS", region="liguria",
                     variable="rainfall_anomaly_pct", value=-35.0, severity="critical"),
    ]


def _sigint_line(ev: WeatherAlert) -> str:
    """Render one alert as an intercepted-transmission line (derived from the event)."""
    kind, label, unit = _VAR_DISPLAY.get(ev.variable, ("signal", ev.variable, ""))
    return f"{ev.source:<26} {ev.severity.upper()} {kind}: {label} {ev.value:+g}{unit}"


def _silence_logs() -> None:
    """Mute structlog's operational lines so the demo terminal stays clean.

    The engine/twin/board emit structured INFO logs; for the demo the console
    output *is* the product, so raise the threshold before the first log fires.
    (Harmless in tests — their captured buffer never received these anyway.)
    """
    import logging

    import structlog

    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.dev.ConsoleRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def run_demo(
    *, iterations: int = 100_000, seed: int = 7, color: bool = True,
    out: TextIO | None = None, llm: LLMProvider | None = None,
) -> DemoResult:
    """Execute the full V2 pipeline once and render it. Returns the computed result."""
    _silence_logs()
    con = Console(out or sys.stdout, color)

    # ── PHASE 1 — INITIALIZE ────────────────────────────────────────────────
    _banner(con)
    con.phase(1, "INITIALIZE")
    con.info("BOOT", "Bringing VECTIS V2 core online...")
    con.info("ENGINE", f"Vectorized Monte Carlo engine armed — {iterations:,} scenarios/run.")
    config = SimulationConfig(n_iterations=iterations, seed=seed)
    twin = RegionTwin("liguria", state=_calm_baseline(), config=config)
    manager = StateManager()
    manager.register(twin)
    updater = RealTimeUpdater(manager)
    baseline = updater.risk_state("liguria")
    assert baseline is not None
    con.info("TWIN", "Registered Digital Twin: RegionTwin[liguria] (Climate Risk).")
    con.info("OK", "Core online. Baseline posture established.", "green")
    con.line()
    _risk_block(con, "BASELINE RISK", baseline)

    # ── PHASE 2 — OBSERVE ───────────────────────────────────────────────────
    con.phase(2, "OBSERVE")
    alerts = _alerts()
    con.info("SIGINT", "Inbound environmental intelligence intercepted.", "yellow")
    for ev in alerts:
        con.line(con.c("    " + _sigint_line(ev), "white"))

    # ── PHASE 3 — CALCULATE ─────────────────────────────────────────────────
    con.phase(3, "CALCULATE")
    for i, event in enumerate(alerts, 1):
        con.info("INGEST", f"Event {i}/{len(alerts)} → RealTimeUpdater (variable={event.to_observation().variable}).")
        con.info("TWIN", "Applying deterministic state transition (fuel-stress / ignition load).")
        con.info("MONTE-CARLO", f"Sampling {iterations:,} scenarios × 3 branches...")
        change = updater.process(event)
        assert change is not None
        con.info("BAYES", f"Posterior belief shift Δ={change.belief_shift:.3f} "
                          f"(rerun={'yes' if change.triggered_rerun else 'no'}).")
        con.info("OK", f"Risk recomputed → {change.risk.risk:.1f}/100 "
                       f"[{change.risk.band.value.upper()}].", "green")
    final = updater.risk_state("liguria")
    assert final is not None
    con.line()
    _risk_block(con, "UPDATED RISK ", final)
    delta = final.risk - baseline.risk
    con.line("  " + con.c(f"Δ RISK  {delta:+.1f}", "red" if delta > 0 else "green", "bold")
             + con.c(f"   ({baseline.band.value.upper()} → {final.band.value.upper()})", "dim"))

    # ── PHASE 4 — ANALYZE (LangGraph board) ─────────────────────────────────
    con.phase(4, "ANALYZE")
    con.info("BOARD", "Convening Simulation Analysis Board (Analyst · Scenario · Debate · Red-Team).")
    report = SimulationBoardService(llm=llm).analyze_twin(twin)
    con.info("OK", f"Decision Intelligence Report compiled — {report.report_id}.", "green")

    # ── PHASE 5 — REPORT ────────────────────────────────────────────────────
    con.phase(5, "DECISION INTELLIGENCE REPORT")
    _render_report(con, report)
    return DemoResult(baseline=baseline, final=final, report=report, iterations=iterations)


def _render_report(con: Console, report: DecisionIntelligenceReport) -> None:
    a = report.analyst
    con.panel("BLUF — BOTTOM LINE UP FRONT", report.bottom_line, "green")
    con.line()

    metrics = (
        f"RISK SCORE     {a.risk_score:5.1f} / 100   [{a.risk_band.value.upper()}]\n"
        f"CONFIDENCE     {a.confidence_pct:5.1f}%\n"
        f"RESIDUAL       {report.red_team.residual_uncertainty_pct:5.1f}%   (unmodeled tail)\n"
        f"PRIMARY DRIVER {a.primary_driver}"
    )
    con.panel("KEY METRICS  ·  ENGINE OUTPUT (AUTHORITATIVE)", metrics, "cyan")
    con.line()

    con.panel("EXECUTIVE SUMMARY  ·  LEAD ANALYST", a.summary, "cyan")
    con.line()

    con.line(con.c("  SCENARIO PROJECTIONS  ·  NARRATIVE CELL", "cyan", "bold"))
    for sc in report.scenarios:
        title = f"{sc.name}  —  {sc.probability_pct:.1f}% probability"
        con.panel(title, sc.storyline, "dim")
    con.line()

    con.panel("ADVERSARIAL REVIEW · BLUE TEAM (OPTIMIST)", report.debate.optimist_case, "green")
    con.panel("ADVERSARIAL REVIEW · GOLD TEAM (PESSIMIST)", report.debate.pessimist_case, "orange")
    con.line()

    rt = report.red_team
    blind = "\n".join(f"• {b}" for b in rt.blind_spots)
    con.panel("RED TEAM · RISK CRITIC", f"{rt.challenge}\n\nBLIND SPOTS:\n{blind}", "red")
    con.line()

    footer = (f"  {report.report_id}  ·  {report.classification}  ·  "
              f"MATH FIREWALL ENFORCED (numbers = engine, prose = analysts)")
    con.line(con.c("─" * WIDTH, "green"))
    con.line(con.c(footer, "dim"))
    con.line(con.c("─" * WIDTH, "green"))


def _force_utf8_stdout() -> None:
    """Ensure stdout can emit box-drawing/neon glyphs on any console (incl. cp1252).

    Modern terminals just reconfigure to UTF-8. On legacy Windows consoles where
    structlog's colorama wrapper blocks ``reconfigure``, fall back to wrapping the
    underlying binary buffer — so the demo never dies with a UnicodeEncodeError.
    """
    import io

    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[union-attr]
        return
    buffer = getattr(sys.stdout, "buffer", None) or getattr(
        getattr(sys.stdout, "wrapped", None), "buffer", None
    )
    if buffer is not None:  # pragma: no cover - legacy-console only
        with contextlib.suppress(Exception):
            sys.stdout = io.TextIOWrapper(
                buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
            )


def main() -> None:
    """Console entry point — render the demo to stdout in full color."""
    _force_utf8_stdout()
    run_demo(color=True)


if __name__ == "__main__":
    main()
