# helper.ps1 - INTERNAL helper for platforms\win\setup.bat.
#
# You never need to run this yourself: setup.bat calls it for the jobs cmd.exe does badly
# (creating the scheduled task and shortcut, stopping the running driver, checking that the
# driver came up). To install or update the Alpaca Driver, run setup.bat.
#
# Usage (by setup.bat):  helper.ps1 -Action <name> -Repo <install folder> [-TaskName <name>]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('stop_driver', 'create_task', 'create_shortcut', 'wait_for_driver')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [string]$Repo,
    [string]$TaskName = 'StartupAlpacaDriver'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

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
            Write-Host 'Asked the running driver to stop...'
            for ($i = 0; $i -lt 12; $i++) {
                Start-Sleep -Seconds 1
                if (-not (Get-DriverProcesses)) { break }
            }
        }
        foreach ($p in (Get-DriverProcesses)) {
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
        $py       = Join-Path $Repo '.venv\Scripts\python.exe'
        $main     = Join-Path $Repo 'driver\main.py'
        # NB: not $action - PowerShell variable names ignore case, so that would overwrite the -Action parameter.
        $taskAction = New-ScheduledTaskAction -Execute $py -Argument ('"' + $main + '"') -WorkingDirectory (Join-Path $Repo 'driver')
        $trigger    = New-ScheduledTaskTrigger -AtStartup
        $settings   = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
                        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        try {
            Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger -Settings $settings `
                -User $user -Password $pw -RunLevel Limited -Force `
                -Description 'Starts the Alpaca Benro Polaris Driver at boot (created by setup.bat).' | Out-Null
            Write-Host "Task '$TaskName' will start the driver at boot as $user."
        } catch {
            Write-Host "Could not create the task: $($_.Exception.Message)"
            Write-Host 'Check the password (blank passwords are not supported), then re-run .\setup.bat -p <password>.'
        }
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
        Write-Host "Created $lnk"
    }

    # Report whether the driver's REST API came up, rather than leaving that to guesswork. The first
    # start of a fresh install is slow (cold Python imports, virus scanning of the new files, and
    # generating the TLS certificates), so say what we are waiting for and show progress.
    'wait_for_driver' {
        Write-Host 'Waiting for the driver to start (the first start can take a couple of minutes)...' -NoNewline
        for ($i = 0; $i -lt 90; $i++) {
            try {
                Invoke-RestMethod 'http://localhost:5555/management/apiversions' -TimeoutSec 2 | Out-Null
                Write-Host ''
                Write-Host 'The Alpaca Driver is running.'
                return
            } catch {
                Write-Host '.' -NoNewline
                Start-Sleep -Seconds 2
            }
        }
        Write-Host ''
        Write-Host "The driver has not answered on port 5555 after 3 minutes. It may still be starting, or it may have failed: check $Repo\logs\alpaca.log."
    }
}
