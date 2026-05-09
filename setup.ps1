$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found on PATH. Please install Python 3.11+ first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item ".env.example" ".env"
    Write-Host "Please open .env and fill in your Slack tokens and IDs." -ForegroundColor Yellow
}

Write-Host "Initializing database..."
python scripts/init_db.py

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  .\run_bot.ps1"
Write-Host "  .\run_dashboard.ps1"
