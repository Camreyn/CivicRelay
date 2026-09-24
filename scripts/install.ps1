#requires -Version 5.1
param([switch]$CheckOnly, [switch]$LocalOnly, [switch]$WithGitHub, [switch]$ConfigureCodex, [switch]$Developer, [switch]$Yes)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'install-support.ps1')
$root = Split-Path -Parent $PSScriptRoot

function Confirm-Setup([string]$Question, [bool]$Default) {
    $hint = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $answer = (Read-Host "$Question $hint").Trim()
        if (-not $answer) { return $Default }
        if ($answer -match '^(y|yes)$') { return $true }
        if ($answer -match '^(n|no)$') { return $false }
        Write-Host 'Please type y or n.'
    }
}

try {
    Write-Host 'CivicRelay - Windows setup'
    Write-Host 'No email, credentials, account enrollment, fees, or public submissions are part of setup.'
    Assert-CivicRelaySource $root
    $inventory = Get-CivicRelayInventory $root
    foreach ($kind in @('python','node','bridge','gh','winget')) {
        $description = if ($inventory[$kind]) { $inventory[$kind] } else { 'not detected' }
        Write-Host "  ${kind}: $description"
    }
    if ($CheckOnly) {
        Write-Host 'Check-only: no installs, config writes, app startup, or mailbox connections.'
        if (-not $inventory.python -or -not $inventory.node) { throw 'Required Python 3.13 (64-bit, Tkinter/pythonw) or Node 22+ with npm is missing. Run Install CivicRelay.cmd.' }
        $env:CRM_PROTON_PYTHON = $inventory.python
        Invoke-CivicRelayCommand $inventory.node @((Join-Path $root 'scripts\check-install.mjs')) 'Dependency check'
        Write-Host 'Core dependencies OK. Bridge login, mailbox enrollment, and assistant trust are not checked.'
        exit 0
    }
    $mail = -not $LocalOnly
    $github = [bool]$WithGitHub
    $codex = [bool]$ConfigureCodex
    if (-not $Yes) {
        if (-not $LocalOnly) { $mail = Confirm-Setup 'Include email support (Proton Mail Bridge; a paid Mail plan and manual sign-in are needed)?' $true }
        if (-not $WithGitHub) { $github = Confirm-Setup 'Install optional GitHub CLI for publishing reviewed records issues?' $false }
        if (-not $ConfigureCodex) { $codex = Confirm-Setup 'Prepare optional project-local Codex assistant configuration (preserves any existing file)?' $true }
    }
    $plan = @(Get-CivicRelayInstallPlan $inventory $mail $github)
    Write-Host ''
    Write-Host 'Setup plan:'
    if ($plan.Count) { foreach ($id in $plan) { Write-Host "  Install missing prerequisite: $id (WinGet community source, vendor installer)." } }
    else { Write-Host '  Reuse existing compatible applications; no system package upgrades.' }
    Write-Host '  Install locked npm packages, run synthetic tests, save non-secret runtime paths under .local/.'
    if ($codex) { Write-Host '  Create assistant config only if absent; do not change trust or permissions.' }
    if ($Developer) { Write-Host '  Download Chromium and run the optional synthetic browser tests.' }
    Write-Host 'Package installers may request Windows administrator consent, update an older version, and change their own PATH entries.'
    Write-Host 'Continuing accepts the selected packages and WinGet source license terms. Cancel to use manual downloads.'
    Write-Host 'Stop this checkout''s dashboard and MCP connections first. Existing mail, private data and host permissions are preserved.'
    if (-not $Yes -and -not (Confirm-Setup 'Proceed with this setup plan?' $true)) { Write-Host 'Cancelled; no changes made.'; exit 0 }
    Invoke-CivicRelayInstall $root $inventory $mail $github $codex ([bool]$Developer)
    Write-Host ''
    Write-Host 'CivicRelay core setup and synthetic checks completed.'
    Write-Host 'Next time, double-click Open CivicRelay.cmd. No terminal path settings are needed.'
    if ($mail) {
        Write-Host 'MAIL STILL NEEDS YOU: open Proton Mail Bridge, sign in to your dedicated account, then use Open Proton Setup.cmd for FIRST-TIME enrollment only.'
        Write-Host 'Never repeat enrollment for an existing account just because you ran this installer. Enter passwords only in the local form.'
    }
    if ($codex) { Write-Host 'ASSISTANT: review .codex/config.toml, open this folder as a trusted project, and reconnect its two MCP servers. See README.md.' }
    if ($github) { Write-Host 'GITHUB (optional): authenticate separately with gh auth login before any authorized publication.' }
    Write-Host 'Troubleshooting and manual downloads: docs/INSTALL.md. No account was signed in or tested.'
    if (-not $Yes -and (Confirm-Setup 'Open the dashboard now?' $true)) { & (Join-Path $root 'Open-Records-Desk.ps1') }
    exit 0
} catch {
    Write-Host ''
    Write-Host ('Setup stopped: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'See docs/INSTALL.md. Already-installed prerequisites are left in place; rerun after resolving the problem.'
    exit 1
}
