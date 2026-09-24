# Trusted, local executable paths only. Never read mailbox settings here.
function Test-CivicRelayExecutablePath([string]$Value) {
    return $Value -match '^[A-Za-z]:[\\/]' -and $Value -notmatch '[\x00-\x1f"<>|?*]' -and $Value -match '\.exe$'
}

function Assert-CivicRelayLocalPath([string]$Root, [string]$Name) {
    $directory = Join-Path $Root '.local'
    $file = Join-Path $directory $Name
    foreach ($item in @($directory, $file)) {
        if (Test-Path -LiteralPath $item) {
            if ((Get-Item -LiteralPath $item -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Refusing a linked .local directory or runtime file. See docs/INSTALL.md.'
            }
        }
    }
    return $file
}

function Read-CivicRelayRuntimePaths([string]$Root) {
    $file = Assert-CivicRelayLocalPath $Root 'runtime-paths.json'
    $result = @{}
    if (-not (Test-Path -LiteralPath $file)) { return $result }
    if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-Item -LiteralPath $file).Length -gt 8192) {
        throw 'Invalid .local/runtime-paths.json. See docs/INSTALL.md.'
    }
    try { $config = [IO.File]::ReadAllText($file) | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'Invalid JSON in .local/runtime-paths.json. No settings were changed.' }
    if ($null -eq $config -or $config -is [array] -or $config.schema_version -isnot [int] -or $config.schema_version -cne 1) {
        throw 'Unsupported runtime-paths schema. See docs/INSTALL.md.'
    }
    foreach ($property in $config.PSObject.Properties) {
        if ($property.Name -ceq 'schema_version') { continue }
        if (@('python','node','gh') -cnotcontains $property.Name -or $property.Value -isnot [string] -or -not (Test-CivicRelayExecutablePath $property.Value)) {
            throw 'Runtime configuration accepts only absolute local python/node/gh executable paths.'
        }
        $result[$property.Name] = $property.Value
    }
    return $result
}

function Use-CivicRelayRuntimePaths([string]$Root) {
    $config = Read-CivicRelayRuntimePaths $Root
    $names = @{ python='CRM_PROTON_PYTHON'; node='RECORDS_DESK_NODE'; gh='RECORDS_DESK_GH' }
    foreach ($key in $names.Keys) {
        if (-not [Environment]::GetEnvironmentVariable($names[$key], 'Process') -and $config.ContainsKey($key)) {
            [Environment]::SetEnvironmentVariable($names[$key], $config[$key], 'Process')
        }
    }
}

function Save-CivicRelayRuntimePaths([string]$Root, [hashtable]$Paths) {
    $file = Assert-CivicRelayLocalPath $Root 'runtime-paths.json'
    # Refuse an unknown existing schema, rather than replacing user configuration.
    $null = Read-CivicRelayRuntimePaths $Root
    $config = [ordered]@{ schema_version=1 }
    foreach ($key in @('python','node','gh')) {
        if ($Paths[$key]) {
            if (-not (Test-CivicRelayExecutablePath $Paths[$key])) { throw 'Invalid runtime executable path.' }
            $config[$key] = $Paths[$key]
        }
    }
    $null = [IO.Directory]::CreateDirectory((Split-Path -Parent $file))
    $temporary = Assert-CivicRelayLocalPath $Root ('runtime-' + [guid]::NewGuid().ToString('N') + '.partial')
    $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($config | ConvertTo-Json) + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
    } finally { $stream.Dispose() }
    try {
        $null = Assert-CivicRelayLocalPath $Root 'runtime-paths.json'
        if (Test-Path -LiteralPath $file) { [IO.File]::Replace($temporary, $file, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $file) }
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary } }
}
