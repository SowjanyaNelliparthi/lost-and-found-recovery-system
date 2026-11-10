@echo off
cd /d "%~dp0"

set "PYTHON=python"
python --version >nul 2>&1
if errorlevel 1 (
  set "PYTHON=py"
  py --version >nul 2>&1
  if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer, then try again.
    pause
    exit /b 1
  )
)

%PYTHON% -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo Flask is not installed yet. Connecting to download it...
  %PYTHON% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Could not install Flask. An internet connection is needed for this first-time setup.
    pause
    exit /b 1
  )
)

echo.
echo Starting the local app. It will choose an available browser address.
echo Internet is not needed while using the app.
echo Keep this window open. Press Ctrl+C to stop the app.
echo.
%PYTHON% app.py
if errorlevel 1 (
  echo.
  echo The app stopped because startup failed. Read the error above.
  pause
)
