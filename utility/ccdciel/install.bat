@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  CCDciel Scripts Installer (Alpaca Benro Polaris Driver)
REM
REM  Copies the Polaris*.py scripts sitting in this same folder
REM  into CCDciel's configuration folder (%LOCALAPPDATA%\ccdciel)
REM  as <name>.script, so they appear in CCDciel's Run Script list.
REM  Existing copies are replaced with the new versions.
REM
REM  Usage: just double-click this file. It must be placed in
REM  the same folder as the .py scripts.
REM  (Optional: install.bat <folder> installs into another folder.)
REM ============================================================

set "SOURCE_DIR=%~dp0"
set "DEST_DIR=%LOCALAPPDATA%\ccdciel"
if not "%~1"=="" set "DEST_DIR=%~1"

echo.
echo CCDciel Scripts Installer
echo -------------------------
echo Source: %SOURCE_DIR%
echo Destination: %DEST_DIR%
echo.

REM --- Check there are scripts to copy ---
dir /b "%SOURCE_DIR%Polaris*.py" >nul 2>&1
if errorlevel 1 (
    echo ERROR: No Polaris*.py scripts found in:
    echo   %SOURCE_DIR%
    echo Make sure install.bat is placed in the same folder as the scripts.
    echo.
    pause
    exit /b 1
)

REM --- CCDciel creates its folder the first time it runs ---
if not exist "%DEST_DIR%\" (
    echo ERROR: CCDciel's folder was not found:
    echo   %DEST_DIR%
    echo Start CCDciel once, close it, then run this installer again.
    echo.
    pause
    exit /b 1
)

REM --- Copy each script, renamed to .script ---
set /a count=0
for %%F in ("%SOURCE_DIR%Polaris*.py") do (
    copy /Y "%%~fF" "%DEST_DIR%\%%~nF.script" >nul
    if errorlevel 1 (
        echo ERROR: Could not copy %%~nxF. Please check permissions and try again.
        pause
        exit /b 1
    )
    echo   %%~nF.script
    set /a count+=1
)

echo.
echo Installed !count! script^(s^) to "%DEST_DIR%".
echo In CCDciel, open the Capture tab: the scripts are listed under Run Script.
echo (Restart CCDciel if it was running.)
echo.
pause
