$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

& ".\.venv\Scripts\Activate.ps1"

if (-not (Test-Path ".env")) {
    Write-Host ".env not found. Copy .env.example to .env and fill in Slack values first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting Slack SLA bot..." -ForegroundColor Green
python app.py
