#Requires -Version 5.1
# Run: powershell -ExecutionPolicy Bypass -File .\install_windows_reset_task.ps1
# Creates a task: every Monday 08:00 (local time), run scrape_fitbook.py --reset-baseline

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$taskName = 'FitBook_RESET_BASELINE'
$projectRoot = $PSScriptRoot
$pyScript = Join-Path $projectRoot 'scrape_fitbook.py'

if (-not (Test-Path -LiteralPath $pyScript)) {
    throw "scrape_fitbook.py not found: $pyScript"
}

$python = (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $python) {
    throw 'python.exe not in PATH. Install Python and add to PATH.'
}

function Get-NextMondayAt8 {
    $now = Get-Date
    $daysUntilMonday = ((1 - [int]$now.DayOfWeek + 7) % 7)
    if ($daysUntilMonday -eq 0) {
        $candidate = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day -Hour 8 -Minute 0 -Second 0
        if ($now -lt $candidate) {
            return $candidate
        }
        $daysUntilMonday = 7
    }
    $nextMonday = $now.Date.AddDays($daysUntilMonday)
    return Get-Date -Year $nextMonday.Year -Month $nextMonday.Month -Day $nextMonday.Day -Hour 8 -Minute 0 -Second 0
}

$firstRun = Get-NextMondayAt8
$longDuration = [TimeSpan]::FromDays(3649)

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$pyScript`" --reset-baseline" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday `
    -At '08:00' `
    -WeeksInterval 1

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'FitBook reset scan baseline every Monday 08:00' `
    -Force | Out-Null

Write-Host "OK: Scheduled task '$taskName' created."
Write-Host "Runs every Monday at 08:00 (local PC time)."
Write-Host "Next run (approx): $firstRun"
Write-Host "Python: $python"
Write-Host "To remove: powershell -ExecutionPolicy Bypass -File .\uninstall_windows_reset_task.ps1"
