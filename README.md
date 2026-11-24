# AgentTrace

AgentTrace is an AI-agent observability and debugging interface. The repository contains a light-themed React/Vite frontend and a FastAPI + MongoDB backend. The frontend continues to use its clearly labeled local preview fixtures; it is not yet connected to the API.

## Frontend

Requirements: Node.js 20.19+ or 22.12+ and npm.

```powershell
npm install
npm run dev
```

The Vite app runs at <http://localhost:5173>. Production build: `npm run build`.

Set `VITE_API_BASE_URL` in the root `.env` when preparing API integration. The default is `http://localhost:8000/api`.

## Backend setup (Windows)

Requires Python 3.11 or later. Python 3.14 was used to build and test this milestone.

From the repository root, create a local environment file and virtual environment:

```powershell
Copy-Item .env.example .env
py -3.14 -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Edit the root `.env` and set `MONGODB_URI`. The `.env` file is ignored by Git.

### MongoDB Atlas

1. Create a MongoDB Atlas cluster and a database user with access to the `agenttrace` database.
2. In Atlas Network Access, allow your current development IP address. Avoid opening access to every IP address.
3. Choose **Connect → Drivers → Python** and copy the connection URI.
4. Replace the username/password placeholders in `.env`; URL-encode reserved characters in the password. Keep the URI only in `.env` and never in source files.
5. Set `MONGODB_DATABASE=agenttrace` and `FRONTEND_URL=http://localhost:5173`.

Alternatively, if MongoDB is already installed locally, use `MONGODB_URI=mongodb://127.0.0.1:27017`. This project does not install or manage a MongoDB server.

### Start the API

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python run.py
```

`run.py` reads `API_HOST`, `API_PORT`, and `APP_ENV` from the root `.env`. The equivalent direct development command is `uvicorn app.main:app --reload` from `backend\` (using Uvicorn's default host and port).

Interactive API documentation is at <http://localhost:8000/docs>.

The API starts even if MongoDB is not configured or unavailable. In that case `/api/health` reports `database_status` as `not_configured` or `unavailable` and returns HTTP 503; database-backed endpoints also return 503. Configure MongoDB and use `/api/health` to verify the current connection.

### Run tests

From the `backend\` directory with its virtual environment active:

```powershell
python -m pytest -q
```

The default suite uses an isolated in-memory Mongo-shaped test double and does not read or modify a development database. A live persistence integration test is skipped unless both `MONGODB_TEST_URI` and `MONGODB_TEST_DATABASE` are set. It requires a dedicated database name beginning with `agenttrace_test_`, exercises project creation and a demo run, then drops only that test database. Never set the test database to `agenttrace`.

## Backend structure

```text
backend/
  app/
    core/       Settings and the single async PyMongo connection manager
    models/     Typed MongoDB document shapes
    agents/     Deterministic synthetic demo scenarios
    debugging/  Evidence-based failure and propagation analysis
    graph/      NetworkX dependency graph construction and serialization
    routes/     Health, projects, runs/events, and demo execution endpoints
    schemas/    Pydantic request and response validation
    services/   Run lifecycle, event persistence, demo orchestration, retrieval, debug analysis
    tracing/    Event creation, collection, validation, and normalization
    utils/      MongoDB-to-API serialization
  tests/        API tests, test doubles, and optional live connection check
  requirements.txt
  run.py
