@echo off
setlocal
rem Resolve dependencies from this removable drive, whether E: or F:.
set "DEPS=%~dp0..\rml24_tx_console_integration_20261031\deps"
set "ORIGINAL_PYTHONPATH=%PYTHONPATH%"
set "QT_QPA_FONTDIR=%SystemRoot%\Fonts"
set "TX_PY="
if defined RML24_UI_PYTHON call :probe "%RML24_UI_PYTHON%"
if not defined TX_PY call :probe "D:\Miniconda3\python.exe"
if not defined TX_PY call :probe "D:\Anaconda\python.exe"
if not defined TX_PY call :probe "D:\radioconda\python.exe"
if not defined TX_PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined TX_PY call :probe "%%P"
if not defined TX_PY (
  echo No compatible Python with NumPy and PyQt5 found.
  echo Set RML24_UI_PYTHON to the full path of a compatible python.exe.
  pause
  exit /b 1
)
echo UI Python: %TX_PY%
"%TX_PY%" "%~dp0pc_console\app.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%

:probe
if not exist "%~1" exit /b
set "PYTHONPATH=%ORIGINAL_PYTHONPATH%"
"%~1" -c "import numpy; from PyQt5 import QtCore, QtWidgets" >nul 2>&1
if not errorlevel 1 (
  set "TX_PY=%~1"
  exit /b
)
set "PYTHONPATH=%DEPS%;%ORIGINAL_PYTHONPATH%"
"%~1" -c "import numpy; from PyQt5 import QtCore, QtWidgets" >nul 2>&1
if not errorlevel 1 (
  set "TX_PY=%~1"
  exit /b
)
set "PYTHONPATH=%ORIGINAL_PYTHONPATH%"
exit /b
