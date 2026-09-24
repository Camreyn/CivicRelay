. (Join-Path $PSScriptRoot 'runtime-paths.ps1')

function Get-CivicRelayCommandPath([string]$Name) {
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    return $null
}

function Test-CivicRelayRuntime([string]$Kind, [string]$Executable) {
    if (-not (Test-CivicRelayExecutablePath $Executable) -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    # Do not trigger a Store installation through a Windows execution alias.
    if ($Executable -match '\\Microsoft\\WindowsApps\\') { return $false }
    try {
        if ($Kind -eq 'python') {
            if (-not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $Executable) 'pythonw.exe') -PathType Leaf)) { return $false }
            $result = & $Executable -B -E -s -S -c 'import sys,tkinter,ssl,sqlite3,ctypes; assert sys.version_info[:2] == (3,13); assert ctypes.sizeof(ctypes.c_void_p) == 8; tkinter.Tcl(); print(313)' 2>$null
            return $LASTEXITCODE -eq 0 -and "$result".Trim() -eq '313'
        }
        if ($Kind -eq 'node') {
            $result = & $Executable --version 2>$null
            return $LASTEXITCODE -eq 0 -and "$result" -match '^v(\d+)\.' -and [int]$Matches[1] -ge 22 -and (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $Executable) 'node_modules\npm\bin\npm-cli.js') -PathType Leaf)
        }
        if ($Kind -eq 'gh') {
            $result = & $Executable --version 2>$null
            return $LASTEXITCODE -eq 0 -and ($result -join ' ') -match '^gh version '
        }
    } catch { return $false }
    return $false
}

function Find-CivicRelayRuntime([string]$Kind, [hashtable]$Saved) {
    $environmentName = @{python='CRM_PROTON_PYTHON';node='RECORDS_DESK_NODE';gh='RECORDS_DESK_GH'}[$Kind]
    $explicit = [Environment]::GetEnvironmentVariable($environmentName, 'Process')
    if (-not $explicit) { $explicit = $Saved[$Kind] }
    if ($explicit) {
        if (Test-CivicRelayRuntime $Kind $explicit) { return $explicit }
        throw "The selected $Kind runtime is missing or incompatible. Check $environmentName and .local/runtime-paths.json; see docs/INSTALL.md. No alternate runtime was silently selected."
    }
    $candidates = @((Get-CivicRelayCommandPath ($Kind + '.exe')))
    if ($Kind -eq 'python') {
        $candidates += 'C:\Python313\python.exe'
        foreach ($base in @($env:LOCALAPPDATA, $env:ProgramFiles)) {
            if ($base) {
                $candidates += Join-Path $base 'Programs\Python\Python313\python.exe'
                $candidates += Join-Path $base 'Python313\python.exe'
            }
        }
        foreach ($key in @('HKCU:\Software\Python\PythonCore\3.13\InstallPath','HKLM:\Software\Python\PythonCore\3.13\InstallPath')) {
            if (Test-Path -LiteralPath $key) {
                $install = Get-ItemProperty -LiteralPath $key
                if ($install.ExecutablePath) { $candidates += $install.ExecutablePath }
                if ($install.'(default)') { $candidates += Join-Path $install.'(default)' 'python.exe' }
            }
        }
    } elseif ($Kind -eq 'node') {
        if ($env:ProgramFiles) { $candidates += Join-Path $env:ProgramFiles 'nodejs\node.exe' }
    } elseif ($Kind -eq 'gh') {
        if ($env:ProgramFiles) { $candidates += Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe' }
        if ($env:LOCALAPPDATA) { $candidates += Join-Path $env:LOCALAPPDATA 'Programs\GitHub CLI\gh.exe' }
    }
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-CivicRelayRuntime $Kind $candidate) { return $candidate }
    }
    return $null
}

