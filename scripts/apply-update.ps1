#requires -Version 5.1
# Interactive, operator-started installation only; no background activation.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'install-support.ps1')
$root = Split-Path -Parent $PSScriptRoot
$extracted = $false
$inventory = $null
try {
    Write-Host 'CivicRelay - install the approved update'
    Write-Host 'Your current folder, templates, records, credentials and assistant permissions will not be replaced.'
    $inventory = Get-CivicRelayInventory $root
    if (-not $inventory.python -or -not $inventory.node) { throw 'Compatible Python/Node runtimes are required. Run the installation diagnostics first.' }
    $bridge = Join-Path $PSScriptRoot 'update-command.py'
    $description = & $inventory.python -B -E -s -S $bridge describe
    if ($LASTEXITCODE -ne 0) { throw 'No valid approved package is ready. Use Settings > Updates first.' }
    $plan = $description | ConvertFrom-Json
    if ($plan.stage -cne 'ready') { throw 'This package was already attempted. Nothing was overwritten; approve a new download to retry.' }
    Write-Host ('Approved version: ' + $plan.version)
    Write-Host ('New permanent folder: ' + $plan.destination)
    Write-Host 'Finish active operations, close the CivicRelay dashboard server, and stop both assistant MCP connections.'
    Write-Host 'This installer will not stop processes, read/copy private stores, change host configuration, or launch the updated app.'
    Write-Host 'It will verify/extract the approved archive, install locked dependencies without lifecycle scripts, and run synthetic self-tests.'
    if ((Read-Host 'Type INSTALL to approve installation, or press Enter to cancel') -cne 'INSTALL') { Write-Host 'Cancelled; no installation changes.'; exit 0 }
    Assert-CivicRelayUpdateIdle $root
    $destination = & $inventory.python -B -E -s -S $bridge extract
    if ($LASTEXITCODE -ne 0) { throw 'The approved package could not be extracted safely. The current installation is untouched.' }
    $extracted = $true
    $destination = [string]$destination
    Assert-CivicRelaySource $destination
    Assert-CivicRelayUpdateIdle $root
    Invoke-CivicRelayDependencies $destination $inventory $false
    Save-CivicRelayRuntimePaths $destination $inventory
    & $inventory.python -B -E -s -S $bridge installed
    if ($LASTEXITCODE -ne 0) { throw 'Installation checks passed, but its completion receipt could not be saved. Review the new folder before using it.' }
    Write-Host ''
    Write-Host 'The new version passed installation checks. Nothing was sent, published, or re-enrolled.'
    Write-Host ('Open the NEW folder: ' + $destination)
    Write-Host 'Start its Open CivicRelay.cmd; replace any old shortcut yourself.'
    Write-Host 'Review your assistant command/args/cwd paths for the new folder, preserving its tool allowlists and permissions, then reconnect both tool servers.'
    Write-Host 'Do not run both installations. Existing AppData stores are used in place. .private, .local and .codex in the old folder are retained there, not copied.'
    Write-Host 'The old folder remains available for reviewed recovery; never downgrade or copy private databases automatically.'
    exit 0
} catch {
    if ($extracted -and $inventory) { & $inventory.python -B -E -s -S (Join-Path $PSScriptRoot 'update-command.py') failed 2>$null }
    Write-Host ('Update stopped: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'The current installation and all user data remain untouched. Any incomplete new folder is retained for review. See docs/UPDATES.md.'
    exit 1
}
