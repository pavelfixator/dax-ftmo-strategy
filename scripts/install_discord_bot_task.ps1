# Register Win Scheduled Task DAX-Discord-Bot-Listener.
# DON'T run this until DISCORD_BOT_TOKEN is set in .env.
#
# Usage (PowerShell, current user):
#   .\scripts\install_discord_bot_task.ps1
#
# Trigger: At system startup
# Restart on failure: 3x with 5min delay
#
# Manual test before scheduled register:
#   python scripts\run_discord_bot_daemon.py

$ErrorActionPreference = 'Stop'

$TaskName = "DAX-Discord-Bot-Listener"
$BotRoot = "C:\Users\AOS Server\dax-ftmo-bot"
$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "$BotRoot\scripts\run_discord_bot_daemon.py"

# Pre-flight: ensure DISCORD_BOT_TOKEN is set
$envFile = "$BotRoot\.env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found at $envFile"
    exit 1
}
$envText = Get-Content $envFile -Raw
if ($envText -notmatch "DISCORD_BOT_TOKEN=\S+") {
    Write-Error "DISCORD_BOT_TOKEN is empty in .env. Add token first, then re-run."
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found at $PythonExe"; exit 1
}
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Daemon script not found at $ScriptPath"; exit 1
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $PythonExe -Argument """$ScriptPath""" -WorkingDirectory $BotRoot

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Phase 1 Discord Bot listener for GO/SKIP signal reactions. Long-running daemon."

Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null

Write-Output "Task '$TaskName' registered (At system startup, restart 3x/5min on fail)."
Write-Output ""
Write-Output "Manual start now:"
Write-Output "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Output ""
Write-Output "Logs: $BotRoot\logs\discord_bot.log"
