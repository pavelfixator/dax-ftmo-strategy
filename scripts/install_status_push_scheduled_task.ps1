# Register Windows Scheduled Task for 2-hourly status push to Discord #alerts.
#
# Usage (PowerShell, current user — admin not required for user-scope task):
#   .\scripts\install_status_push_scheduled_task.ps1
#
# To unregister:
#   Unregister-ScheduledTask -TaskName "DAX-Status-Push-2h" -Confirm:$false
#
# Task spec:
#   - Runs every 2 hours starting at next even hour
#   - Action: python status_push.py (idempotent, ~1s, no MT5)
#   - User scope (no admin required)
#   - Hidden window
#   - Survives reboots

$ErrorActionPreference = 'Stop'

$TaskName = "DAX-Status-Push-2h"
$BotRoot = "C:\Users\AOS Server\dax-ftmo-bot"
$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "$BotRoot\scripts\status_push.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found at $PythonExe"
    exit 1
}
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Status push script not found at $ScriptPath"
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Action: python status_push.py
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument """$ScriptPath""" -WorkingDirectory $BotRoot

# Trigger: every 2 hours, starting at next even-hour boundary +1 minute
$now = Get-Date
$nextEvenHour = $now.Date.AddHours([math]::Ceiling(($now.Hour + 0.0167) / 2) * 2)
if ($nextEvenHour -le $now) { $nextEvenHour = $nextEvenHour.AddHours(2) }
$trigger = New-ScheduledTaskTrigger -Once -At $nextEvenHour -RepetitionInterval (New-TimeSpan -Hours 2)

# Settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

# Principal: current user, NOT highest privileges
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Posts DAX bot health snapshot to Discord #alerts every 2h."

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null

Write-Output "Task '$TaskName' registered successfully."
Write-Output "  Action:      $PythonExe ""$ScriptPath"""
Write-Output "  First fire:  $nextEvenHour"
Write-Output "  Interval:    every 2 hours"
Write-Output "  User scope:  $env:USERDOMAIN\$env:USERNAME"
Write-Output ""
Write-Output "Verify:  Get-ScheduledTask -TaskName '$TaskName' | Select-Object State"
Write-Output "Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Output "Manual:  $PythonExe ""$ScriptPath"" --dry-run"
