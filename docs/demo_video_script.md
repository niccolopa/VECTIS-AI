# VECTIS V2 — 2-Minute Showcase Video Script

A shot-by-shot storyboard for recording a ~2:00 showcase. Goal: in two minutes a
viewer understands that VECTIS is a **real-time probabilistic decision-intelligence
platform** with serious engineering underneath (Monte Carlo, Bayesian inference, a
Math Firewall) and a tactical "Matrix × Palantir" interface.

**Recording setup**
- Dark terminal, large monospace font (the green-on-black reads as "Matrix").
- Browser at 1920×1080, OS dark mode, no bookmarks bar.
- Two prep terminals running before you hit record:
  - `make api` (backend on :8000)
  - `cd frontend && npm run dev` (UI on :5173)
- Have a third terminal ready for the live commands below.

---

## Beat sheet (total ≈ 2:00)

### 0:00 – 0:15 · Cold open — the engine, in the terminal
**On screen:** full-screen terminal. Run:
```bash
python -m vectis.scripts.demo_v2
```
**Action:** let the tactical console output stream — twin init, scenarios,
Bayesian update, the risk verdict, the AI brief.
**Narration:**
> "This is VECTIS. It doesn't guess a single number — it simulates thousands of
> possible futures and tells you how likely each one is."

### 0:15 – 0:35 · The scale flex
**On screen:** same terminal. Run:
```bash
make stress
```
**Action:** scroll to the VERDICT block.
**Narration:**
> "The engine is vectorized NumPy. One million scenarios — three million trajectory
> evaluations — in under a second, fully reproducible. And it's honest: it measured
> that multiprocessing was *slower* here, and says so."
**Hold on:** the `~0.8 s / 1,000,000 scenarios` and the cache `~6000× faster` lines.

### 0:35 – 0:55 · Enter the dashboard
**On screen:** cut to the browser → `http://localhost:5173`.
**Action:** click **Decision Intelligence** in the sidebar (the activity icon).
Let the dark, tactical dashboard load.
**Narration:**
> "Same engine, now as a command center. This is the Liguria wildfire digital twin —
> live."
**Action:** point cursor at the live risk score + "● live" badge in the header.

### 0:55 – 1:15 · Scenario Explorer
**On screen:** the **Scenario Explorer** card.
**Action:** slowly hover each branch — Baseline, Hotter & Drier, Extreme Wind —
showing the box-and-whisker spreads.
**Narration:**
> "Every branch is a full distribution, not a point. The whisker is the 5th-to-95th
> percentile, the line is the median, the dot is the mean. This is uncertainty you
> can actually see."

### 1:15 – 1:35 · What-If Simulator (the interactive moment)
**On screen:** the **What-If Simulator** card on the right.
**Action:** drag **Temperature anomaly** to **+5 °C**, then click **Run simulation**.
**Narration:**
> "Ask a question. Slide the temperature to plus five degrees and re-run —
> synchronously, served from cache. Risk jumps, and you see exactly how much."
**Hold on:** the "+X.X vs current" delta badge.

### 1:35 – 1:50 · The AI brief (Future Worlds)
**On screen:** scroll to the **AI Intelligence Brief**.
**Action:** scroll through bottom-line → analyst → optimist/pessimist debate →
red-team critique.
**Narration:**
> "Then an AI board narrates it — analyst, a debate, and a red team that attacks the
> prediction. But every number comes from the math engine. The AI writes the words,
> never the numbers. We call it the Math Firewall."

### 1:50 – 2:00 · Live update + close
**On screen:** split or cut to the third terminal. Fire a real observation:
```bash
curl -s -X POST http://localhost:8000/api/v1/stream/ingest \
  -H "Content-Type: application/json" \
  -d '{"kind":"weather_alert","source":"demo","region":"liguria","variable":"temp_anomaly_c","value":4.0,"severity":"critical"}'
```
**Action:** cut back to the dashboard — the **Probability Timeline** ticks with a new
point, no refresh.
**Narration:**
> "And it's real-time. A new observation arrives, beliefs update, the timeline moves.
> VECTIS — probabilistic decision intelligence, open source."
**End card:** repo URL + `github.com/<you>/vectis`.

---

## One-take fallback (if curl/event timing is fiddly)

Skip the live `curl` beat; instead end on the What-If + AI brief and the tagline.
The timeline still shows the seeded current-state point.

## Exact assets referenced
- Terminal demo: `python -m vectis.scripts.demo_v2` (alias `make demo-v2`)
- Stress test: `make stress` (`backend/scripts/stress_test.py`)
- Dashboard route: `/dashboard` → sidebar **Decision Intelligence**
- Live ingest: `POST /api/v1/stream/ingest` → WebSocket push → Probability Timeline
