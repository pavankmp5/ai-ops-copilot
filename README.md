# AI Ops Copilot

AI Ops Copilot is a full-stack demo application for secure dataset upload, role-based access control, auditability, and AI-assisted analysis.

## Stack

- Backend: FastAPI
- Frontend: React + Vite
- Database: SQLite for local/demo usage, PostgreSQL-ready for hosted scale
- Auth: JWT access tokens + refresh tokens
- RBAC: tenant-aware `admin` / `analyst` / `viewer` roles
- AI: prompt-based analytics with optional RAG enrichment and resilient local fallback

## What It Does

Users sign in through the React frontend, upload CSV datasets, and ask operational questions about those datasets. The backend validates uploads, stores metadata, enforces access control, records audit logs, and orchestrates the AI answer flow.

The system is designed to degrade gracefully:

- If the live LLM is available, it is used first.
- If the live LLM is unavailable, the backend returns a structured local fallback analysis.
- If RAG dependencies or indexed context are unavailable, the app still answers without retrieval context.

## Architecture

```text
React frontend (Vite SPA)
    |
    |  JWT + REST
    v
FastAPI backend (modular monolith)
    |- Auth + RBAC
    |- Dataset upload + access control
    |- Audit logging
    |- Query orchestration
    |- Conversation persistence
    |- Optional RAG retrieval
    |- LLM call with fallback
    |
    +--> SQLite / PostgreSQL
    +--> data/ local dataset files
    +--> vector_db/ Chroma data
```

Implementation blueprint:

- [Enterprise Architecture Blueprint](docs/architecture/enterprise_blueprint.md)

## Project Layout

```text
ai_ops_copilot/
|-- app/
|-- frontend/
|-- scripts/
|-- deploy/azure/
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- requirements-rag.txt
```

## Environment Variables

Use `.env.example` as the starting point for backend configuration.

Important backend variables:

- `ENVIRONMENT`
- `JWT_SECRET_KEY`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `LLM_MODEL`
- `LOG_JSON`
- `RAG_ENABLED`
- `CORS_ALLOWED_ORIGINS`

`OPENROUTER_API_KEY` is optional for local startup. If it is unset, the app still works and returns the built-in local fallback analysis path.

For local frontend development, use `frontend/.env.example` if you want to override the API URL at build time.

For Docker and Azure frontend hosting, runtime values are injected through `runtime-config.js`, so you do not need to rebuild the frontend just to change the backend URL.

## Quick Start

### Docker

This is the supported default path.

1. Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

2. Start the stack:

```powershell
docker compose up --build
```

3. Open the app:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Readiness: `http://localhost:8000/readyz`

The Compose setup uses SQLite by default and persists local runtime data in:

- `./data`
- `./vector_db`
- `./logs`

### Local Development

Recommended Python: `3.11` or `3.12`

Backend:

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv pip install --python .venv\Scripts\python.exe -r requirements-rag.txt
scripts\start-backend-local.cmd
```

Frontend:

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
cd frontend
npm install
cd ..
scripts\start-frontend-local.cmd
```

### Manual verification commands

Open a second terminal and verify the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/readyz
Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/token `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body 'username=admin&password=admin123'
```

Then open the frontend:

```text
http://127.0.0.1:5173
```

Recommended manual path:

1. Sign in as `admin / admin123`
2. Confirm datasets load
3. Upload a CSV
4. Ask one dataset question
5. Ask one general question
6. Confirm `answer_source`, `rag_used`, and `latency_ms`

### Smoke Test

```powershell
cd f:\Python_learning\ai_ops_copilot
.venv\Scripts\python.exe scripts\smoke_test.py
```

The smoke test forces a local SQLite configuration so it does not depend on a developer's personal `.env`.

This checks:

- `/`
- `/health`
- `/readyz`
- `/auth/token`
- `/auth/me`
- `/datasets`

## Docker

`docker-compose.yml` is the source of truth for local startup. The default stack runs:

- `backend`: FastAPI + SQLite-backed local persistence
- `frontend`: Nginx serving the built React app with runtime API configuration

Health model:

- `GET /health`: lightweight liveness
- `GET /readyz`: dependency-aware readiness
- Compose waits for backend readiness before starting the frontend

## Azure Hosting

Recommended host: **Azure Container Apps**

Why this is the best fit here:

- Native Docker container hosting
- Simple ingress and HTTPS
- Runtime env vars and secrets
- Health probe support
- Easier than AKS for a demo-ready production path

Deployment guidance lives in [deploy/azure/README.md](deploy/azure/README.md).

## CI/CD Pipelines

GitHub Actions workflows are configured in `.github/workflows`:

- `ci-backend.yml`
- runs on pull requests and pushes to `main`/`master`
- validates backend smoke test, frontend build, Docker image build, and container runtime health checks

- `deploy-azure.yml`
- runs automatically after `CI` succeeds for `main`/`master` and also supports manual dispatch
- deploys backend and frontend to Azure Container Apps
- performs post-deploy health checks on backend and frontend URLs

### Required GitHub Secrets for Azure Deployment

