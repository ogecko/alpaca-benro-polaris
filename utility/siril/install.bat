@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Siril Scripts Installer
REM
REM  Copies the five .py scripts sitting in this same folder
REM  into %APPDATA%\Siril Scripts, so Siril can find and link
REM  to them automatically.
REM
REM  Usage: just double-click this file. It must be placed in
REM  the same folder as the .py scripts.
REM ============================================================

set "SOURCE_DIR=%~dp0"
set "DEST_DIR=%APPDATA%\siril\scripts"

echo.
echo Siril Scripts Installer
echo ------------------------
echo Source: %SOURCE_DIR%
echo Destination: %DEST_DIR%
echo.

REM --- Check there are .py files to copy ---
dir /b "%SOURCE_DIR%*.py" >nul 2>&1
if errorlevel 1 (
    echo ERROR: No .py files found in:
    echo   %SOURCE_DIR%
    echo Make sure install.bat is placed in the same folder as the scripts.
    echo.
    pause
    exit /b 1
)

REM --- Create destination folder if it doesn't exist ---
if not exist "%DEST_DIR%\" (
    echo Destination folder not found - creating it...
    mkdir "%DEST_DIR%"
)

REM --- Copy the scripts ---
echo Copying scripts...
xcopy "%SOURCE_DIR%*.py" "%DEST_DIR%\" /Y /I /Q

if errorlevel 1 (
    echo.
    echo ERROR: Copy failed. Please check permissions and try again.
    pause
    exit /b 1
)

REM --- Verify five files were copied ---
set /a count=0
for %%F in ("%DEST_DIR%\*.py") do set /a count+=1

echo.
echo Copied !count! file^(s^) to "%DEST_DIR%".

if !count! LSS 5 (
    echo WARNING: Expected 5 script files but only found !count!.
    echo Please double-check this folder contains all five .py scripts.
) else (
    echo Installation complete. Siril should now detect the scripts.
)

echo.
pause