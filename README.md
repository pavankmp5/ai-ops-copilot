# AI Ops Copilot

AI Ops Copilot is a full-stack demo application for secure dataset upload, role-based access control, auditability, and AI-assisted analysis.

## Stack

- Backend: FastAPI
- Frontend: React + Vite
- Database: SQLite for local/demo usage, PostgreSQL-ready for hosted scale
- Auth: JWT access tokens + refresh tokens
- RBAC: tenant-aware `admin` / `user` roles
- AI: prompt-based analytics with optional RAG enrichment and resilient local fallback

## What It Does

Users sign in through the React frontend, upload CSV datasets, and ask operational questions about those datasets. The backend validates uploads, stores metadata, enforces access control, records audit logs, and orchestrates the AI answer flow.

The system is designed to degrade gracefully:

- If the live LLM is available, it is used first.
- If the live LLM is unavailable, the backend returns a structured local fallback analysis.
- If RAG dependencies or indexed context are unavailable, the app still answers without retrieval context.

## Architecture

```text
React frontend
    |
    v
FastAPI backend
    |- Auth + RBAC
    |- Dataset upload + access control
    |- Audit logging
    |- Query orchestration
    |- Optional RAG retrieval
    |- LLM call with fallback
    |
    +--> SQLite
    +--> data/ CSV files
    +--> vector_db/ Chroma data
```

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

For local frontend development, use `frontend/.env.example` if you want to override the API URL at build time.

For Docker and Azure frontend hosting, runtime values are injected through `runtime-config.js`, so you do not need to rebuild the frontend just to change the backend URL.

## Local Development

### Backend

Recommended Python: `3.11` or `3.12`

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Optional RAG dependencies:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-rag.txt
```

### Frontend

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
cd frontend
npm install
npm run dev
```

### Smoke Test

```powershell
cd f:\Python_learning\ai_ops_copilot
.venv\Scripts\python.exe scripts\smoke_test.py
```

This checks:

- `/`
- `/health`
- `/readyz`
- `/auth/token`
- `/auth/me`
- `/datasets`

## Docker

### Local container run with Compose

```powershell
docker compose up --build
```

Services:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

The backend container stores uploaded files and vector data in mounted local folders:

- `./data`
- `./vector_db`
- `./logs`

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

- `ci.yml`
- runs on pull requests and pushes to `main`/`master`
- validates backend smoke test, frontend build, Docker image build, and container runtime health checks

- `deploy-azure.yml`
- runs automatically after `CI` succeeds for `main`/`master` and also supports manual dispatch
- deploys backend and frontend to Azure Container Apps
- performs post-deploy health checks on backend and frontend URLs

### Required GitHub Secrets for Azure Deployment

Add these repository secrets before running deployment:

- `AZURE_CREDENTIALS`
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
- A dedicated GitHub Actions workflow (`secret-scan.yml`) now scans commits/PRs for leaked secrets.

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

This lets you demo both analytics and broader copilot behavior from the same frontend.

### RAG Strategy

Current RAG behavior:

1. A CSV upload is stored and registered in the backend.
2. A background task prepares dataset overview, summary, and preview text.
3. If RAG dependencies are available, these documents are indexed into Chroma for that dataset.
4. On `/ask`, retrieval is filtered to the selected dataset.
5. Retrieved context is added to the prompt only when available.

This keeps retrieval scoped and demo-friendly instead of searching across unrelated datasets.

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
- `alice / alice123`
- `bob / bob123`
- `charlie / charlie123`

## Troubleshooting

### `node` or `npm` not found

Node may be installed but not in the current PowerShell session:

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
```

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

## Optional Future Extension

If you run out of hosted API credits later, you can add a local-model provider path as a follow-on enhancement. A practical next step would be routing fallback generation to a local OpenAI-compatible endpoint such as Ollama or another self-hosted model gateway. That is not wired in yet, but the current `local_fallback` branch gives you a clear insertion point for it.

## Next-Phase Hardening Roadmap

- Authentication: move seeded users to real user identities (managed IdP or your own user DB with password hashing + reset flow).
- Authorization: extend RBAC with tenant/project-scoped roles and admin audit actions.
- Session security: short-lived access tokens, rotating refresh tokens, revoke-on-password-change.
- Data security: encrypt sensitive uploads at rest and enforce strict per-tenant dataset isolation.
- LLM quality: add evaluation datasets, prompt/version tracking, and offline regression checks for answer quality.