Add these repository secrets before running deployment:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINERAPPS_ENV`
- `AZURE_BACKEND_APP_NAME`
- `AZURE_FRONTEND_APP_NAME`
- `JWT_SECRET_KEY`
- `OPENROUTER_API_KEY`
- `DATABASE_URL`
- `AZURE_BLOB_CONNECTION_STRING`
- `AZURE_BLOB_CONTAINER`

### Secret Safety Notes

- Keep real keys only in local `.env` and GitHub Secrets.
- `.env` is already ignored by git and should never be committed.
- Avoid running `docker compose config` in shared logs because it prints resolved environment values.
- Use `docker compose config --no-interpolate` when you only need structural validation.
- A dedicated GitHub Actions workflow (`secret-scan.yml`) scans commits and pull requests for leaked secrets.

## API and UI Behavior

### Uploads

Uploads now happen from the frontend UI, but they still require the backend server.

That means:

- You do **not** need Swagger for uploads anymore.
- You **do** still need the FastAPI backend running, because the frontend posts the file to the backend API.

### Swagger

Swagger remains useful for:

- API inspection
- backup testing
- debugging auth and payloads

It is not the main user flow anymore.

### General Copilot Mode

The app now supports two question types:

- dataset-grounded questions through `/ask`
- general operational questions through `/chat`
- persistent threaded conversations through `/chat/sessions/*`

### Conversation APIs

Conversation persistence is now available for both dataset and general chat flows.

- `POST /chat/sessions`
  - creates a new session
- `GET /chat/sessions`
  - lists current user sessions
- `GET /chat/sessions/{session_id}`
  - returns session messages and retrieval events
- `POST /chat/sessions/{session_id}/messages`
  - appends a message to an existing session
  - body:
    - `question` (required)
    - `dataset_id` (optional, uses dataset-grounded mode when provided)

Both `/ask` and `/chat` also accept optional `session_id`; if omitted, a new session is auto-created.

This lets you demo both analytics and broader copilot behavior from the same frontend.

### RAG Strategy

Current RAG behavior:

1. **Multi-format Ingestion**: Supports `.csv`, `.pdf`, `.docx`, `.txt`, and `.md` files.
2. **Parser Architecture**:
   - `detector.py`: Identifies file type and MIME type.
   - `registry.py`: Resolves the appropriate parser for the file extension.
   - `parsers/`: Modular parsers for each format (e.g., `CsvParser`, `PdfParser`, `DocxParser`).
3. **Pipeline**:
   - Files are parsed into a `NormalizedDocument` with sections and metadata.
   - Background task chunks the normalized document using `chunking.py`.
   - Chunks are indexed into Chroma for retrieval-augmented generation.
4. **Scoping**: Retrieval is filtered to the selected dataset, ensuring scoped and relevant context.

This architecture keeps retrieval modular and supports expanding to new formats easily.

### Answer Source

Each answer returns:

- `answer_source`: `llm` or `local_fallback`
- `rag_used`: whether retrieval context was actually used
- `latency_ms`: total, RAG, and LLM timings

This makes demos easier because you can explain exactly where the result came from.

## Observability and Reliability

Built-in improvements:

- request IDs on every response
- request latency headers
- rate limit headers
- `/health` and `/readyz`
- `/system/status` for runtime/service visibility
- in-memory request metrics snapshot
- structured JSON logging support via `LOG_JSON=true`
- local fallback when the live LLM is unavailable
- background indexing after upload

## Demo Script

1. Start backend and frontend.
2. Open the React frontend.
3. Sign in as `admin / admin123`.
4. Show the system status panel.
5. Upload a CSV.
6. Show that the dataset appears in the dataset registry.
7. Ask a question.
8. Point out:
   - mode
   - answer source
   - RAG used / no context
   - latency
9. Mention that Swagger exists as a backup API console.

## Seeded Users

- `admin / admin123`
- `alice / alice123` (`analyst`)
- `bob / bob123` (`viewer`)
- `charlie / charlie123` (`analyst`)
- `nitin / nitin123` (`admin`)

## Troubleshooting

### `node` or `npm` not found

Node may be installed but not in the current PowerShell session:

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
```

### `uvicorn` fails locally

Use the repo-local launcher instead of a bare `uvicorn` command:

```powershell
scripts\start-backend-local.cmd
```

This ensures:

- the project virtualenv is used
- the ASGI target is `app.main:app`
- local startup uses the supported local SQLite path

If `uvicorn app.main:app --reload` still fails, the usual causes are:

- `uvicorn` is not on your shell `PATH`
- port `8000` is already occupied by another local process or Docker/WSL port forwarding

### Live LLM falls back every time

That usually means one of:

- `OPENROUTER_API_KEY` is missing
- outbound network access is blocked
- the provider endpoint is temporarily unavailable

The application is designed to keep responding with local fallback analysis instead of failing.

### RAG does not appear to contribute

Possible reasons:

- `RAG_ENABLED=false`
- `chromadb` / `sentence-transformers` are not installed
- the embedding model is not cached locally
- the uploaded dataset has not been indexed yet

## Room For Improvement

- Authentication: replace seeded local users with a real identity store or managed IdP.
- Authorization: extend RBAC to project- or dataset-scope policies without duplicating checks across routes.
- Ingestion: move background indexing to explicit job records with retry state and operator visibility.
- Storage: keep local storage for development, but standardize production on managed object storage.
- RAG: move from container-local Chroma to a shared vector store when multi-instance retrieval consistency matters.
- Security: move frontend token storage from `localStorage` to a safer cookie-based flow when the auth model is upgraded.
- Observability: add durable metrics, request dashboards, and audit log search for production support.
- Database migrations: the current app keeps lightweight in-process schema evolution in `init_db()`. Replacing it with Alembic or a similar migration tool is reasonable future work, but it would touch startup behavior and upgrade paths, so it was deferred in this hardening pass to avoid an unnecessary compatibility risk.
