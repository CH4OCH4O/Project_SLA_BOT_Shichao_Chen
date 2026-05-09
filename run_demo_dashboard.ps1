$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "Initializing and seeding demo database..."
python scripts/init_db.py
python scripts/seed_demo_data.py

Write-Host "Starting Streamlit dashboard with demo data..." -ForegroundColor Green
streamlit run dashboard.py
