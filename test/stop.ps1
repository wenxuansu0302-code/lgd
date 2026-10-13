$ErrorActionPreference='Stop'
$pidFile=Join-Path $PSScriptRoot '.runtime/server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'No dashboard PID recorded.'; exit 0 }
$dashboardPid=[int](Get-Content -LiteralPath $pidFile)
$process=Get-CimInstance Win32_Process -Filter "ProcessId=$dashboardPid"
$expectedCommandPath=((Join-Path $PSScriptRoot 'server.py').Replace('\','/') -replace '/+','/').ToLowerInvariant()
$actualCommandLine=if ($process) { ($process.CommandLine.Replace('\','/') -replace '/+','/').ToLowerInvariant() } else { '' }
if ($process -and $actualCommandLine.Contains($expectedCommandPath)) {
  $state=Invoke-RestMethod 'http://127.0.0.1:8090/api/state' -TimeoutSec 2
  if ($state.validation.running) { throw 'Validation is running; let automatic cleanup finish before stopping.' }
  Stop-Process -Id $dashboardPid
  Write-Output 'Dashboard stopped; the three device services were not stopped.'
} else { Write-Output 'Recorded PID is no longer this dashboard.' }
