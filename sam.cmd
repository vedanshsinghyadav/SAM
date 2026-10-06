@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%"
python -m src.sam.cli %*
endlocal
