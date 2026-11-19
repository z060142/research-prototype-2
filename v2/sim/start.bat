@echo off
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv not found. Install: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  pause
  exit /b 1
)
uv run python run.py --n 4000 --md results_lock.md --json results_lock.json
pause