function Find-CivicRelayBridge {
    # Inspect application binaries only: never open Bridge configuration or mail.
    $bases = @($env:ProgramFiles, ${env:ProgramFiles(x86)})
    if ($env:LOCALAPPDATA) { $bases += Join-Path $env:LOCALAPPDATA 'Programs' }
    foreach ($base in ($bases | Where-Object { $_ })) {
        foreach ($relative in @('Proton AG\Proton Mail Bridge\bridge-gui.exe','Proton\Proton Mail Bridge\bridge-gui.exe','Proton Mail Bridge\bridge-gui.exe')) {
            $file = Join-Path $base $relative
            if (Test-Path -LiteralPath $file -PathType Leaf) { return $file }
        }
    }
    return $null
}

function Get-CivicRelayInventory([string]$Root) {
    $saved = Read-CivicRelayRuntimePaths $Root
    return @{
        python = Find-CivicRelayRuntime 'python' $saved
        node = Find-CivicRelayRuntime 'node' $saved
        gh = Find-CivicRelayRuntime 'gh' $saved
        bridge = Find-CivicRelayBridge
        winget = Get-CivicRelayCommandPath 'winget.exe'
    }
}

function Get-CivicRelayInstallPlan([hashtable]$Inventory, [bool]$Mail, [bool]$GitHub) {
    if (-not $Inventory.python) { 'Python.Python.3.13' }
    if (-not $Inventory.node) { 'OpenJS.NodeJS.LTS' }
    if ($Mail -and -not $Inventory.bridge) { 'Proton.ProtonMailBridge' }
    if ($GitHub -and -not $Inventory.gh) { 'GitHub.cli' }
}

function Get-CivicRelayPackageArguments([string]$Id) {
    if (@('Python.Python.3.13','OpenJS.NodeJS.LTS','Proton.ProtonMailBridge','GitHub.cli') -cnotcontains $Id) {
        throw 'Package is not on the CivicRelay prerequisite allowlist.'
    }
    $arguments = @('install','--id',$Id,'--exact','--source','winget','--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    if ($Id -eq 'Python.Python.3.13') { $arguments += @('--scope','user','--custom','Include_tcltk=1 InstallLauncherAllUsers=0') }
    if ($Id -eq 'OpenJS.NodeJS.LTS') { $arguments += @('--scope','machine') }
    return $arguments
}

function Invoke-CivicRelayCommand([string]$Executable, [string[]]$Arguments, [string]$Label) {
    & $Executable @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit $LASTEXITCODE). Setup stopped; see docs/INSTALL.md. If Windows requests a restart, restart and rerun setup. Nothing will automatically retry or reboot."
    }
}

function Install-CivicRelayPackage([string]$Winget, [string]$Id) {
    Write-Host "Installing $Id through Windows Package Manager..."
    Invoke-CivicRelayCommand $Winget (Get-CivicRelayPackageArguments $Id) $Id
    # Update this process only so newly installed programs can be discovered.
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + $env:Path
}

