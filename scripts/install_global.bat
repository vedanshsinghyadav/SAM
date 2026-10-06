@echo off
setlocal enabledelayedexpansion

REM Determine repository root directory
set "CURRENT_DIR=%~dp0"
pushd "%CURRENT_DIR%.."
set "REPO_ROOT=%CD%"
popd

echo ======================================================================
echo                  SAM Global CLI Installer
echo ======================================================================
echo Repository Root: %REPO_ROOT%

REM Find target bin directory in user PATH
set "TARGET_BIN="
if exist "%LOCALAPPDATA%\Python\bin" (
    set "TARGET_BIN=%LOCALAPPDATA%\Python\bin"
) else if exist "%LOCALAPPDATA%\Microsoft\WindowsApps" (
    set "TARGET_BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
)

if "%TARGET_BIN%"=="" (
    echo [WARNING] Default Python/WindowsApps bin directory not found in PATH.
    echo Defaulting to %LOCALAPPDATA%\Microsoft\WindowsApps
    set "TARGET_BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
)

echo Target Global Bin: %TARGET_BIN%

REM Create sam.cmd in global bin
(
    echo @echo off
    echo setlocal
    echo set "SAM_HOME=%%SAM_HOME%%"
    echo if "%%SAM_HOME%%"=="" set "SAM_HOME=%REPO_ROOT%"
    echo set "PYTHONPATH=%%SAM_HOME%%;%%PYTHONPATH%%"
    echo python -m src.sam.cli %%*
    echo endlocal
) > "%TARGET_BIN%\sam.cmd"

if exist "%TARGET_BIN%\sam.ps1" del /f /q "%TARGET_BIN%\sam.ps1" 2>nul

echo [SUCCESS] Global command installed:
echo   - %TARGET_BIN%\sam.cmd
echo.
echo You can now run 'sam' from any Command Prompt or PowerShell!

REM Create Desktop shortcut without CMD if Desktop exists
if exist "%USERPROFILE%\Desktop" (
    python "%REPO_ROOT%\scripts\create_shortcut.py"
    copy /y "%REPO_ROOT%\launch_gui.vbs" "%USERPROFILE%\Desktop\SAM (Direct).vbs" >nul
)

echo ======================================================================
echo Installation complete! Try running: sam --version
echo ======================================================================
endlocal