```

The async MongoDB API comes from PyMongo's `AsyncMongoClient` (PyMongo 4.13+). One client is created during FastAPI lifespan startup, its indexes are initialized there, and the same client is closed on shutdown. Collection operations use async FastAPI handlers consistently.

## MongoDB collections and indexes

The database name defaults to `agenttrace` and can be changed through `MONGODB_DATABASE`. MongoDB `_id` fields use `ObjectId`; API IDs and the `project_id`, `run_id`, and parent references are serialized as strings. Trace events are stored separately from runs so large traces do not grow a single run document.

| Collection | Purpose | Indexes |
| --- | --- | --- |
| `projects` | Project name, description, UTC creation/update timestamps | `name` for lookups; `created_at` descending for recent-first lists |
| `agent_runs` | Project reference, task, agent, status and timing | `project_id`, `status`, `started_at` descending, and compound `project_id + started_at` for project run history |
| `trace_events` | Ordered event records with flexible JSON inputs/outputs/error/metadata | `run_id`, `sequence_number`, `parent_event_id`, and compound `run_id + sequence_number` for trace reads |
| `evaluations` | Numeric run metrics and ground-truth availability state | `run_id`, `metric_name`, and compound `run_id + metric_name` |
| `experiments` | Experiment metadata and associated run ID strings | `created_at` descending |

Indexes are non-unique and initialized idempotently at startup. The `experiments` service verifies every associated run exists before storing an experiment. Project deletion returns 409 while runs reference that project, preserving run and event data; there is no cascade deletion in this milestone.

UTC-aware datetimes are stored and returned. Run/event status and event type fields use enumerated values. Nested event structures accept JSON-compatible values. Localization metrics carry a ground-truth state; the backend does not infer that an unverified metric is accurate.

## Demo execution and trace pipeline

`POST /api/demo/run` executes one of six deterministic scenarios without an external model or tool service. Every generated run and event is marked `synthetic: true` with source/scenario metadata. These records demonstrate the product and are not traces from a live AI agent. The `wrong_tool_selection` case is explicitly an illustrative fixture, not a detected reasoning failure.

The pipeline is:

1. `RunManager` verifies the project and creates a pending run with no invented start time.
2. It marks the run running and records the actual UTC start time.
3. `DemoAgent` generates event payloads in memory and has no database access.
4. `TraceCollector` validates each payload and rejects mixed run IDs or duplicate event IDs.
5. `TraceProcessor` assigns one-based sequence numbers, normalizes timestamps to UTC, checks event IDs, validates same-run parent references, and rejects cycles.
6. `EventPersistence` upserts each trace event by its Mongo `_id`. Repeating the same persistence request does not insert duplicate event IDs.
7. `RunManager` stores the terminal status, persisted event count, end time, and measured wall-clock duration.

Events stay in `trace_events`, with `run_id` stored as a string and `_id` exposed as `event_id` (the API also keeps the general `id` field). Parent IDs refer to event ObjectIds in that same run. If persistence fails after some events have been written, the run is finalized as failed where MongoDB remains reachable, and its event count/metadata show the available partial state. Writes are idempotent by event ID, but there is no multi-document transaction; a partial trace can remain after a database interruption.

The six scenarios are `successful_execution`, `tool_failure`, `wrong_tool_selection`, `repeated_tool_calls`, `error_with_recovery`, and `unrecovered_failure`. `duration_ms` is measured wall-clock time for the local synchronous demo pipeline (and can be near zero); it is not a simulated agent latency.

## Execution graph and debugging analysis

`GET /api/runs/{run_id}/graph` and `GET /api/runs/{run_id}/debug` derive their results from the persisted `trace_events` collection. NetworkX builds an in-memory directed graph for one run; it is derived data and is not stored in MongoDB. One indexed query retrieves the run's ordered events. If a parent ID is absent from that run, a single batched ID lookup distinguishes a reference to another run from a genuinely missing parent.

Each event becomes a stable node keyed by its event ID. Node data includes the label, event type, status, sequence number, timestamp, duration, error indicator, and small scalar metadata useful to the UI. Inputs and outputs remain available through `/events` and are not copied into graph nodes. Each existing `parent_event_id` becomes a directed dependency edge. Sequence order is used for stable display and failure ordering; it never creates an edge by itself. Nodes and edges use React Flow's `id`/`type`/`data` and `source`/`target` fields; the browser can add positions during layout.

The graph validator reports duplicate IDs, missing and cross-run parents, self references, invalid event fields, and cycles. Invalid references are not repaired and cyclic edges are retained for inspection. For DAGs, statistics include roots, leaves, branching points, weakly connected component count, a deterministic topological order, and longest dependency depth. Depth is `null` when a cycle prevents a DAG ordering. Empty and multi-root graphs are supported.

Failure detection records each event once when its status is `failed`, its type is `error`, or it carries structured error data. A failed run without an event-level failure gets a separate run-status signal. Categories are assigned only from explicit validation/tool/execution evidence; otherwise the category is `unknown_failure`. The first detected failure is selected by sequence number, with timestamps reported as context. This is recorded failure evidence, not proof of a true root cause. Successful `validation` events are not treated as failures.

Propagation analysis follows NetworkX graph descendants of each event-level failure. It reports direct and indirect dependency distance, actual downstream statuses, and which failure nodes reach each downstream event. Aggregate counts use unique downstream nodes, so overlap across failures is visible without double-counting. A descendant's dependency on a failure does not mean that it failed. Recovery is reported only when a successful recovery node and a subsequent successful task completion are recorded downstream; absence of a recovery event does not prove recovery was impossible. Error events remain visible even when a later recovery succeeds and the overall run status is `success`.

Example PowerShell requests after running the demo above:

```powershell
Invoke-RestMethod "http://localhost:8000/api/runs/$($demo.run_id)/graph" | ConvertTo-Json -Depth 10
Invoke-RestMethod "http://localhost:8000/api/runs/$($demo.run_id)/debug" | ConvertTo-Json -Depth 10
```

The graph response contains `run_id`, `graph_valid`, React Flow-friendly `nodes` and `edges`, calculated `statistics`, and `validation_issues`. The debug response includes run status and synthetic marker, graph summary, all failure records and the first detected failure, downstream event classifications, recovery evidence, and analysis limitations.

### Run a demo

With MongoDB configured and the API running, from PowerShell:

```powershell
$project = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/projects" `
  -ContentType "application/json" `
  -Body '{"name":"Demo workspace","description":"Synthetic trace examples"}'

$demo = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/demo/run" `
  -ContentType "application/json" `
  -Body (@{ project_id = $project.id; scenario = "error_with_recovery" } | ConvertTo-Json)

$demo
Invoke-RestMethod "http://localhost:8000/api/runs/$($demo.run_id)"
Invoke-RestMethod "http://localhost:8000/api/runs/$($demo.run_id)/events"
Invoke-RestMethod "http://localhost:8000/api/runs/$($demo.run_id)/summary"
```

