# helper.ps1 - INTERNAL helper for platforms\win\setup.bat.
#
# You never need to run this yourself: setup.bat calls it for the jobs cmd.exe does badly
# (the firewall rules and scheduled task, the shortcut, stopping the running driver, checking that
# the driver came up). To install or update the Alpaca Driver, run setup.bat.
#
# Usage (by setup.bat):  helper.ps1 -Action <name> -Repo <install folder> [-TaskName <name>] [-Detail]
#
# Quiet by default, like setup.bat: only real problems are printed. -Detail (setup.bat -v) adds progress.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('stop_driver', 'elevated_setup', 'create_shortcut', 'wait_for_driver')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [string]$Repo,
    [string]$TaskName = 'StartupAlpacaDriver',
    [switch]$Detail,
    # Internal to elevated_setup, which starts a hidden elevated copy of itself:
    [switch]$Elevated,
    [string]$PwEnc,         # the account password, encrypted for this Windows account only (DPAPI)
    [string]$TaskUser,
    [string]$ResultFile
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# Progress messages, shown only with -Detail. Problems use Write-Host directly, so they always show.
function Say([string]$Message, [switch]$NoNewline) { if ($Detail) { Write-Host $Message -NoNewline:$NoNewline } }

function Get-DriverProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($Repo) -and $_.Name -match '^(python|pythonw|driver)\.exe$'
    }
}

