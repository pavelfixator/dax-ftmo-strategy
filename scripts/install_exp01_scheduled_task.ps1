# Register Windows Scheduled Task for Experiment #0.1 orchestrator.
#
# Usage (PowerShell, current user — admin not required for user-scope task):
#   .\scripts\install_exp01_scheduled_task.ps1
#
# To unregister:
#   Unregister-ScheduledTask -TaskName "DAX-FTMO-Exp01" -Confirm:$false
#
# Task spec:
#   - Runs every 5 minutes
#   - Action: python orchestrator.py run (idempotent; no-op outside windows)
#   - User scope (no admin required)
#   - Hidden window
#   - Survives reboots (StartBoundary at next minute, StopBoundary 2026-05-08)
#
# Per Strategy v3.2 6-test schedule: Mon 27.4 - Thu 7.5.2026

$ErrorActionPreference = 'Stop'

$TaskName = "DAX-FTMO-Exp01"
$BotRoot = "C:\Users\AOS Server\dax-ftmo-bot"
$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "$BotRoot\scripts\exp01_orchestrator.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found at $PythonExe"
    exit 1
}
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Orchestrator not found at $ScriptPath"
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: python orchestrator.py run (idempotent)
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument """$ScriptPath"" run" -WorkingDirectory $BotRoot

# Trigger: every 5 min, no end (or until 2026-05-08)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$trigger.EndBoundary = (Get-Date "2026-05-08T23:00:00").ToString("yyyy-MM-ddTHH:mm:ss")

# Settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew

# Principal: current user, NOT highest privileges
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "DAX FTMO Experiment #0.1 swap measurement orchestrator (idempotent state machine, runs every 5 min)"

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null

Write-Output "Task '$TaskName' registered successfully."
Write-Output "  Action:      $PythonExe ""$ScriptPath"" run"
Write-Output "  Schedule:    every 5 min, ends 2026-05-08 23:00"
Write-Output "  User scope:  $env:USERDOMAIN\$env:USERNAME (current user)"
Write-Output ""
Write-Output "Verify:  Get-ScheduledTask -TaskName '$TaskName' | Select-Object State"
Write-Output "Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Output "Logs:    Event Viewer -> Windows Logs -> Application (filter: Source TaskScheduler)"
Write-Output ""
Write-Output "Manual test before scheduled fire:"
Write-Output "  $PythonExe ""$ScriptPath"" run --dry-run"
