@echo off
cd /d "%~dp0.."
set DATABASE_URL=sqlite:///ai_ops_copilot_local_demo.db
set ENVIRONMENT=development
set CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
set STORAGE_PROVIDER=local
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