The demo response includes `run_id`, `project_id`, `scenario`, final status, event count, actual wall-clock duration, and `synthetic: true`. The summary counts successful/failed events, tool calls, errors, and recoveries from persisted `trace_events` records.

## API endpoints

All routes use `/api`:

- `GET /api/health` — current database ping and API status (503 when the database is not reachable).
- `POST /api/projects` — create a project.
- `GET /api/projects?skip=0&limit=50` — recent-first project list.
- `GET /api/projects/{project_id}` — retrieve a project.
- `PATCH /api/projects/{project_id}` — update name and/or description.
- `DELETE /api/projects/{project_id}` — delete only when no runs reference the project.
- `POST /api/runs` — create a pending run record without inventing execution timestamps or events.
- `GET /api/runs?skip=0&limit=50&project_id=…&status=…` — paginated run retrieval and filters.
- `GET /api/runs/{run_id}` — retrieve a run.
- `GET /api/runs/{run_id}/events?skip=0&limit=200` — retrieve run events in sequence order, including event IDs and metadata.
- `GET /api/runs/{run_id}/summary` — compute event/tool/error/recovery counts from persisted data.
- `GET /api/runs/{run_id}/graph` — build and validate the run's NetworkX dependency graph.
- `GET /api/runs/{run_id}/debug` — combine failure detection, dependency propagation, and recovery evidence.
- `POST /api/demo/run` — execute one deterministic synthetic scenario and persist its run and events.

External trace ingestion, run comparison, and evaluation calculation are intentionally not implemented yet. A missing run or event is never presented as a successful execution.

Validation and API errors use a consistent `{ "error": { "code", "message", "details?" } }` response shape. Database errors return a generic 503 message without connection details. CORS allows the configured `FRONTEND_URL` origin; it is not open to arbitrary origins.
