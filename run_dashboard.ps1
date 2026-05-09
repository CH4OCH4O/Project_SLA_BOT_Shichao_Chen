$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

& ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path "sla_bot.db")) {
    Write-Host "Database not found. Initializing database..."
    python scripts/init_db.py
}

Write-Host "Starting Streamlit dashboard..." -ForegroundColor Green
streamlit run dashboard.py
