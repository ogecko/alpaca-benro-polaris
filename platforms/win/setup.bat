@echo off
rem ============================================================================
rem setup.bat - installs or updates the Alpaca Benro Polaris Driver on Windows 10/11.
rem
rem The Windows counterpart of platforms/raspberry_pi/setup.sh. Safe to re-run: it
rem only installs what is missing, reuses your existing checkout and branch, keeps
rem your data\ folder, and stashes (never discards) local edits to tracked files.
rem
rem Usage:  setup.bat [-d folder] [-p password] [-s] [-y] [-h] [branch]
rem
rem   -d folder     Folder for the driver (default: %USERPROFILE%\alpaca-benro-polaris, which
rem                 is never synced by OneDrive, unlike Documents).
rem   -p password   Windows password for the account that runs the driver at boot
rem                 (default: prompted). Task Scheduler needs it to run the driver
rem                 whether or not you are logged on. Blank passwords are not supported.
rem   -s            Skip creating the start-at-boot task.
rem   -y            Unattended: never pause at the end.
rem   -h            Print this help and exit.
rem   branch        Git branch to install (default: the branch of an existing install,
rem                 otherwise main).
rem
rem It updates an existing install if it finds one (the checkout it is run from, or the folder
rem it is run in, or the default folder), otherwise it installs into the default folder.
rem Administrator rights are requested (UAC) because it adds Windows Firewall rules and a
rem Task Scheduler task.
rem
rem The few jobs cmd.exe does badly (scheduled task, shortcut, stopping the running driver) are done
rem by platforms\win\helper.ps1, which this script calls once the driver has been downloaded.
rem ============================================================================
setlocal EnableExtensions DisableDelayedExpansion

set "BRANCH=main"
set "BRANCH_GIVEN="
set "ABP_PW="
set "SKIP_TASK="
set "ABP_NOPAUSE="
set "REPO_DIR=alpaca-benro-polaris"
set "INSTALL_DIR=%USERPROFILE%\alpaca-benro-polaris"
set "DIR_GIVEN="
set "REPO_URL=https://github.com/ogecko/alpaca-benro-polaris.git"
set "ABP_TASK=StartupAlpacaDriver"
rem SHIFT (used to parse the options below) shifts %0 too, so anything derived from %0 must be
rem captured here, before parsing, and never read from %0 again.
set "ABP_SELF=%~f0"
set "ABP_HERE=%~dp0."
set "ABP_CWD=%CD%"
set "ABP_ARGS=%*"

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="-h" goto usage
if /i "%~1"=="/?" goto usage
if /i "%~1"=="-s" (set "SKIP_TASK=1" & shift & goto parse)
if /i "%~1"=="-y" (set "ABP_NOPAUSE=1" & shift & goto parse)
if /i "%~1"=="-d" (set "INSTALL_DIR=%~2" & set "DIR_GIVEN=1" & shift & shift & goto parse)
if /i "%~1"=="-p" (set "ABP_PW=%~2" & shift & shift & goto parse)
set "ARG=%~1"
if "%ARG:~0,1%"=="-" (echo Error: invalid option %~1. & goto usage_error)
set "BRANCH=%~1"
set "BRANCH_GIVEN=1"
shift
goto parse

:usage
echo.
echo Usage: setup.bat [-d folder] [-p password] [-s] [-y] [-h] [branch]
echo.
echo Options:
echo     -d ^<folder^>    Folder for the driver.
echo                    (default: %%USERPROFILE%%\alpaca-benro-polaris)
echo     -p ^<password^>  Windows password for the account that runs the driver at boot
echo                    (default: prompted). Needed by Task Scheduler.
echo     -s             Skip creating the start-at-boot task.
echo     -y             Unattended, do not pause at the end.
echo     -h             Print this help and exit.
echo.
echo     branch         Git branch to install, as a plain trailing argument.
echo                    (default: stay on the branch of an existing install, otherwise main)
echo.
exit /b 0

:usage_error
echo.
echo Usage: setup.bat [-d folder] [-p password] [-s] [-y] [-h] [branch]
exit /b 1

:parsed
echo == Alpaca Benro Polaris Windows Setup ===========================================.

rem --- Administrator rights (relaunch elevated via UAC if needed) ---------------------
net session >nul 2>&1
if errorlevel 1 (
    echo Administrator rights are needed to add firewall rules and the start-at-boot task.
    echo Requesting them now, please accept the User Account Control prompt...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd.exe -Verb RunAs -Wait -ArgumentList ('/c cd /d \"{0}\" && \"{1}\" {2}' -f $env:ABP_CWD, $env:ABP_SELF, $env:ABP_ARGS)"
    exit /b
)

