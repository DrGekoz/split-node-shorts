@echo off
title Split Node Shorts
setlocal enabledelayedexpansion

echo.
echo   ==============================================
echo          SPLIT NODE SHORTS
echo       Vertical AI money-exploit shorts.
echo       True stories of people who beat the system.
echo   ==============================================
echo.

cd /d "F:\aaaaaVIBECODING\split node shorts"

echo [CHECK] Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Python not found! Please install Python 3.11+
    pause
    exit /b 1
) else (
    echo [OK] Python found
)

echo [CHECK] PocketTTS server (port 8769)...
curl -s -o nul http://127.0.0.1:8769/health 2>nul
if %errorlevel% neq 0 (
    echo [WARN] PocketTTS not running - attempting to start...
    start "PocketTTS" /B pocket-tts serve --port 8769
    timeout /t 15 /nobreak >nul
) else (
    echo [OK] PocketTTS server running
)

echo [CHECK] LM Studio (port 1234)...
curl -s -o nul http://localhost:1234/v1/models 2>nul
if %errorlevel% neq 0 (
    echo [WARN] LM Studio not running on port 1234
    echo        Start LM Studio first, then re-run this.
    pause
) else (
    echo [OK] LM Studio ready
)

echo.
echo All checks passed! Starting Split Node Shorts...
echo.
python split_node_shorts.py

echo.
echo Short complete! Press any key to exit.
pause >nul
