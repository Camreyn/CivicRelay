$ErrorActionPreference = 'Stop'
$python = if ($env:CRM_PROTON_PYTHON) { $env:CRM_PROTON_PYTHON } else { 'C:\Python313\python.exe' }
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
$desktop = Join-Path $PSScriptRoot 'connector\desktop.py'
if (-not [IO.Path]::IsPathRooted($python) -or -not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'Python 3.13 with Tkinter is required. See docs/SETUP.md.' }
# Explicitly launched interactive setup: credentials stay inside its local form.
Start-Process -FilePath $pythonw -ArgumentList @('-E','-s','-S',('"'+$desktop+'"'),'setup') -WorkingDirectory $PSScriptRoot -WindowStyle Normal