rem --- Never run from inside the checkout we are about to update ------------------------------
rem git pull can replace this very file while cmd.exe is still reading it, and cmd.exe re-reads a
rem running batch file by byte offset, so an edit mid-run corrupts what it executes next. So a copy
rem of this script that lives in a checkout re-runs itself from a temporary copy instead.
if not defined ABP_ORIGIN set "ABP_ORIGIN=%ABP_HERE%"
if defined ABP_COPIED goto not_in_checkout
if not exist "%ABP_HERE%\..\..\driver\main.py" goto not_in_checkout
set "ABP_COPIED=1"
copy /y "%ABP_SELF%" "%TEMP%\abp_setup.bat" >nul
call "%TEMP%\abp_setup.bat" %*
set "ABP_RC=%errorlevel%"
del "%TEMP%\abp_setup.bat" >nul 2>&1
exit /b %ABP_RC%
:not_in_checkout

rem --- 1. Prerequisites -----------------------------------------------------------------
echo ==SETUP== 1. Install Git and uv if they are missing.
rem Put the usual install locations on PATH for this run, so tools installed earlier (or
rem just now) are found even from shells that never picked up the new PATH.
set "PATH=%ProgramFiles%\Git\cmd;%USERPROFILE%\.local\bin;%PATH%"

where git >nul 2>&1
if errorlevel 1 (
    echo Installing Git...
    winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
    where git >nul 2>&1
    if errorlevel 1 (
        echo Error: Git could not be installed automatically. Install it from https://git-scm.com/download/win and re-run setup.bat.
        goto fail
    )
) else (
    echo Git is already installed - skipping.
)

where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    where uv >nul 2>&1
    if errorlevel 1 (
        echo Error: uv could not be installed. See https://docs.astral.sh/uv/getting-started/installation/ and re-run setup.bat.
        goto fail
    )
) else (
    echo uv is already installed - skipping.
)

rem --- 2. Clone / update ------------------------------------------------------------------
echo ==SETUP== 2. Clone/Fetch the alpaca-benro-polaris software from Git-Hub.
rem An explicit -d folder wins. Otherwise find an existing checkout: the one this script lives in,
rem the one we are run from, .\%REPO_DIR% beneath the current directory, or the default folder.
set "REPO="
if defined DIR_GIVEN goto by_dir
for %%D in ("%ABP_ORIGIN%" "%CD%") do if not defined REPO for /f "delims=" %%T in ('git -C "%%~D" rev-parse --show-toplevel 2^>nul') do if exist "%%T\driver\main.py" set "REPO=%%T"
rem NOTE: %VAR% inside a ( ) block is expanded once, before the block runs, so the steps below
rem are flat statements joined by goto, not blocks, wherever a value set earlier is used later.
if defined REPO goto found_repo
if exist "%CD%\%REPO_DIR%\.git" goto found_subdir
:by_dir
if exist "%INSTALL_DIR%\.git" goto found_install_dir
goto clone_repo

:found_install_dir
set "REPO=%INSTALL_DIR%"
echo Found existing install at %REPO% - fetching latest updates...
goto update_repo

:found_repo
set "REPO=%REPO:/=\%"
echo Found existing checkout at %REPO% - fetching latest updates...
goto update_repo

:found_subdir
set "REPO=%CD%\%REPO_DIR%"
echo Directory exists - fetching latest updates...

:update_repo
pushd "%REPO%"
git diff --quiet HEAD
if errorlevel 1 (
    echo Local changes found - stashing them ^(get them back later with: git stash pop^).
    git -c user.name="setup.bat" -c user.email="setup@localhost" stash push -m "setup.bat auto-stash"
)
rem With no branch argument, stay on the branch this install is already on.
if not defined BRANCH_GIVEN for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH_GIVEN echo No branch given - staying on '%BRANCH%'.
git fetch --all
if errorlevel 1 goto fail_pop
git checkout "%BRANCH%"
if errorlevel 1 goto fail_pop
git pull
if errorlevel 1 goto fail_pop
goto repo_ready

:clone_repo
echo No existing install found - cloning a fresh copy into %INSTALL_DIR%...
set "REPO=%INSTALL_DIR%"
git clone --branch "%BRANCH%" "%REPO_URL%" "%REPO%"
if errorlevel 1 goto fail
pushd "%REPO%"

:repo_ready

