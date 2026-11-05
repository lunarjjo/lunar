@echo off
REM lunar - one-click launcher (Windows)
REM Creates a private venv, installs pinned deps, downloads the model on
REM first run, then starts the console and opens the browser.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set PORT=8765
if not "%LUNAR_PORT%"=="" set PORT=%LUNAR_PORT%

where py >nul 2>nul
if errorlevel 1 (
  echo lunar needs Python 3.11+ - install from https://python.org then rerun.
  pause & exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [lunar] creating private python environment ^(.venv^)...
  py -3 -m venv .venv
  if errorlevel 1 ( echo venv creation failed & pause & exit /b 1 )
)
set VPY=.venv\Scripts\python.exe

if not exist .venv\.deps-stamp (
  echo [lunar] installing dependencies ^(first run only^)...
  "%VPY%" -m pip install --quiet -r requirements.txt
  if errorlevel 1 ( echo pip install failed - check network & pause & exit /b 1 )
  echo ok> .venv\.deps-stamp
)

if not exist voices\voices-v1.0.bin (
  echo [lunar] downloading the voice model ^(first run only, ~340 MB^)...
  "%VPY%" -m app.download fp32
  if errorlevel 1 ( echo model download failed & pause & exit /b 1 )
) else if not exist models\kokoro-v1.0.onnx (
  if not exist models\kokoro-v1.0.int8.onnx (
    echo [lunar] downloading the voice model ^(first run only^)...
    "%VPY%" -m app.download fp32
    if errorlevel 1 ( echo model download failed & pause & exit /b 1 )
  )
)

echo [lunar] live console: http://127.0.0.1:%PORT%/   ^(config: /config^)
start "" "http://127.0.0.1:%PORT%/"
"%VPY%" -m app --port %PORT%
pause
