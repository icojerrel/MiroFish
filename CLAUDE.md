# MiroFish - AI Coding Assistant Guide

## Project Overview

MiroFish is an AI Prediction Engine that uses multi-agent simulation to forecast outcomes from seed documents. Users upload documents (PDFs, text), the system builds a knowledge graph, generates thousands of AI agent personalities, runs a social simulation, then produces prediction reports.

**Tech Stack:**
- **Frontend**: Vue 3 + Vite + D3.js (port 3000)
- **Backend**: Python Flask + OpenAI SDK + Zep (memory graph) + CAMEL-OASIS (multi-agent) (port 5001)
- **Infrastructure**: Docker/Docker Compose, GitHub Actions

---

## Repository Structure

```
MiroFish/
├── backend/
│   ├── app/
│   │   ├── api/              # Flask blueprint route handlers
│   │   │   ├── graph.py      # /api/graph - project, ontology, graph tasks
│   │   │   ├── simulation.py # /api/simulation - entity, profile, sim execution
│   │   │   └── report.py     # /api/report - report generation, agent chat
│   │   ├── models/           # Data models (Project, Task)
│   │   ├── services/         # Core business logic
│   │   │   ├── graph_builder.py            # Zep graph construction
│   │   │   ├── zep_entity_reader.py        # Entity extraction/filtering
│   │   │   ├── ontology_generator.py       # Domain ontology from text
│   │   │   ├── oasis_profile_generator.py  # Agent personality generation
│   │   │   ├── simulation_config_generator.py
│   │   │   ├── simulation_runner.py        # OASIS simulation execution
│   │   │   ├── simulation_manager.py       # Simulation state management
│   │   │   ├── simulation_ipc.py           # Subprocess IPC
│   │   │   ├── report_agent.py             # ReACT report generation
│   │   │   ├── zep_graph_memory_updater.py
│   │   │   ├── zep_tools.py                # Zep query utilities
│   │   │   └── zep_entity_reader.py
│   │   ├── utils/            # Shared utilities
│   │   ├── config.py         # Config class with env var loading
│   │   └── __init__.py       # Flask app factory (create_app)
│   ├── scripts/              # Helper scripts
│   ├── uploads/              # File storage (gitignored)
│   ├── pyproject.toml        # Python dependencies (uv-managed)
│   ├── requirements.txt      # Alternative dependency list
│   └── run.py                # Backend entry point with config validation
├── frontend/
│   ├── src/
│   │   ├── api/              # Axios API client modules
│   │   │   ├── graph.js      # Graph API calls
│   │   │   ├── simulation.js # Simulation API calls
│   │   │   ├── report.js     # Report API calls
│   │   │   └── index.js      # Axios instance with interceptors
│   │   ├── components/       # Step-based workflow components
│   │   │   ├── Step1GraphBuild.vue     # Document upload + graph building
│   │   │   ├── Step2EnvSetup.vue       # Environment configuration
│   │   │   ├── Step3Simulation.vue     # Simulation setup and execution
│   │   │   ├── Step4Report.vue         # Report generation and display
│   │   │   ├── Step5Interaction.vue    # Agent conversation interface
│   │   │   ├── GraphPanel.vue          # D3.js knowledge graph visualization
│   │   │   └── HistoryDatabase.vue     # Project history management
│   │   ├── views/            # Page-level router views
│   │   │   ├── Home.vue      # Landing page
│   │   │   └── Process.vue   # Main workflow orchestration
│   │   ├── router/           # Vue Router configuration
│   │   ├── store/            # Reactive state (pendingUpload)
│   │   └── main.js           # Vue app entry point
│   ├── public/               # Static assets
│   ├── vite.config.js        # Dev server + API proxy to :5001
│   └── package.json
├── .env.example              # Required environment variables template
├── docker-compose.yml        # Ports: 3000 (frontend), 5001 (backend)
├── Dockerfile                # Multi-stage Python 3.11 + Node.js 18
├── package.json              # Root npm scripts
└── README-EN.md              # English documentation
```

---

## Development Setup

### Prerequisites
- Python 3.11-3.12
- Node.js 18+
- `uv` (Python package manager)
- Zep Cloud account + API key
- LLM API key (OpenAI-compatible endpoint)

### Environment Configuration
Copy `.env.example` to `.env` and fill in:
```bash
LLM_API_KEY=<your-llm-api-key>
LLM_BASE_URL=<openai-compatible-endpoint>
LLM_MODEL=<model-name>
ZEP_API_KEY=<your-zep-cloud-api-key>
```

### Install and Run
```bash
# Install all dependencies
npm run setup

# Run frontend + backend concurrently (recommended)
npm run dev

# Run individually
npm run backend    # Flask on port 5001
npm run frontend   # Vite on port 3000

# Production build
npm run build
```

### Docker
```bash
docker-compose up --build
```

---

## Architecture Patterns

### Backend

**Flask Factory Pattern** — `create_app()` in `backend/app/__init__.py` registers blueprints and initializes services.