rem Check the branch is supported BEFORE touching the running driver, and say so plainly (as setup.sh does).
if not exist pyproject.toml (
    echo Error: branch '%BRANCH%' doesn't have a pyproject.toml 1>&2
    echo This script only supports Alpaca Driver v2.2 Beta 6 or above. 1>&2
    echo '%BRANCH%' is either an older version or an unrelated branch. 1>&2
    echo Try a different version/branch, e.g.: 1>&2
    echo     setup.bat dev2_2 1>&2
    goto fail_pop
)
if not exist platforms\win\helper.ps1 (
    echo Error: branch '%BRANCH%' doesn't have platforms\win\helper.ps1 1>&2
    echo It is an early v2.2 build that predates this installer. Try a newer version/branch, e.g.: 1>&2
    echo     setup.bat dev2_2 1>&2
    goto fail_pop
)
rem Stop a running driver now: it locks files in .venv, which would break uv sync below.
call :helper stop_driver
if not exist data mkdir data
if not exist logs mkdir logs

rem --- 3. Python dependencies ---------------------------------------------------------------
echo ==SETUP== 3. Sync the python dependencies needed for the application with uv (creates %REPO%\.venv).
rem --managed-python: use a uv-managed Python 3.13 (downloaded if needed), so the driver never
rem depends on, or is broken by changes to, any other Python installed on this PC.
uv sync --no-dev --locked --managed-python --no-build-package numpy --no-build-package scipy
if errorlevel 1 (
    echo Error: uv sync failed. If it cannot download packages, see docs\troubleshooting.md A2.
    goto fail_pop
)

rem --- 4. Firewall ---------------------------------------------------------------------------
echo ==SETUP== 4. Allow the driver's network ports through Windows Firewall.
rem Rules are by port, not by program: the python.exe path changes whenever uv moves to a newer
rem Python, and program rules would then trigger the Windows Firewall popup all over again.
netsh advfirewall firewall delete rule name="Alpaca Benro Polaris Driver (TCP)" >nul 2>&1
netsh advfirewall firewall delete rule name="Alpaca Benro Polaris Driver (UDP)" >nul 2>&1
netsh advfirewall firewall add rule name="Alpaca Benro Polaris Driver (TCP)" dir=in action=allow protocol=TCP localport=80,443,5555,5556,10001 profile=any >nul
netsh advfirewall firewall add rule name="Alpaca Benro Polaris Driver (UDP)" dir=in action=allow protocol=UDP localport=32227,5353 profile=any >nul
echo Allowed TCP 80,443,5555,5556,10001 and UDP 32227,5353.

rem --- 5. Start at boot -------------------------------------------------------------------------
echo ==SETUP== 5. Set up a Task Scheduler task to start the Alpaca Driver at boot time.
set "HAVE_TASK="
if defined SKIP_TASK (
    echo Skipped, as requested with -s.
) else (
    call :helper create_task
    schtasks /Query /TN "%ABP_TASK%" >nul 2>&1
    if not errorlevel 1 set "HAVE_TASK=1"
)

rem --- 6. Shortcut -----------------------------------------------------------------------------------
echo ==SETUP== 6. Create a desktop shortcut.
call :helper create_shortcut

rem --- 7. Start the driver ---------------------------------------------------------------------------
echo ==SETUP== 7. Start the Alpaca Driver.
if defined HAVE_TASK (
    schtasks /Run /TN "%ABP_TASK%" >nul
) else (
    start "Alpaca Benro Polaris Driver" /D "%REPO%\driver" "%REPO%\.venv\Scripts\python.exe" "%REPO%\driver\main.py"
)
call :helper wait_for_driver

popd
echo.
echo -------------------------------------------------------------------
echo Alpaca Benro Polaris Setup Complete
echo.
echo You can:
echo * Access Alpaca Pilot via:      http://%COMPUTERNAME%   (or http://localhost)
echo * Start the driver by hand with: the "Alpaca Benro Polaris Driver" desktop shortcut
echo * Re-run this script at any time to update the driver (keeps your branch and data)
echo * View the logs in:             %REPO%\logs\alpaca.log
echo -------------------------------------------------------------------
goto end

:fail_pop
popd
:fail
echo.
echo Setup did not complete. Fix the problem above and re-run setup.bat.
if not defined ABP_NOPAUSE pause
exit /b 1

:end
if not defined ABP_NOPAUSE pause
exit /b 0

rem --- Run one action of platforms\win\helper.ps1 ------------------------------------------------
:helper
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\platforms\win\helper.ps1" -Action %~1 -Repo "%REPO%" -TaskName "%ABP_TASK%"
exit /b %errorlevel%
