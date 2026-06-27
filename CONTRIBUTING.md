# Contributing to VECTIS

Thanks for your interest in VECTIS. This guide explains how to set up a dev
environment and the standards we hold contributions to.

## Project philosophy

VECTIS is production-grade decision-intelligence infrastructure, not a demo.
Three principles gate every contribution:

1. **Explainability** — every AI output must be traceable to evidence.
2. **Human-in-the-loop** — VECTIS recommends; humans decide.
3. **Reproducibility** — `docker compose up` must produce identical results
   from the bundled sample data, with no external API keys.

## Local setup

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest

# Frontend (Node 20+)
cd ../frontend
npm install
npm run dev
```

Or run the whole stack:

```bash
make up      # docker compose: db + backend + frontend
make seed    # generate the deterministic Liguria sample
make demo    # run one analysis end-to-end and print the Decision Report
```

## Standards

- **Typing**: backend is fully type-hinted; `mypy` must pass. Frontend is
  strict TypeScript.
- **Lint/format**: `ruff` (Python) and `eslint`/`prettier` (TS). Run `make lint`.
- **Tests**: new logic needs tests. ML changes must keep metric thresholds in
  `backend/tests/model/` green. Run `make test`.
- **Commits**: imperative mood, scoped (e.g. `agents: bound critic revision loop`).
- **Contracts first**: changes to `DecisionReport`/`AgentState` schemas are
  reviewed carefully — they are the spine the whole system agrees on.

## Adding things

- **A new agent** → see [`docs/agents.md`](docs/agents.md).
- **A new dataset/connector** → see [`docs/data_pipeline.md`](docs/data_pipeline.md).

## Pull requests

Open against `main`, fill out the PR template, ensure CI is green. By
contributing you agree your work is licensed under Apache-2.0.
