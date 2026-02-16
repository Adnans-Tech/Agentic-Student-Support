@echo off
cls
echo ========================================
echo   ACE College Support System
echo   Starting Backend + Frontend
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    echo Please install Node.js 18+ and try again
    pause
    exit /b 1
)

echo [1/4] Checking environment setup...
if not exist .env (
    echo [WARNING] .env file not found. Creating from .env.example...
    copy .env.example .env >nul
    echo [INFO] Please update .env with your API keys before continuing
    pause
)

echo [2/4] Starting Backend Server...
cd /d "%~dp0"
start "ACE Backend Server" cmd /k "python app.py"
timeout /t 3 /nobreak >nul

echo [3/4] Starting Frontend Development Server...
cd frontend
start "ACE Frontend Server" cmd /k "npm run dev"

echo [4/4] Waiting for servers to start...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   Servers Started Successfully!
echo ========================================
echo.
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:5173
echo.
echo Opening browser...
start http://localhost:5173
echo.
echo ========================================
echo Close the terminal windows to stop servers
echo ========================================
pause
