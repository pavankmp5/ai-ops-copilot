# AI Ops Copilot Demo Presentation Summary

## 1) Environment URLs

### Local (dev mode)
- Backend API: `http://127.0.0.1:8000`
- Backend Docs: `http://127.0.0.1:8000/docs`
- Frontend (Vite dev): `http://127.0.0.1:5173`

### Live (Docker on local machine)
- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:8000`
- Backend Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## 2) Important Commands (Quick Demo Ops)

### Start local backend
```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Start local frontend
```powershell
cd frontend
npm run dev
```

### Start Docker stack
```powershell
docker compose up -d --build
docker compose ps
```

### Health checks
```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:8000/readyz -UseBasicParsing
Invoke-WebRequest http://localhost:8080 -UseBasicParsing
```

### View runtime logs
```powershell
docker compose logs --tail 100 backend frontend
```

### Stop stack
```powershell
docker compose down
```

## 3) High-Level Architecture (HLD)

```text
React Frontend
   |
   |  JWT + REST
   v
FastAPI Backend (Modular Monolith)
   |- Auth + RBAC + Tenant Context
   |- Dataset Upload + Access Control
   |- Query Orchestrator
   |- Optional RAG Retrieval
   |- Audit Logging + Runtime Metrics
   |
   +--> PostgreSQL / SQLite (metadata, users, sessions, audit)
   +--> Blob/Local storage (dataset files)
   +--> Vector DB (Chroma) for retrieval context
   +--> OpenRouter LLM (with local fallback path)
```

## 4) Demo Workflow Diagrams

### A) Login + Session
```text
User -> Frontend -> POST /auth/token -> Backend
Backend -> validate credentials + issue JWT/refresh
Frontend <- tokens + user profile
Frontend -> GET /auth/me (token verification)
```

### B) Upload + Index
```text
User -> Frontend upload CSV
Frontend -> POST /upload-csv (JWT)
Backend:
  1) validate file
  2) dedupe by hash
  3) store metadata + access grants
  4) enqueue background indexing
Background:
  build overview/summary/preview docs
  push to vector store (if RAG available)
```

### C) Ask Flow (Dataset Mode)
```text
Frontend -> POST /ask {question, dataset_id}
Backend:
  1) RBAC + tenant access check
  2) read dataset
  3) retrieve RAG context (best-effort)
  4) call LLM
  5) fallback response if LLM unavailable
  6) persist chat + retrieval/audit
Frontend <- answer + source + latency + rag_used
```

## 5) Stability and Fix Summary

### Through latest committed baseline
- `3c5c8fe` Stable checkpoint before demo prep
- `82b5acb` RBAC hardening + persistent chat sessions
- `131efa6` Blob readiness diagnostics + CI guard
- `cac893a` Azure blob dependency readiness fix
- `b676633` Production repro check script

### Current pre-demo fixes (pending commit)
- Docker CORS origin support for `:8080` frontend.
- Dataset dedupe recovery when metadata exists but backing CSV is missing.
- RAG failure hardening: unexpected Chroma exceptions now degrade to empty context instead of breaking query flow.

## 6) Known Current Risk
- If Chroma metadata is corrupted or version-mismatched, indexing/retrieval can fail.
- Mitigation in place: query path now safely falls back without returning HTTP 500 from RAG exceptions.

## 7) Presentation Script (2-3 min)
1. Open frontend on `http://localhost:8080`.
2. Login as `admin/admin123`.
3. Upload a CSV.
4. Ask a dataset question.
5. Explain response metadata:
   - `answer_source` (`llm` or fallback)
   - `rag_used`
   - latency breakdown
6. Show `/system/status` and `/health` to demonstrate operability.