switch ($Action) {

    # Stop a running driver (politely first) so its files are not locked during the update.
    'stop_driver' {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
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
            if ($_.Exception.Status -in 'ReceiveFailure', 'ConnectionClosed', 'Timeout') { $asked = $true }
        }
        if ($asked) {
            Say 'Asked the running driver to stop...'
            for ($i = 0; $i -lt 12; $i++) {
                Start-Sleep -Seconds 1
                if (-not (Get-DriverProcesses)) { break }
            }
        }
        foreach ($p in (Get-DriverProcesses)) {
            Say "Stopping driver process $($p.ProcessId)..."
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    # Automatic startup: the firewall rules and the start-at-boot task, the only things that need
    # administrator rights. The firewall rules belong here because a driver started by Task Scheduler
    # has no desktop, so Windows cannot show its "Allow access" popup and would just block it. (A driver
    # you start yourself does get that popup, so setup.bat does not touch the firewall without this.)
    # Everything else in setup.bat runs as the user, in its own window. Run normally this is the
    # launcher: it starts a hidden elevated copy of itself (Windows asks permission once, and no
    # extra window appears) and reports what that did. The elevated copy (-Elevated) does the work.
    'elevated_setup' {
        if (-not $Elevated) {
            $me    = [Security.Principal.WindowsIdentity]::GetCurrent()
            $admin = ([Security.Principal.WindowsPrincipal]$me).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            # setup.bat asks for the password up front and passes it here as -p (plain) or already encrypted.
            $blob  = $env:ABP_PW_ENC
            if (-not $blob -and $env:ABP_PW) { $blob = ConvertTo-SecureString $env:ABP_PW -AsPlainText -Force | ConvertFrom-SecureString }
            if (-not $blob) {
                Write-Host 'No password was given, so the driver will not start automatically at boot. Run setup.bat again to add it.'
                exit 4          # nothing was set up
            }
            if (-not $admin) { Write-Host 'Windows will now ask your permission (needed for automatic startup).' }
            $result = Join-Path $env:TEMP 'abp-elevated.txt'
            Remove-Item $result -ErrorAction SilentlyContinue
            # Start-Process joins its arguments with spaces, so anything that may contain a space is quoted.
            $q = { param([string]$Text) '"' + $Text + '"' }
            $childArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (& $q $PSCommandPath),
                           '-Action', 'elevated_setup', '-Repo', (& $q $Repo), '-TaskName', (& $q $TaskName),
                           '-TaskUser', (& $q $me.Name), '-ResultFile', (& $q $result), '-Elevated')
            $childArgs += @('-PwEnc', $blob)
            try {
                $child = Start-Process powershell -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList $childArgs
            } catch {
                Write-Host 'Windows permission was not given, so the firewall rules and automatic startup were skipped.'
                Write-Host 'The driver still works, but Windows may ask you to allow it through the firewall the first time it runs.'
                exit 2
            }
            if (Test-Path $result) {
                foreach ($line in (Get-Content $result)) {
                    if ($child.ExitCode -eq 0) { Say $line } elseif ($line -notmatch '^(Allowed|Task) ') { Write-Host $line }     # on failure show only the problems
                }
                Remove-Item $result -ErrorAction SilentlyContinue
            }
            exit $child.ExitCode
        }

        # ---- the elevated, hidden copy ----
        function Report([string]$Message) { Add-Content -Path $ResultFile -Value $Message }
        # If Windows asked for a different account's password to elevate, the task and the encrypted
        # password belong to the account that ran setup, not this one. Say so plainly.
        $self = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        if ($self -ne $TaskUser) {
            Report "Automatic startup was not set up: permission was given by a different account ($self) from the one running setup ($TaskUser). Run setup.bat from an administrator account."
            exit 3
        }
        $failed = $false
        try {
            # Rules are by port, not by program: the python.exe path changes whenever uv moves to a newer
            # Python, and program rules would then trigger the Windows Firewall popup all over again.
            Remove-NetFirewallRule -DisplayName 'Alpaca Benro Polaris Driver (TCP)', 'Alpaca Benro Polaris Driver (UDP)' -ErrorAction SilentlyContinue
            New-NetFirewallRule -DisplayName 'Alpaca Benro Polaris Driver (TCP)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80, 443, 5555, 5556, 10001 -Profile Any | Out-Null
            New-NetFirewallRule -DisplayName 'Alpaca Benro Polaris Driver (UDP)' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 32227, 5353 -Profile Any | Out-Null
            Report 'Allowed TCP 80,443,5555,5556,10001 and UDP 32227,5353 through Windows Firewall.'
        } catch {
            Report "Could not set up the firewall rules: $($_.Exception.Message)"
            $failed = $true
        }

        # Task Scheduler needs the account password to run the task whether or not anyone is logged
        # on. Unlike the manual steps this also removes the default 3 day run limit, and restarts the
        # driver if it ever crashes (the Windows counterpart of Restart=always).
        try {
            $pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR((ConvertTo-SecureString $PwEnc)))
            $py         = Join-Path $Repo '.venv\Scripts\python.exe'
            $main       = Join-Path $Repo 'driver\main.py'
            # NB: not $action - PowerShell variable names ignore case, so that would overwrite the -Action parameter.
            $taskAction = New-ScheduledTaskAction -Execute $py -Argument ('"' + $main + '"') -WorkingDirectory (Join-Path $Repo 'driver')
            $trigger    = New-ScheduledTaskTrigger -AtStartup
            $settings   = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                            -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
                            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
            Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger -Settings $settings `
                -User $TaskUser -Password $pw -RunLevel Limited -Force `
                -Description 'Starts the Alpaca Benro Polaris Driver at boot (created by setup.bat).' | Out-Null
            Report "Task '$TaskName' will start the driver at boot as $TaskUser."
        } catch {
            Report "Could not create the start-at-boot task: $($_.Exception.Message)"
            Report 'Check the password (blank passwords are not supported), then run setup.bat again.'
            $failed = $true
        }
        exit ([int]$failed * 3)
    }

    'create_shortcut' {
        $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Alpaca Benro Polaris Driver.lnk'
        $s   = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        $s.TargetPath       = Join-Path $Repo '.venv\Scripts\python.exe'
        $s.Arguments        = '"' + (Join-Path $Repo 'driver\main.py') + '"'
        $s.WorkingDirectory = Join-Path $Repo 'driver'
        $s.IconLocation     = Join-Path $Repo 'docs\images\abp-icon.ico'
        $s.Description      = 'Alpaca Benro Polaris Driver'
        $s.Save()
        Say "Created $lnk"
    }

    # Report whether the driver's REST API came up, rather than leaving that to guesswork. The first
    # start of a fresh install is slow (cold Python imports, virus scanning of the new files, and
    # generating the TLS certificates), so say what we are waiting for and show progress.
    'wait_for_driver' {
        Say 'Waiting for the driver to start...' -NoNewline
        for ($i = 0; $i -lt 90; $i++) {
            try {
                Invoke-RestMethod 'http://localhost:5555/management/apiversions' -TimeoutSec 2 | Out-Null
                Say ''
                Say 'The Alpaca Driver is running.'
                return
            } catch {
                Say '.' -NoNewline
                Start-Sleep -Seconds 2
            }
        }
        Write-Host ''
        Write-Host "The driver has not answered on port 5555 after 3 minutes. It may still be starting, or it may have failed: check $Repo\logs\alpaca.log."
    }
}
