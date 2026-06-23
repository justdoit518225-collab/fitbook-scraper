#Requires -Version 5.1
# Run: powershell -ExecutionPolicy Bypass -File .\install_windows_task.ps1
# 背景工作排程：每 N 分鐘執行 scrape_fitbook.py（無終端機視窗）

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$taskName = 'FitBook_SCRAPE_SESSIONS'
$projectRoot = $PSScriptRoot
$configPath = Join-Path $projectRoot 'config.json'

$python = (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $python) {
    throw 'python.exe not in PATH. Install Python and add to PATH.'
}

$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {
  $pythonw = $python
}
Set-Content -LiteralPath (Join-Path $projectRoot '.run_pythonw_path.txt') -Value $pythonw -Encoding UTF8 -NoNewline

$intervalMinutes = 2
if (Test-Path -LiteralPath $configPath) {
    try {
        $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -ne $cfg.quick_scan_interval_minutes) {
            $intervalMinutes = [int]$cfg.quick_scan_interval_minutes
        }
    } catch {
        Write-Warning '無法讀取 config.json，使用預設間隔 2 分鐘'
    }
}
if ($intervalMinutes -lt 1) { $intervalMinutes = 1 }
if ($intervalMinutes -gt 60) { $intervalMinutes = 60 }

$firstRun = (Get-Date).AddMinutes(1)
$longDuration = [TimeSpan]::FromDays(3649)

$pyScript = Join-Path $projectRoot 'scrape_fitbook.py'
$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "`"$pyScript`"" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At $firstRun `
    -RepetitionInterval (New-TimeSpan -Minutes $intervalMinutes) `
    -RepetitionDuration $longDuration

$settingsParams = @{
    AllowStartIfOnBatteries    = $true
    DontStopIfGoingOnBatteries = $true
    ExecutionTimeLimit         = (New-TimeSpan -Minutes 20)
    MultipleInstances          = 'IgnoreNew'
    StartWhenAvailable         = $true
    Hidden                     = $true
}
$settings = New-ScheduledTaskSettingsSet @settingsParams

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
    -Description "FitBook 快掃每 ${intervalMinutes} 分鐘（完全背景）" `
    -Force | Out-Null

Write-Host "OK: 已建立背景工作排程 '$taskName'（無終端機視窗）"
Write-Host "執行：pythonw.exe scrape_fitbook.py"
Write-Host "間隔：每 $intervalMinutes 分鐘"
Write-Host "取消：powershell -ExecutionPolicy Bypass -File .\uninstall_windows_task.ps1"
