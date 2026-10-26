# CargoPulse — Logistics & Shipment Intelligence Platform

CargoPulse tracks shipments across carriers and lanes, records every lifecycle change, and
raises alerts automatically when a shipment misses its ETA. The dashboard is computed live
from PostgreSQL; overdue detection runs on a Celery beat schedule backed by Redis.

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 4, React Router 7, Axios, Recharts 3 |
| Backend | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2.x, Alembic |
| Data | PostgreSQL 16 |
| Jobs | Celery 5 (worker + beat) with Redis 7 as broker, result backend and lock store |
| Tests | pytest (81 tests against a real PostgreSQL test database) |
| Dev | Docker Compose, Git |

## Features

- **Dashboard** — total / in-transit / delivered / delayed counts, on-time rate, 30-day
  dispatched-vs-delivered trend, status breakdown, carrier on-time ranking, transport-mode
  mix, recent shipments, deliveries due in the next 7 days and the most severe open alerts.
  Refreshes every 60 s; every figure links to the matching filtered list.
- **Shipments** — create, view, edit and delete; generated or custom tracking IDs; ETA
  derived from the route's transit time when omitted; full-text search (tracking ID,
  customer, reference, city, lane code, carrier), multi-status / carrier / route / mode /
  priority / overdue / ETA-range filters, sortable columns and pagination, all reflected
  in the URL.
- **Lifecycle** — validated transitions
  (`pending → picked_up → in_transit → out_for_delivery → delivered`, plus `delayed` and
  `cancelled`) with a persistent, append-only status history recording who made each
  change. Terminal shipments are locked; leaving `delayed` requires a future ETA.
- **Carriers & routes** — CRUD with uniqueness rules, live per-carrier performance,
  generated lane codes (e.g. `SHA-LOS-OCN`), deactivate instead of delete when in use.
- **Overdue monitor** — scheduled Celery task flags shipments past ETA as `delayed`,
  raises one alert per shipment per ETA (database-enforced), escalates severity as delays
  grow, and resolves alerts automatically when a shipment is delivered, cancelled or
  re-planned. Operators can resolve alerts manually or trigger a scan from the UI.
- **API** — REST with correct status codes (201/204/404/409/422/503), consistent error
  bodies, Pydantic schemas, and interactive docs at `/docs` (Swagger) and `/redoc`.

## Quick start (Docker)

Requirements: Docker with Compose v2.

```bash
cp .env.example .env        # optional — every value has a default
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API | http://localhost:8000/api |
| Swagger docs | http://localhost:8000/docs |

On first start the `api` container applies migrations and loads demo data (8 carriers,
16 routes, 160 shipments with history and alerts, all dated relative to "now"). Three
shipments are seeded to breach their ETA within ~30 minutes, so you can watch the worker
flag them live. Seeding is skipped when data already exists.

Useful commands (see `Makefile`):

```bash
make test       # run the pytest suite in the api container
make reseed     # wipe and reload demo data
make logs       # follow api, worker and beat logs
make scan       # queue an overdue scan immediately
```

To shorten the scan interval while exploring, set `OVERDUE_SCAN_INTERVAL_SECONDS=30`
in `.env` and run `docker compose up -d worker beat api`.

## Local development (without Docker)

Requirements: Python 3.12+, Node 22.12+, PostgreSQL 14+, Redis 6+.

```bash
# 1. Databases
createuser -P cargopulse                      # password: cargopulse
createdb -O cargopulse cargopulse
createdb -O cargopulse cargopulse_test

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env                       # localhost settings
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload                 # http://localhost:8000

# 3. Worker and scheduler (two more terminals, venv activated, in backend/)
celery -A app.worker.celery_app worker --loglevel=INFO
celery -A app.worker.celery_app beat --loglevel=INFO --schedule /tmp/celerybeat-schedule