function Assert-CivicRelaySource([string]$Root) {
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Major -lt 10) {
        throw 'CivicRelay setup requires 64-bit Windows 10 or later. Windows 11 is recommended.'
    }
    foreach ($file in @('package.json','package-lock.json','app\server.py','connector\desktop.py','scripts\check-install.mjs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $file) -PathType Leaf)) { throw 'Extract the entire CivicRelay source ZIP into a permanent local folder before running setup.' }
    }
    if (($Root -notmatch '^[A-Za-z]:[\\/]') -or ($Root.Length -gt 150)) { throw 'Use a short local folder path, such as your Documents\CivicRelay folder.' }
    $null = Assert-CivicRelayLocalPath $Root 'runtime-paths.json'
    # npm ci replaces node_modules. Do not follow a linked dependency folder.
    $modules = Join-Path $Root 'node_modules'
    if ((Test-Path -LiteralPath $modules) -and ((Get-Item -LiteralPath $modules -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Refusing a linked node_modules directory.'
    }
}

function Assert-CivicRelayIdle([string]$Root) {
    $status = $null
    try { $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -TimeoutSec 2 } catch { }
    if ($status -and $status.distribution -eq 'civic-records-desk') {
        throw 'Close the running CivicRelay dashboard server and stop its assistant MCP connections before installing dependencies. Setup will not stop processes for you. See docs/INSTALL.md.'
    }
    $entry = [regex]::Escape($Root.TrimEnd('\') + '\') + '(?:app\\tools\.mjs|connector\\server\.mjs|app\\server\.py)'
    $busy = Get-CimInstance Win32_Process -Filter "Name = 'node.exe' OR Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -and ($_.CommandLine.Replace('/','\') -match $entry) }
    if ($busy) { throw 'This checkout has active dashboard or MCP processes. Stop its connections before rerunning setup; no process was stopped.' }
}

function Invoke-CivicRelayDependencies([string]$Root, [hashtable]$Inventory, [bool]$Developer) {
    $env:CRM_PROTON_PYTHON = $Inventory.python
    $env:RECORDS_DESK_NODE = $Inventory.node
    if ($Inventory.gh) { $env:RECORDS_DESK_GH = $Inventory.gh }
    $env:Path = (Split-Path -Parent $Inventory.node) + ';' + $env:Path
    $npm = Join-Path (Split-Path -Parent $Inventory.node) 'node_modules\npm\bin\npm-cli.js'
    Push-Location -LiteralPath $Root
    try {
        Write-Host 'Installing locked JavaScript dependencies (no package lifecycle scripts)...'
        Invoke-CivicRelayCommand $Inventory.node @($npm,'ci','--ignore-scripts','--include=dev','--no-audit','--no-fund') 'JavaScript dependencies'
        Invoke-CivicRelayCommand $Inventory.node @((Join-Path $Root 'scripts\check-install.mjs')) 'Local dependency check'
        Write-Host 'Running synthetic self-tests; no mailbox login or live send is used...'
        Invoke-CivicRelayCommand $Inventory.node @($npm,'test') 'Synthetic self-tests'
        if ($Developer) {
            Invoke-CivicRelayCommand $Inventory.node @((Join-Path $Root 'node_modules\playwright\cli.js'),'install','chromium') 'Developer browser download'
            Invoke-CivicRelayCommand $Inventory.node @($npm,'run','test:browser') 'Synthetic browser tests'
        }
    } finally { Pop-Location }
}

function Set-CivicRelayAssistantConfig([string]$Root, [string]$Node) {
    # Existing host trust, permissions, and configuration are never changed/read.
    if (Test-Path -LiteralPath (Join-Path $Root '.codex\config.toml')) {
        Write-Host 'Existing assistant configuration preserved. See docs/SETUP.md for a reviewed upgrade.'
        return
    }
    Invoke-CivicRelayCommand $Node @((Join-Path $Root 'scripts\configure-codex.mjs')) 'Optional assistant configuration'
}

function Invoke-CivicRelayInstall([string]$Root, [hashtable]$Inventory, [bool]$Mail, [bool]$GitHub, [bool]$Codex, [bool]$Developer) {
    Assert-CivicRelaySource $Root
    Assert-CivicRelayIdle $Root
    $plan = @(Get-CivicRelayInstallPlan $Inventory $Mail $GitHub)
    if ($plan.Count -and -not $Inventory.winget) {
        throw 'Windows Package Manager (WinGet) is unavailable. Install/update Microsoft App Installer from the Microsoft Store, reopen setup, or use the official manual downloads in docs/INSTALL.md. No software was downloaded.'
    }
    foreach ($id in $plan) { Install-CivicRelayPackage $Inventory.winget $id }
    $installed = Get-CivicRelayInventory $Root
    if (-not $installed.python -or -not $installed.node -or ($Mail -and -not $installed.bridge) -or ($GitHub -and -not $installed.gh)) {
        throw 'A selected prerequisite is still missing or incompatible. See docs/INSTALL.md for manual paths, Python Tcl/Tk repair, or Bridge installation. Setup is not complete.'
    }
    Invoke-CivicRelayDependencies $Root $installed $Developer
    Save-CivicRelayRuntimePaths $Root $installed
    if ($Codex) { Set-CivicRelayAssistantConfig $Root $installed.node }
}
