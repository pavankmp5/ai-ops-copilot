# Local Dev Commands

Use these commands from the repository root.

## Backend

The backend should be started with the project virtualenv and a local SQLite database override:

```cmd
scripts\start-backend-local.cmd
```

Equivalent expanded command:

```cmd
cd /d F:\Python_learning\ai_ops_copilot
set DATABASE_URL=sqlite:///ai_ops_copilot_local_demo.db
set ENVIRONMENT=development
set CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
set STORAGE_PROVIDER=local
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Why this works:

- `app.main:app` is the correct ASGI target.
- Running `python -m uvicorn` from the repo root uses the project interpreter reliably.
- Overriding `DATABASE_URL` keeps local runs deterministic even if you later switch `.env` to another database backend.

## Frontend

Start the Vite frontend in its own terminal:

```cmd
scripts\start-frontend-local.cmd
```

Equivalent expanded command:

```cmd
cd /d F:\Python_learning\ai_ops_copilot\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## URLs

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
