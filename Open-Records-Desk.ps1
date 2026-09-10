param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$server = Join-Path $PSScriptRoot 'app\server.py'
$python = if ($env:CRM_PROTON_PYTHON) { $env:CRM_PROTON_PYTHON } else { 'C:\Python313\python.exe' }
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not [IO.Path]::IsPathRooted($python) -or -not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'Configure CRM_PROTON_PYTHON to an absolute Python 3.13 path with Tkinter/pythonw. See docs/SETUP.md.' }
$url = 'http://127.0.0.1:8766/'
$hasher = [Security.Cryptography.SHA256]::Create()
try { $installationId = -join ($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes((Resolve-Path -LiteralPath $PSScriptRoot).Path.ToLowerInvariant())) | ForEach-Object { $_.ToString('x2') }) } finally { $hasher.Dispose() }
function Test-OwnDashboard($status) {
    return $status.ok -and $status.app -eq 'CivicResultMaps Records Desk' -and $status.distribution -eq 'civic-records-desk' -and $status.installation_id -eq $installationId
}
$healthy = $false
$otherServer = $false
try { $status = Invoke-RestMethod -Uri ($url + 'health') -TimeoutSec 2; $healthy = Test-OwnDashboard $status; $otherServer = -not $healthy } catch { }
if ($otherServer) { throw 'Port 8766 belongs to a different or legacy dashboard. Stop only that identified dashboard before starting this checkout. No process was stopped.' }
if (-not $healthy) {
    Start-Process -FilePath $pythonw -ArgumentList @('-E', '-s', '-S', ('"' + $server + '"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $status = Invoke-RestMethod -Uri ($url + 'health') -TimeoutSec 1; if (Test-OwnDashboard $status) { $healthy = $true; break } } catch { }
    }
}
if (-not $healthy) { throw 'Records Desk did not start. Port 8766 may be occupied. No other process was stopped.' }
if (-not $NoBrowser) { Start-Process $url }
Write-Output 'Records Desk is ready at http://127.0.0.1:8766/'