# 4. Frontend
cd ../frontend
npm install
npm run dev                                   # http://localhost:5173 (proxies /api)
```

## Tests

```bash
cd backend && pytest            # or: make test (Docker)
```

The suite migrates the `cargopulse_test` database down and up (proving the migration is
reversible), truncates tables between tests, and uses an in-memory Redis (fakeredis with
Lua support) for locks and caches. Coverage:

| File | What it verifies |
|---|---|
| `test_shipments.py` | CRUD, tracking-ID generation/uniqueness, field and date validation, inactive/unknown references, search, every filter, sorting, pagination, invalid query params |
| `test_lifecycle.py` | allowed/invalid transitions, history ordering, terminal locking, revised-ETA rule, alert auto-resolution on delivery and ETA change |
| `test_carriers_routes.py` | carrier and route CRUD, validation, duplicate handling, delete protection, stats |
| `test_dashboard.py` | every summary metric against a known dataset, breakdowns, trend window, carrier/mode performance, upcoming and recent lists, last-scan cache, health |
| `test_overdue_alerts.py` | detection, idempotent re-runs, dedupe after manual resolution, superseded ETAs, auto-resolution, severity escalation, grace period, DB constraints (partial unique index, dedupe key, CHECKs), Celery task execution, Redis lock contention, beat schedule, scan API (202/503) |

## How overdue detection works

```
celery beat ──every OVERDUE_SCAN_INTERVAL_SECONDS──▶ Redis queue ──▶ celery worker
                                                                       │
                       Redis lock (SET NX + expiry) prevents overlapping scans
                                                                       ▼
            detect_overdue_shipments()  (app/services/alert_service.py)
            1. resolve active alerts whose shipment is delivered/cancelled or whose ETA moved
            2. find active shipments with eta < now − grace (row locks, SKIP LOCKED)
            3. INSERT alert … ON CONFLICT DO NOTHING; escalate severity of existing alerts
            4. transition the shipment to `delayed` with a system history entry
            5. store the run summary in Redis (shown on the dashboard and Alerts page)
```

Duplicate prevention is guaranteed by PostgreSQL, not just application logic:

- `alerts.dedupe_key` is unique and built from type + shipment + ETA, so one ETA can never
  raise two alerts, even after an operator resolves the first one.
- A partial unique index (`shipment_id, alert_type WHERE status = 'active'`) allows at
  most one open alert per shipment and type.

Severity is based on hours past ETA (< 6 h low, < 24 h medium, < 72 h high, otherwise
critical), raised one level for express and two for critical-priority shipments. A worker
also runs one scan as soon as it starts.

## API overview

All endpoints are under `/api`; full schemas are in Swagger at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | DB and Redis status (503 when degraded) |
| GET | `/dashboard` | All dashboard data in one call (`trend_days` 7–180) |
| GET | `/dashboard/summary`, `/status-breakdown`, `/volume-trend`, `/carrier-performance` | Individual dashboard datasets |
| GET | `/shipments` | List with `search`, `status` (comma-separated), `carrier_id`, `route_id`, `priority`, `mode`, `overdue`, `eta_from`, `eta_to`, `sort_by`, `sort_order`, `page`, `page_size` |
| POST | `/shipments` | Create (201) |
| GET | `/shipments/{id}` | Detail with history, alerts and allowed transitions |
| GET | `/shipments/tracking/{tracking_id}` | Look up by tracking ID |
| PATCH | `/shipments/{id}` | Update details (status changes are rejected here) |
| DELETE | `/shipments/{id}` | Delete with history and alerts (204) |
| POST | `/shipments/{id}/status` | Lifecycle transition (409 if not allowed) |
| GET | `/shipments/{id}/history` | Status history |
| GET | `/shipments/lifecycle` | Transition map |
| GET/POST | `/carriers` | List / create |
| GET/PATCH/DELETE | `/carriers/{id}` | Read / update / delete (409 when in use) |
| GET/POST | `/routes` | List / create |
| GET/PATCH/DELETE | `/routes/{id}` | Read / update / delete (409 when in use) |
| GET | `/alerts` | List with `status`, `severity`, `shipment_id`, `search` |
| GET | `/alerts/counts` | Open/resolved counts by severity |
| POST | `/alerts/{id}/resolve` | Resolve manually (409 if already resolved) |
| POST | `/alerts/scan` | Queue a scan on the worker (202, 503 if the broker is down) |
| GET | `/alerts/scan/{task_id}` | Poll a queued scan |
| GET | `/alerts/scan/last` | Most recent scan summary |

Errors use one shape: `{"detail": "…", "code": "not_found|conflict|validation_error|…", "field": "…"}`.
Request-schema violations return FastAPI's standard 422 list.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://cargopulse:cargopulse@localhost:5432/cargopulse` | App database |
| `TEST_DATABASE_URL` | `…/cargopulse_test` | Database used by pytest |
| `REDIS_URL` | `redis://localhost:6379/0` | Locks, scan summary cache, default broker |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | `REDIS_URL` | Celery transport and results |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Allowed browser origins (comma-separated) |
| `OVERDUE_SCAN_INTERVAL_SECONDS` | `300` | Beat schedule for the overdue scan |
| `OVERDUE_GRACE_MINUTES` | `0` | Minutes past ETA before a shipment is overdue |
| `OVERDUE_LOCK_TIMEOUT_SECONDS` | `120` | Redis lock expiry |
| `SEED_DEMO_DATA` | `true` | Seed on first container start |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | Where the Vite dev server proxies `/api` |
| `VITE_API_URL` | `/api` | Override the API base URL at build time |

