@echo off
rem ============================================================================
rem setup.bat - installs or updates the Alpaca Benro Polaris Driver on Windows 10/11.
rem
rem The Windows counterpart of platforms/raspberry_pi/setup.sh. Safe to re-run: it
rem only installs what is missing, reuses your existing checkout and branch, keeps
rem your data\ folder, and stashes (never discards) local edits to tracked files.
rem
rem Usage:  setup.bat [-p password] [-s] [-y] [-h] [branch]
rem
rem   -p password   Windows password for the account that runs the driver at boot
rem                 (default: prompted). Task Scheduler needs it to run the driver
rem                 whether or not you are logged on. Blank passwords are not supported.
rem   -s            Skip creating the start-at-boot task.
rem   -y            Unattended: never pause at the end.
rem   -h            Print this help and exit.
rem   branch        Git branch to install (default: the branch of an existing install,
rem                 otherwise main).
rem
rem Run it from the folder the driver should live in; it creates .\alpaca-benro-polaris
rem there, or updates the checkout it is run from. Administrator rights are requested
rem (UAC) because it adds Windows Firewall rules and a Task Scheduler task.
rem
rem Everything cmd.exe cannot do easily (scheduled task with no run-time limit,
rem shortcut, Git download fallback, stopping the running driver) lives in the
rem PowerShell block at the end of this file, which cmd.exe never reads.
rem ============================================================================
setlocal EnableExtensions DisableDelayedExpansion

set "BRANCH=main"
set "BRANCH_GIVEN="
set "ABP_PW="
set "SKIP_TASK="
set "ABP_NOPAUSE="
set "REPO_DIR=alpaca-benro-polaris"
set "REPO_URL=https://github.com/ogecko/alpaca-benro-polaris.git"
set "ABP_TASK=StartupAlpacaDriver"
set "ABP_SELF=%~f0"
set "ABP_CWD=%CD%"
set "ABP_ARGS=%*"

:parse
if "%~1"=="" goto parsed
if /i "%~1"=="-h" goto usage
if /i "%~1"=="/?" goto usage
if /i "%~1"=="-s" (set "SKIP_TASK=1" & shift & goto parse)
if /i "%~1"=="-y" (set "ABP_NOPAUSE=1" & shift & goto parse)
if /i "%~1"=="-p" (set "ABP_PW=%~2" & shift & shift & goto parse)
set "ARG=%~1"
if "%ARG:~0,1%"=="-" (echo Error: invalid option %~1. & goto usage_error)
set "BRANCH=%~1"
set "BRANCH_GIVEN=1"
shift
goto parse

:usage
echo.
echo Usage: setup.bat [-p password] [-s] [-y] [-h] [branch]
echo.
echo Options:
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
echo Usage: setup.bat [-p password] [-s] [-y] [-h] [branch]
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

rem --- 1. Prerequisites -----------------------------------------------------------------
echo ==SETUP== 1. Install Git and uv if they are missing.
rem Put the usual install locations on PATH for this run, so tools installed earlier (or
rem just now) are found even from shells that never picked up the new PATH.
set "PATH=%ProgramFiles%\Git\cmd;%USERPROFILE%\.local\bin;%PATH%"

