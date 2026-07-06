# Deployment — the lean single node (and how to grow it)

> VECTIS runs a worldwide picture on **one box**. This is the whole production topology,
> validated end-to-end, plus the honest note on when — and how — to scale horizontally.
> Horizontal scale is **available, not required**: nothing below needs to change to get
> there.

## The stack

`docker compose up --build` brings up five services on a single node:

| Service | Image | Role |
|---|---|---|
| **db** | `postgis/postgis:16-3.4` | Durable belief-history + roll-up store (Alembic-migrated). The system of record. |
| **redis** | `redis:7-alpine` | Shared hot-tier state store + event broker for the Redis-ready seams. Cache-only — nothing durable lives *only* here. |
| **sluice** | `vectis-backend` (alt entrypoint) | The **ingestion gateway** (Session 31): credential failover, retry, and normalization in front of NASA FIRMS / USGS / GDACS. |
| **backend** | `vectis-backend` | FastAPI app: the global H3 grid, tiered compute loop, tile server, streams, and the V1 California case study. Migrates, seeds, and trains on first boot. |
| **frontend** | `vectis-frontend` | React console (`/terminal` and the Origin Demo · V1 Archive pages). |

```bash
cp .env.example .env
make up            # docker compose up --build
```

Ports: frontend `:5173`, backend `:8000`, sluice `:8900`, PostGIS `:5432`, Redis `:6379`.
The LLM provider defaults to `mock`, so the whole stack runs **with zero external API
keys**. Set `VECTIS_LLM_PROVIDER=claude` + `VECTIS_ANTHROPIC_API_KEY` to have the board
narrate with a real model (it still only *narrates* already-computed numbers).

## Boot sequence (why the health gates exist)

`db`, `redis`, and `sluice` come up first and are healthchecked; `backend` waits for all
three, then runs `alembic upgrade head → generate_sample → train → uvicorn`. Its
healthcheck only passes once uvicorn is actually serving (`start_period: 180s` covers the
one-time model train), so `frontend` never starts against a half-ready API.

## Validated end-to-end

The four-service core (`db + redis + sluice + backend`) was brought up from a clean
build and verified on a single node:

- `db`, `redis`, `sluice`, `backend` all report **healthy**.
- `GET /health` → `{"status":"ok",...,"llm_provider":"mock"}`.
- `GET /api/v1/regions` → the V1/V2 twins **california · new_south_wales · attica**
  (no stale "liguria").
- `GET /api/v1/tiles?west=-125&south=32&east=-114&north=42&zoom=5` → real global H3 cells
  with per-hazard screening scores — the V4 grid serving live.
- `redis-cli ping` → `PONG`; sluice `GET /health` → `{"status":"ok","service":"sluice"}`.

## The ingestion gateway (Sluice)

The Sluice is a **drop-in**: the connectors build the same upstream URL whether they point
at it or straight at the real API, and they fall back to the upstream (then to offline
mock) if it isn't reachable. The offline/keyless promise is unbroken. It runs keyless
(health-only) until you give it credentials:

```bash
VECTIS_SLUICE_FIRMS_KEYS=key1,key2   # one primary + a spare or two, for outage tolerance
```

It is **not** a way to pool keys around a provider's rate limit — failover is for
reliability (a jammed key never takes the fire feed down), never quota evasion.

## Redis, honestly

Redis is provisioned as the **production** state-store + event-broker backend, behind the
`VECTIS_STATE_BACKEND=redis` and `VECTIS_BROKER=redis` seams (`RedisStateStore`,
`RedisStreamBroker`). On a single node the default in-memory path also works — a truly
minimal box can drop Redis entirely. Redis earns its place the moment you want state and
the event bus **shared across processes**, which is exactly what a second backend replica
needs. That is why it is in the single-node stack: so scaling out is a config change, not
a re-architecture.

## Horizontal scale — available, not required

`docs/scale_limits.md` has the measured ceilings: one node comfortably runs a ~100k
active-cell global hot set with sub-1.5 s cycles in tens of MB. Most deployments never
leave the single node.

When you do need more — sustained deep-analysis/narration demand above the per-tick
budgets, or more cells resident than one box's memory holds — scale **out**, not by
inflating budgets:

- Run **N backend replicas** behind a load balancer, all sharing the **same Redis**
  (hot-tier state + broker) and **same PostGIS** (durable history). The compute loop's work
  is already bounded by attention + real events, not viewer count, so replicas share load
  without duplicating it.
- Promote the simulation dispatch seam (`simulation/engine/distributed.py`, a Ray/Dask
  abstraction with a runnable local stub) to a real cluster for wider T1 throughput.

None of this changes the single-node compose — the same Redis and PostGIS services are
already the shared backends a multi-node deployment points at.
