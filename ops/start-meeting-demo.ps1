param([int]$Port = 8220, [switch]$PrepareOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Create this worktree virtual environment first: python -m venv .venv' }
$env:DJANGO_ENV = 'development'
$env:DJANGO_DEBUG = 'true'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
$env:ESEPTEP_DEMO_MODE = '1'
$env:PLAN_AI_ENABLED = '0'
$env:DJANGO_DB_PATH = Join-Path $root 'meeting-demo.sqlite3'
$env:DJANGO_PRIVATE_MEDIA_ROOT = Join-Path $root 'meeting-demo-private-media'
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; no seed or server started.' }
& $python manage.py seed_meeting_demo --confirm-isolated
if ($LASTEXITCODE -ne 0) { throw 'Demo preparation refused; existing data not reset.' }
Write-Host "Open http://127.0.0.1:$Port/projects/upload/ (manual demo; OpenAI disabled)"
if (-not $PrepareOnly) { & $python manage.py runserver "127.0.0.1:$Port" --noreload }