where git >nul 2>&1
if errorlevel 1 (
    echo Installing Git...
    call :ps install_git
    where git >nul 2>&1
    if errorlevel 1 (
        echo Error: Git could not be installed. Install it from https://git-scm.com/download/win and re-run setup.bat.
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
rem Find an existing checkout: the one this script lives in, or the one we are run from,
rem before falling back to .\%REPO_DIR% beneath the current directory.
set "REPO="
for %%D in ("%~dp0." "%CD%") do if not defined REPO for /f "delims=" %%T in ('git -C "%%~D" rev-parse --show-toplevel 2^>nul') do if exist "%%T\driver\main.py" set "REPO=%%T"
rem NOTE: %VAR% inside a ( ) block is expanded once, before the block runs, so the steps below
rem are flat statements joined by goto, not blocks, wherever a value set earlier is used later.
if defined REPO goto found_repo
if exist "%CD%\%REPO_DIR%\.git" goto found_subdir
goto clone_repo

:found_repo
set "REPO=%REPO:/=\%"
echo Found existing checkout at %REPO% - fetching latest updates...
goto update_repo

:found_subdir
set "REPO=%CD%\%REPO_DIR%"
echo Directory exists - fetching latest updates...

:update_repo
rem Stop a running driver first: it locks files in .venv, which would break uv sync.
set "ABP_REPO=%REPO%"
call :ps stop_driver
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
echo Directory does not exist - cloning fresh copy...
set "REPO=%CD%\%REPO_DIR%"
git clone --branch "%BRANCH%" "%REPO_URL%" "%REPO%"
if errorlevel 1 goto fail
pushd "%REPO%"

:repo_ready
set "ABP_REPO=%REPO%"

if not exist pyproject.toml (
    echo Error: branch '%BRANCH%' doesn't have a pyproject.toml 1>&2
    echo This script only supports Alpaca Driver v2.2 Beta 6 or above. 1>&2
    echo Try a different version/branch, e.g.:  .\setup.bat dev2_2 1>&2
    goto fail_pop
)
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
    call :ps create_task
    schtasks /Query /TN "%ABP_TASK%" >nul 2>&1
    if not errorlevel 1 set "HAVE_TASK=1"
)

rem --- 6. Shortcut -----------------------------------------------------------------------------------
echo ==SETUP== 6. Create a desktop shortcut.
call :ps create_shortcut

rem --- 7. Start the driver ---------------------------------------------------------------------------
echo ==SETUP== 7. Start the Alpaca Driver.
if defined HAVE_TASK (
    schtasks /Run /TN "%ABP_TASK%" >nul
) else (
    start "Alpaca Benro Polaris Driver" /D "%REPO%\driver" "%REPO%\.venv\Scripts\python.exe" "%REPO%\driver\main.py"
)
call :ps wait_for_driver

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
if defined HAVE_TASK echo * Start the driver from a terminal with:  schtasks /Run /TN %ABP_TASK%   - stop it with Stop in Alpaca Pilot
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

rem --- Run one action of the PowerShell block below --------------------------------------------------
:ps
set "ABP_ACTION=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t = [IO.File]::ReadAllText($env:ABP_SELF); Invoke-Expression $t.Substring($t.IndexOf('#'+'#PS-BEGIN'))"
exit /b %errorlevel%

rem cmd.exe never gets past this line, so it never parses the PowerShell below.
exit /b

##PS-BEGIN
$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
$repo = $env:ABP_REPO
$task = $env:ABP_TASK

switch ($env:ABP_ACTION) {

    # Git for Windows: winget where it exists (built into Windows 11), else the official installer.
    'install_git' {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -eq 0) { break }
            Write-Host "winget could not install Git (exit code $LASTEXITCODE), downloading the installer instead..."
        }
        $rel   = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'setup.bat' }
        $asset = $rel.assets | Where-Object { $_.name -match '^Git-.*-64-bit\.exe$' } | Select-Object -First 1
        $exe   = Join-Path $env:TEMP $asset.name
        Invoke-WebRequest $asset.browser_download_url -OutFile $exe
        Start-Process $exe -ArgumentList '/VERYSILENT', '/NORESTART' -Wait
    }

    # Stop a running driver (politely first) so its files are not locked during the update.
    'stop_driver' {
        Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
        # The API rejects a PUT without a form content type (HTTP 400). Nothing is sent, and no wait
        # is needed, when no driver answers on the port.
        $asked = $false
        try {
            Invoke-RestMethod -Method Put -Uri 'http://localhost:5555/api/v1/telescope/0/action' -TimeoutSec 4 `
                -ContentType 'application/x-www-form-urlencoded' `
                -Body @{ Action = 'Polaris:StopDriver'; Parameters = ' '; ClientID = 1; ClientTransactionID = 1 } | Out-Null
            $asked = $true
        } catch {
            # The driver starts shutting down before it finishes replying, so a dropped reply still
            # means it was asked; only a refused connection or an HTTP error means it was not.
            if ($_.Exception.Status -eq 'ReceiveFailure' -or $_.Exception.Status -eq 'ConnectionClosed' -or $_.Exception.Status -eq 'Timeout') { $asked = $true }
        }
        if ($asked) {
            Write-Host 'Asked the running driver to stop...'
            for ($i = 0; $i -lt 12; $i++) {
                Start-Sleep -Seconds 1
                $alive = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($repo) -and $_.Name -match '^(python|pythonw|driver)\.exe$' }
                if (-not $alive) { break }
            }
        }
        $running = Get-CimInstance Win32_Process | Where-Object {
            $_.CommandLine -and $_.CommandLine.Contains($repo) -and $_.Name -match '^(python|pythonw|driver)\.exe$'
        }
        foreach ($p in $running) {
            Write-Host "Stopping driver process $($p.ProcessId)..."
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    # Start-at-boot task. Task Scheduler needs the account password to run it whether or not
    # anyone is logged on. Unlike the manual steps it also removes the default 3 day run limit,
    # and restarts the driver if it ever crashes (the Windows counterpart of Restart=always).
    'create_task' {
        # The identity, not %USERDOMAIN%\%USERNAME%: those env vars can name a network domain/workgroup that is not the account's real domain.
        $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $pw   = $env:ABP_PW
        if (-not $pw -and [Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
            $sec = Read-Host "Windows password for $user, needed to start the driver at boot (blank to skip)" -AsSecureString
            $pw  = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
        }
        if (-not $pw) {
            Write-Host 'No password given - not creating the start-at-boot task. Re-run .\setup.bat -p <password> to add it.'
            break
        }
        $py       = Join-Path $repo '.venv\Scripts\python.exe'
        $main     = Join-Path $repo 'driver\main.py'
        $action   = New-ScheduledTaskAction -Execute $py -Argument ('"' + $main + '"') -WorkingDirectory (Join-Path $repo 'driver')
        $trigger  = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
                        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        try {
            Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings `
                -User $user -Password $pw -RunLevel Limited -Force `
                -Description 'Starts the Alpaca Benro Polaris Driver at boot (created by setup.bat).' | Out-Null
            Write-Host "Task '$task' will start the driver at boot as $user."
        } catch {
            Write-Host "Could not create the task: $($_.Exception.Message)"
            Write-Host 'Check the password (blank passwords are not supported), then re-run .\setup.bat -p <password>.'
        }
    }

    'create_shortcut' {
        $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Alpaca Benro Polaris Driver.lnk'
        $s   = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        $s.TargetPath       = Join-Path $repo '.venv\Scripts\python.exe'
        $s.Arguments        = '"' + (Join-Path $repo 'driver\main.py') + '"'
        $s.WorkingDirectory = Join-Path $repo 'driver'
        $s.IconLocation     = Join-Path $repo 'docs\images\abp-icon.ico'
        $s.Description      = 'Alpaca Benro Polaris Driver'
        $s.Save()
        Write-Host "Created $lnk"
    }

    # Report whether the driver's REST API came up, rather than leaving that to guesswork.
    'wait_for_driver' {
        for ($i = 0; $i -lt 30; $i++) {
            try {
                Invoke-RestMethod 'http://localhost:5555/management/apiversions' -TimeoutSec 2 | Out-Null
                Write-Host 'The Alpaca Driver is running.'
                return
            } catch { Start-Sleep -Seconds 2 }
        }
        Write-Host "The driver did not answer on port 5555 within a minute. Check $repo\logs\alpaca.log."
    }
}
