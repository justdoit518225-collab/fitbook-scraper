#Requires -Version 5.1
$taskName = 'FitBook_RESET_BASELINE'
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed scheduled task (if existed): $taskName"
