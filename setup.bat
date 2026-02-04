@echo off
setlocal

REM SignalForge Windows setup script

where python >nul 2>&1
if %errorlevel% neq 0 (
  echo Python not found. Install Python 3.10+ from https://python.org first.
  exit /b 1
)

REM Create virtual environment
if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\activate

REM Upgrade pip
python -m pip install --upgrade pip

REM Install dependencies
pip install -r requirements.txt

REM Create .env if missing
if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example. Please edit it with your API keys.
)

REM Run the app
uvicorn app.main:app --host 127.0.0.1 --port 8000

endlocal