**Service Layer** — Business logic lives in `backend/app/services/`. API routes are thin wrappers that call services and return JSON responses. Do not put business logic in route handlers.

**Manager Singletons** — Long-running state is held in manager singletons:
- `ProjectManager` — project lifecycle
- `TaskManager` — async task tracking with status/progress
- `SimulationManager` — simulation state
- `ReportManager` — report storage and retrieval

**Task-Based Async Pattern** — Long operations (graph building, simulation, report generation) are launched as background tasks tracked by `TaskManager`. Clients poll the task status endpoint. Endpoints that start background work return a `task_id` immediately.

**LLM Client** — Uses the OpenAI SDK with configurable `base_url`, so any OpenAI-compatible provider works. Client is configured from `Config` class.

**IPC for Simulation** — OASIS simulation runs as a subprocess. `simulation_ipc.py` handles inter-process communication between Flask and the OASIS process.

### Frontend

**Multi-Step Wizard** — The main workflow is Step1 → Step2 → Step3 → Step4 → Step5. `Process.vue` orchestrates which step is active.

**API Modules** — All backend calls go through `src/api/`. Never call `axios` directly in components; use the module functions.

**Polling Pattern** — Long-running tasks are polled via `setInterval` until the task status reaches `completed` or `failed`. Always clear intervals on component unmount.

**Store** — `src/store/` uses a simple reactive store (not Pinia/Vuex) for cross-component state like `pendingUpload`.

**D3 Graph** — `GraphPanel.vue` renders the knowledge graph using D3.js force simulation. Node/edge data comes from the Zep graph API.

---

## Naming Conventions

| Context | Convention | Example |
|---------|-----------|---------|
| Python functions/variables | snake_case | `build_graph()`, `api_key` |
| Python classes | PascalCase | `GraphBuilderService` |
| JS/Vue functions/variables | camelCase | `buildGraph()`, `apiKey` |
| Vue components (files) | PascalCase | `Step1GraphBuild.vue` |
| API routes | kebab-case | `/build-graph`, `/entity-reader` |
| Vue component names (in templates) | PascalCase | `<GraphPanel />` |

---

## API Route Reference

### Graph API (`/api/graph`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/graph/projects` | Create new project, upload documents |
| GET | `/api/graph/projects` | List all projects |
| POST | `/api/graph/ontology` | Generate domain ontology |
| POST | `/api/graph/build-graph` | Start graph building task |
| GET | `/api/graph/tasks/:id` | Poll task status |

### Simulation API (`/api/simulation`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/simulation/entity-reader` | Extract entities from graph |
| POST | `/api/simulation/create` | Create simulation config |
| POST | `/api/simulation/prepare` | Generate agent profiles |
| POST | `/api/simulation/run` | Start simulation execution |
| GET | `/api/simulation/status` | Poll simulation status |

### Report API (`/api/report`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/report/generate` | Start report generation task |
| GET | `/api/report/:id` | Retrieve generated report |
| POST | `/api/report/chat` | Chat with report agent |

---

## Key Dependencies

### Python
- **Flask 3.0** — web framework
- **openai** — LLM API client (unified interface for any compatible provider)
- **zep-cloud** — knowledge graph memory management
- **camel-ai + camel-oasis** — multi-agent simulation framework
- **PyMuPDF** — PDF parsing
- **pydantic 2** — data validation

### JavaScript
- **Vue 3** — frontend framework (Composition API)
- **Vue Router 4** — client-side routing
- **Axios** — HTTP client with retry interceptors
- **D3 7** — knowledge graph visualization
- **Vite 7** — build tool and dev server

---

## Testing

The project uses pytest with pytest-asyncio for backend testing.

```bash
cd backend
uv sync --extras dev
uv run pytest
```

No frontend tests are currently configured.

---

## Common Development Tasks

### Adding a New Backend Service
1. Create `backend/app/services/my_service.py` with a class
2. Add route handlers in the appropriate `backend/app/api/*.py` blueprint
3. Register any new blueprints in `backend/app/__init__.py`

### Adding a New API Endpoint
1. Add route in the appropriate blueprint (`graph.py`, `simulation.py`, `report.py`)
2. Add corresponding function in `frontend/src/api/` module
3. Keep route handlers thin — delegate to services

### Adding a New Workflow Step
1. Create `frontend/src/components/StepN<Name>.vue`
2. Register it in `Process.vue` and update step navigation logic
3. Add any new routes to `frontend/src/router/`

### Environment Variables
All configuration is loaded via `backend/app/config.py`. Add new env vars there and update `.env.example`. The `run.py` entrypoint validates required vars before starting Flask.

---

## Web Scraping Integration (Data Ingestion)

