<#
.SYNOPSIS
  Create (or remove) a daily Windows scheduled task that runs "junkchecker clean" on a folder.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\schedule_task.ps1 -Folder "D:\Projects" -Mode recycle -Time 18:00
  powershell -ExecutionPolicy Bypass -File tools\schedule_task.ps1 -Folder "D:\Projects" -Mode zip -Dest "E:\JunkArchive" -Weekly Friday
  powershell -ExecutionPolicy Bypass -File tools\schedule_task.ps1 -Remove
#>
param(
    [string]$Folder,
    [ValidateSet("recycle", "move", "zip")][string]$Mode = "recycle",
    [string]$Dest = "",
    [string]$Time = "18:00",
    [string]$Weekly = "",
    [string]$TaskName = "JunkChecker clean",
    [switch]$Remove
)

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
    return
}
if (-not $Folder -or -not (Test-Path $Folder)) { throw "Folder not found: $Folder" }
if ($Mode -ne "recycle" -and -not $Dest) { throw "-Dest is required for -Mode $Mode" }

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root "dist\JunkChecker.exe"
$cliArgs = "clean `"$Folder`" --mode $Mode --yes --quiet"
if ($Dest) { $cliArgs += " --dest `"$Dest`"" }

if (Test-Path $exe) {
    # the windowed exe forwards CLI arguments to the command line interface
    $action = New-ScheduledTaskAction -Execute $exe -Argument $cliArgs -WorkingDirectory $root
} else {
    $py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = (Get-Command python.exe).Source }
    $action = New-ScheduledTaskAction -Execute $py -Argument "-m junkchecker $cliArgs" -WorkingDirectory $root
}
if ($Weekly) {
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekly -At $Time
} else {
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
}
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "JunkChecker: clean safe junk in $Folder ($Mode)" -Force | Out-Null
Write-Host "Scheduled '$TaskName': $($action.Execute) $($action.Arguments)"
Write-Host "Results are logged to $env:APPDATA\JunkChecker\logs\junkchecker.log"
