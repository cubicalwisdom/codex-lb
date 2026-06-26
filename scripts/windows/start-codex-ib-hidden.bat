@echo off
setlocal

set "APP_DIR=H:\Opencode IDE\codex-ib\codex-lb"
set "LOG_DIR=%LOCALAPPDATA%\CodexIB"
set "LOG_FILE=%LOG_DIR%\codex-ib-startup.log"
set "HOST=127.0.0.1"
set "PORT=2455"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
cd /d "%APP_DIR%" || exit /b 1

echo [%date% %time%] Starting Codex IB from %APP_DIR% >> "%LOG_FILE%"
echo [%date% %time%] Codex IB URL: http://%HOST%:%PORT%/codexneo >> "%LOG_FILE%"

if exist "%APP_DIR%\.venv\Scripts\python.exe" (
  "%APP_DIR%\.venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT% >> "%LOG_FILE%" 2>&1
  exit /b %ERRORLEVEL%
)

where uv.exe >nul 2>nul
if %ERRORLEVEL%==0 (
  uv run python -m uvicorn app.main:app --host %HOST% --port %PORT% >> "%LOG_FILE%" 2>&1
  exit /b %ERRORLEVEL%
)

for %%U in ("%USERPROFILE%\.local\bin\uv.exe" "%USERPROFILE%\.cargo\bin\uv.exe") do (
  if exist "%%~U" (
    "%%~U" run python -m uvicorn app.main:app --host %HOST% --port %PORT% >> "%LOG_FILE%" 2>&1
    exit /b %ERRORLEVEL%
  )
)

echo [%date% %time%] ERROR: Could not find .venv\Scripts\python.exe or uv.exe. >> "%LOG_FILE%"
exit /b 1
