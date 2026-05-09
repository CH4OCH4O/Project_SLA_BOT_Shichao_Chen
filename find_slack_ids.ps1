$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running setup first..." -ForegroundColor Yellow
    & ".\setup.ps1"
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "Listing Slack channel and user IDs..." -ForegroundColor Green
python scripts/get_slack_ids.py
