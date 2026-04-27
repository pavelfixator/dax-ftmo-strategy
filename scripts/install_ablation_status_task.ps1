# Register Windows Scheduled Task for hourly ablation status push to Discord.
#
# Usage (PowerShell, current user — admin not required):
#   .\scripts\install_ablation_status_task.ps1
#
# To unregister (after ablation completes):
#   Unregister-ScheduledTask -TaskName "DAX-Ablation-Status-1h" -Confirm:$false
#
# Spec:
#   - Runs every 1 hour starting at next hour
#   - Action: python ablation_status_push.py
#   - Reads experiments/extended_ablation/progress.json, posts to #system-health
#   - User scope, hidden window, ~1s execution

$ErrorActionPreference = 'Stop'

$TaskName = "DAX-Ablation-Status-1h"
$BotRoot = "C:\Users\AOS Server\dax-ftmo-bot"
$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "$BotRoot\scripts\ablation_status_push.py"

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

# Action
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument """$ScriptPath""" -WorkingDirectory $BotRoot

# Trigger: every 1 hour starting at next full hour + 1 minute
$now = Get-Date
$nextHour = $now.Date.AddHours($now.Hour + 1).AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $nextHour -RepetitionInterval (New-TimeSpan -Hours 1)

# Settings — short execution time limit to avoid stuck instances
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Posts ablation progress snapshot to Discord #system-health every 1h. Auto-unregister after ablation completes."

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null

Write-Output "Task '$TaskName' registered successfully."
Write-Output "  Action:      $PythonExe ""$ScriptPath"""
Write-Output "  First fire:  $nextHour"
Write-Output "  Interval:    every 1 hour"
Write-Output ""
Write-Output "Manual test:  $PythonExe ""$ScriptPath"" --dry-run"
