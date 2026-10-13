param([Parameter(Mandatory=$true)][string]$Port,[Parameter(Mandatory=$true)][string]$Script,[Parameter(Mandatory=$true)][string]$Output,[int]$TimeoutSeconds=60)
$ErrorActionPreference='Stop'
$payload=[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Script)))
$frameId='LGD_RESULT_'+[Guid]::NewGuid().ToString('N')+'_'
$wire="python3 - <<'LGD_REMOTE_PY'`nimport base64,contextlib,io,json,traceback,zlib`ns=io.StringIO()`ne=io.StringIO()`nok=True`ntry:`n with contextlib.redirect_stdout(s),contextlib.redirect_stderr(e):`n  exec(compile(base64.b64decode('''`n"
for($i=0;$i -lt $payload.Length;$i+=76){$wire+=$payload.Substring($i,[Math]::Min(76,$payload.Length-$i))+"`n"}
$wire+="'''),'lgd_remote','exec'),{'__name__':'__main__'})`nexcept BaseException:`n ok=False`n e.write(traceback.format_exc())`nr=base64.b64encode(zlib.compress(json.dumps({'ok':ok,'stdout':s.getvalue(),'stderr':e.getvalue()}).encode())).decode()`nprint('$frameId'+r,flush=True)`nLGD_REMOTE_PY`n"
$serial=New-Object System.IO.Ports.SerialPort $Port,115200,'None',8,'One'
$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Encoding=[Text.Encoding]::UTF8
$serial.ReadBufferSize=1048576;$serial.WriteTimeout=30000
$buffer=New-Object Text.StringBuilder
try {
 $serial.Open()
 # This tool exclusively owns the logged-in test console. Cancel a leftover
 # command/heredoc after an interrupted RPC; systemd business is unaffected.
 $serial.Write([string][char]3+"`r")
 Start-Sleep -Milliseconds 180
 $serial.DiscardInBuffer()
 for($i=0;$i -lt $wire.Length;$i+=400){$serial.Write($wire.Substring($i,[Math]::Min(400,$wire.Length-$i)));Start-Sleep -Milliseconds 35;[void]$buffer.Append($serial.ReadExisting())}
 $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
 $result=$null
 while((Get-Date) -lt $deadline){
  [void]$buffer.Append($serial.ReadExisting())
  if($buffer.ToString() -match ('(?m)^'+[Regex]::Escape($frameId)+'([A-Za-z0-9+/=]+)\r?\n')){$result=$Matches[1];break}
  Start-Sleep -Milliseconds 75
 }
 if($null -eq $result){throw ('No completed result on '+$Port+'; tail='+$buffer.ToString().Substring([Math]::Max(0,$buffer.Length-1000)))}
 [IO.File]::WriteAllText($Output,$result,[Text.UTF8Encoding]::new($false))
 Write-Output ('Serial script completed on '+$Port+'; result='+$Output)
}finally{if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
