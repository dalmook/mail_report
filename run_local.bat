@echo off
setlocal
if not exist .env (
  copy .env.example .env >nul
  echo [.env.example] copied to [.env]. Fill in secrets before first run.
)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
endlocal
