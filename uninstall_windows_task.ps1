#Requires -Version 5.1
# Run: powershell -ExecutionPolicy Bypass -File .\uninstall_windows_task.ps1

$ErrorActionPreference = 'Stop'
$taskName = 'FitBook_SCRAPE_SESSIONS'

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed scheduled task (if existed): $taskName"
