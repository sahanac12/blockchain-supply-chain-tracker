@echo off
title Decentralized Proof-of-Location Console Launcher
echo =====================================================================
echo    🛡️  DECENTRALIZED PROOF-OF-LOCATION CONSOLE LAUNCHER
echo =====================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python and try again.
    echo.
    pause
    exit /b
)

:: Start the FastAPI backend API and launch browser
echo [1/2] Launching DCPoL Console in your default browser...
start http://127.0.0.1:8000

echo.
echo [2/2] Starting backend API and web server on http://127.0.0.1:8000...
echo.
echo =====================================================================
echo   To shut down the server, press Ctrl+C or close this window.
echo =====================================================================
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