## Data model

```
carriers 1──* shipments *──1 routes
                 │
                 ├──* shipment_status_history   (append-only, ON DELETE CASCADE)
                 └──* alerts                    (ON DELETE CASCADE)
```

- Foreign keys from shipments to carriers/routes use `ON DELETE RESTRICT`.
- CHECK constraints cover enum values, positive weight/pieces/distance, `eta > shipped_at`,
  `delivered_at` present exactly when delivered, `resolved_at` present exactly when resolved,
  code formats, and origin ≠ destination.
- Indexes: `(status, eta)` for overdue scans and dashboard counts, `eta`, `created_at`,
  `customer_name`, carrier/route FKs, `(shipment_id, changed_at)` for history, alert
  status/severity, plus the partial unique index above.

## Project structure

```
backend/
  app/
    api/endpoints/     FastAPI routers (shipments, carriers, routes, alerts, dashboard, health)
    services/          business logic (lifecycle, alert detection, dashboard queries, CRUD)
    schemas/           Pydantic request/response models
    worker/            Celery app, beat schedule and tasks
    models.py          SQLAlchemy models, constraints and indexes
    seed.py            demo data generator
  alembic/             migrations
  tests/               pytest suite
frontend/
  src/pages/           Dashboard, Shipments, ShipmentDetail, ShipmentForm, Carriers, Routes, Alerts
  src/components/      layout, charts, shared UI
  src/api/             Axios client and endpoint helpers
docker-compose.yml     db, redis, api, worker, beat, frontend
```

## Production build

`frontend/Dockerfile` has a `prod` target that builds the bundle and serves it with nginx,
proxying `/api` to the `api` service (`frontend/nginx.conf`):

```bash
docker build --target prod -t cargopulse-web ./frontend
```

For production also set `UVICORN_EXTRA_ARGS=""` (disables `--reload`), use strong
database credentials, and set `SEED_DEMO_DATA=false`.

## Troubleshooting

- **"Cannot reach the CargoPulse API"** in the UI — the backend is not running or the Vite
  proxy target is wrong; check `docker compose ps` and `VITE_API_PROXY_TARGET`.
- **Scans never run** — check `docker compose logs worker beat`; the sidebar status turns
  amber when Redis is unreachable.
- **Tests fail to connect** — create the `cargopulse_test` database (Docker creates it on
  the first start of a fresh `pgdata` volume; for an existing volume run
  `docker compose exec db createdb -U cargopulse cargopulse_test`).
- **File changes not detected in Docker** — set `VITE_USE_POLLING=true`.
