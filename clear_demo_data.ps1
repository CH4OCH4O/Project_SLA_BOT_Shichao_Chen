$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "Clearing seeded demo SLA cases..." -ForegroundColor Green
python scripts/clear_demo_data.py