MiroFish integrates with **[Scrapling](https://github.com/icojerrel/Scrapling)** — an adaptive scraping framework with anti-bot bypass — to feed live web content into the knowledge graph pipeline.

### Data flow

```
URLs → ScraperService → clean text → ProjectManager.save_extracted_text()
                                              ↓
                                   existing graph build pipeline
```

### Fetch modes

| Mode | When to use |
|------|-------------|
| `auto` | Default — picks the right mode per domain heuristically |
| `basic` | Fast HTTP with TLS fingerprint spoofing (most public sites) |
| `stealthy` | Bypass Cloudflare, anti-bot, paywalls |
| `dynamic` | Full Playwright browser for JS-heavy SPAs |

### Scraper API routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/scraper/fetch` | Scrape 1–10 URLs, return clean text preview |
| POST | `/api/scraper/crawl` | Start async domain crawl (task-based) |
| POST | `/api/scraper/ingest` | Scrape URLs and append to project corpus |
| GET | `/api/scraper/tasks/:id` | Poll crawl task status |

### New files

| File | Purpose |
|------|---------|
| `backend/app/services/scraper_service.py` | Scrapling wrapper — fetch, crawl, HTML→text |
| `backend/app/api/scraper.py` | `/api/scraper` Flask blueprint |
| `frontend/src/api/scraper.js` | Frontend API module |
| `frontend/src/components/ScraperPanel.vue` | URL input UI with mode selector and progress |

### Using ScraperPanel in Step1

```vue
<!-- In Step1GraphBuild.vue, add after the file upload section: -->
<ScraperPanel :project-id="projectId" @ingested="onScraperIngested" />
```

### Per use case

| Use case | Recommended URLs to scrape |
|----------|---------------------------|
| Political intelligence | Reuters, AP, government press releases |
| Financial risk | SEC filings, central bank publications, Bloomberg |
| Crisis management | Emergency services sites, demographic databases |
| Competitive intel | Competitor investor pages, job boards, patent offices |
| Cybersecurity | CVE databases, threat intel feeds, vendor advisories |

### Installation

```bash
pip install scrapling
# For dynamic mode (JS-heavy sites):
playwright install chromium
```

---

## Canopy Integration (Enterprise Collaboration)

MiroFish integrates with **[Canopy](https://github.com/icojerrel/Canopy)** — a local-first, encrypted P2P workspace (Slack alternative built for the agentic era). This turns MiroFish into an enterprise platform where prediction reports and simulation signals are automatically shared with the team in a secure, self-hosted workspace.

### What gets posted to Canopy

| Event | Canopy message type |
|-------|-------------------|
| Report generation completed | `[task]` block with report summary |
| Simulation completed | `[signal]` block with final status |
| Knowledge graph built | `[signal]` block with graph metadata |

### Agent inbox (mention commands)

MiroFish registers as an agent in Canopy. Team members can @mention it:

| Command | Response |
|---------|----------|
| `@mirofish status` | List recent simulations |
| `@mirofish report <sim_id>` | Fetch report summary |
| `@mirofish help` | Show available commands |

### New files added for this integration

| File | Purpose |
|------|---------|
| `backend/app/services/canopy_service.py` | Canopy REST API client (post messages, signals, reports) |
| `backend/app/services/canopy_agent.py` | Background daemon polling Canopy inbox for @mentions |
| `backend/app/api/canopy.py` | `/api/canopy` blueprint (status, test, push-report) |
| `frontend/src/api/canopy.js` | Frontend API calls to Canopy endpoints |
| `frontend/src/components/CanopyPanel.vue` | Connection status panel + push buttons |

### Canopy API routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/canopy/status` | Connection status + config info |
| POST | `/api/canopy/test` | Post a test message to the channel |
| POST | `/api/canopy/push-report` | Manually push a report by `report_id` |

### Setup

1. Run Canopy: `python -m canopy` (default port 7770)
2. Create an API key: Canopy UI → Settings → API Keys
3. Copy the target channel ID from channel settings
4. Add to `.env`:

```bash
CANOPY_BASE_URL=http://localhost:7770
CANOPY_API_KEY=your_canopy_api_key_here
CANOPY_CHANNEL_ID=your_channel_id_here
CANOPY_POLL_INTERVAL=30   # inbox poll in seconds
```

5. Restart MiroFish backend — the inbox listener starts automatically
6. Use `<CanopyPanel />` in any Vue component to show connection status and push buttons

### Architecture notes

- **`CanopyService`** is instantiated per-request (stateless HTTP calls to Canopy's `/api/v1`)
- **Canopy inbox listener** runs as a background daemon thread; all LLM/DB work is done inside MiroFish, replies go back to Canopy via REST
- All Canopy calls are **non-fatal** — if Canopy is offline or not configured, MiroFish continues normally
- The integration is **opt-in**: no Canopy vars = no listener, no hooks fire

---

## Important Notes

- **uploads/** directory is gitignored — created automatically on first run
- **Zep graph IDs** are project-scoped; each project has its own Zep graph namespace
- **Simulation subprocess** — OASIS runs in a separate process; do not try to import OASIS modules directly into Flask request handlers
- **CORS** is enabled for frontend-backend communication; configured in `create_app()`
- **Vite dev proxy** — in development, `/api/*` requests from the frontend are proxied to `localhost:5001`
- The project is licensed under **AGPL-3.0**
