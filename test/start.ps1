param([int]$Port=8090)
$ErrorActionPreference='Stop'
$dashboardRoot=$PSScriptRoot
try { $state=Invoke-RestMethod "http://127.0.0.1:$Port/api/state" -TimeoutSec 2; if ($state.collector -eq 'serial') { Write-Output "Dashboard already running: http://127.0.0.1:$Port"; exit 0 } } catch {}
$pythonChoices=@("$env:LOCALAPPDATA/Programs/Python/Python312/python.exe","C:/Users/PC/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
$pythonExe=$pythonChoices | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonExe) { $pythonExe=(Get-Command python -ErrorAction Stop).Source }
New-Item -ItemType Directory -Force "$dashboardRoot/.runtime" | Out-Null
Start-Process -FilePath $pythonExe -ArgumentList @('-u',"`"$dashboardRoot/server.py`"",'--port',$Port) -WorkingDirectory $dashboardRoot -WindowStyle Hidden -RedirectStandardOutput "$dashboardRoot/.runtime/server.log" -RedirectStandardError "$dashboardRoot/.runtime/server-error.log"
Write-Output "Dashboard: http://127.0.0.1:$Port"
Write-Output "Reserved LAN URL: http://192.168.0.100:$Port (requires that address on the wired NIC)"
Write-Output 'Close other COM5/COM8 serial tools before sampling.'
