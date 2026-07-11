# StudyGame launcher (Windows PowerShell).
# Builds the frontend, then starts the API which also serves the app.
# Open http://localhost:8000 on this PC, or http://<this-PC-IP>:8000 on your iPad.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location "$root/frontend"
npm run build
Pop-Location

Write-Host "`nStarting StudyGame on http://0.0.0.0:8000 ..." -ForegroundColor Green
Write-Host "  This PC:  http://localhost:8000"
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -First 1).IPAddress
if ($ip) { Write-Host "  iPad/LAN: http://$ip`:8000" }
Write-Host ""

& "$root/.venv/Scripts/python.exe" -m uvicorn app.api.main:app --app-dir "$root/backend" --host 0.0.0.0 --port 8000
