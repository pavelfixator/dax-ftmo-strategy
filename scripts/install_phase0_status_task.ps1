# Register Win Scheduled Task for hourly Phase 0 backtest status push.
$ErrorActionPreference = 'Stop'

$TaskName = "DAX-Phase0-Status-1h"
$BotRoot = "C:\Users\AOS Server\dax-ftmo-bot"
$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$ScriptPath = "$BotRoot\scripts\phase0_status_push.py"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }

$action = New-ScheduledTaskAction -Execute $PythonExe -Argument """$ScriptPath""" -WorkingDirectory $BotRoot

$now = Get-Date
$nextHour = $now.Date.AddHours($now.Hour + 1).AddMinutes(2)
$trigger = New-ScheduledTaskTrigger -Once -At $nextHour -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Hourly Phase 0 backtest progress -> Discord #system-health"
Register-ScheduledTask -TaskName $TaskName -InputObject $task | Out-Null
Write-Output "Task '$TaskName' registered. First fire: $nextHour. Interval: 1h."
