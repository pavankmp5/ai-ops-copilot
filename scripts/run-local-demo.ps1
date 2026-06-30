$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPort = 8000
$frontendPort = 5173

function Test-PortListening {
    param([int]$Port)

    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $listener
}

function Test-HttpOk {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

if (-not (Test-Path (Join-Path $repoRoot ".venv\Scripts\python.exe"))) {
    throw "Backend venv is missing at .venv\Scripts\python.exe"
}

if (-not (Test-Path (Join-Path $repoRoot "frontend\node_modules"))) {
    throw "Frontend dependencies are missing. Run 'npm install' in frontend first."
}

$backendHealthy = Test-HttpOk "http://127.0.0.1:$backendPort/health"
if (-not $backendHealthy) {
    if (Test-PortListening -Port $backendPort) {
        throw "Port $backendPort is occupied by a non-healthy process. Resolve that before running the local demo."
    }

    $backendCmd = "cd /d `"$repoRoot`" && set DATABASE_URL=sqlite:///ai_ops_copilot_local_demo.db&& set ENVIRONMENT=development&& set CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173&& set STORAGE_PROVIDER=local&& .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $backendCmd -WindowStyle Hidden
    Start-Sleep -Seconds 6

    if (-not (Test-HttpOk "http://127.0.0.1:$backendPort/health")) {
        throw "Backend did not become healthy on port $backendPort."
    }
}

$frontendHealthy = Test-HttpOk "http://127.0.0.1:$frontendPort"
if (-not $frontendHealthy) {
    if (Test-PortListening -Port $frontendPort) {
        throw "Port $frontendPort is occupied by a non-healthy process. Resolve that before running the local demo."
    }

    $frontendRoot = Join-Path $repoRoot "frontend"
    Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort" -WorkingDirectory $frontendRoot -WindowStyle Hidden
    Start-Sleep -Seconds 6

    if (-not (Test-HttpOk "http://127.0.0.1:$frontendPort")) {
        throw "Frontend did not become reachable on port $frontendPort."
    }
}

Write-Output "Local demo ready"
Write-Output "Frontend: http://127.0.0.1:$frontendPort"
Write-Output "Backend:  http://127.0.0.1:$backendPort"
Write-Output "Docs:     http://127.0.0.1:$backendPort/docs"
