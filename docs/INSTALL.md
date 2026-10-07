# Easy Windows installation

Use a **64-bit Intel/AMD Windows PC** (Windows 11 recommended), an internet
connection, and your normal Windows account. Proton Bridge supports up-to-date
Windows 10 22H2 or Windows 11; Windows ARM is not supported for this mail setup.
See [Proton's system requirements](https://proton.me/support/operating-systems-supported-bridge).
Do not run the whole setup as a
different administrator account: encrypted records belong to the signed-in user.

## Three steps

1. Download **Source code (zip)** from [v0.7.1](https://github.com/Camreyn/CivicRelay/releases/tag/v0.7.1)
   (also available from the repository's **Code → Download ZIP** menu).
   The older **v0.6.1 release ZIP does not include this installer**. These
   instructions describe the current source, not that older release. Extract
   the **entire ZIP** into a permanent,
   writable local folder, such as `Documents\CivicRelay`. Do not run it inside
   the ZIP, a temporary preview, a network share, or `Program Files`. A Git clone
   also works, but Git is not required for the ZIP route.
2. Double-click **Install CivicRelay.cmd**. Choose email support or local-only
   use, optional GitHub publishing tools, and optional Codex configuration.
   Review the displayed installation plan, then continue. This is a readable
   PowerShell bootstrap, not a signed MSI or a bundled/offline installer.
3. When setup reports success, open the dashboard when offered. Afterwards,
   double-click **Open CivicRelay.cmd** whenever you need it. Runtime paths are
   remembered across terminals and reboots; no manual environment commands are
   needed for normal launches.

Windows may request administrator consent for an individual vendor installer.
Follow your organization's policy; do not disable SmartScreen, antivirus, or
managed script restrictions. The launchers use a process-only PowerShell
execution-policy option, not a permanent policy change. If your organization
blocks this, ask its administrator or use its approved installation process.

## What setup takes care of

| Component | Setup behavior |
| --- | --- |
| Python 3.13, 64-bit | Reuses a compatible installation or installs the official Python package, including Tcl/Tk. Checks `pythonw.exe`, Tcl/Tk, SSL, SQLite and ctypes. No `pip install` is needed; CivicRelay uses Python's standard library. |
| Node.js 22+ and npm | Reuses a compatible Node/npm pair or installs the current Node LTS package. Uses the selected executable directly, even before a new terminal picks up PATH changes. |
| JavaScript libraries | Runs `npm ci --ignore-scripts --include=dev` from the shipped lockfile, including the dependencies needed by its self-tests. No lifecycle scripts run during dependency installation. |
| Proton Mail Bridge | Optional for local-only work; detects or installs it when email support is selected. Installation does **not** sign in or verify a mailbox. |
| GitHub CLI | Optional; detects or installs it only when requested for reviewed issue publication. No login is performed. |
| Local runtime configuration | Saves only executable paths in ignored `.local/runtime-paths.json`; never passwords. Dashboard, enrollment launcher and native assistant adapters use these paths. |
| Codex configuration | Optional, project-local `.codex/config.toml`; only created if absent. Existing files, trust, tool permissions and global settings are not overwritten. |
| Verification | Checks runtime/dependency imports and the public catalog, then runs synthetic unit, MCP, storage and documentation tests. No real mail is used or sent. |
| Developer browser | Only with `-Developer`: downloads Playwright Chromium and runs synthetic browser tests. An ordinary user needs only their existing browser, not this additional download. |

Missing applications use fixed package identifiers from the WinGet community
source: `Python.Python.3.13`, `OpenJS.NodeJS.LTS`, `Proton.ProtonMailBridge`, and
`GitHub.cli`. WinGet handles vendor downloads and manifest integrity checks.
Setup never disables those checks, installs an arbitrary supplied package,
uninstalls an application, accepts fees, or restarts Windows. A selected vendor
installer may upgrade an incompatible older installation or change its own PATH
entries; compatible detected versions are reused. Review the plan and license
terms before continuing. See [Microsoft's install-command reference](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)
and the [WinGet package manifests](https://github.com/microsoft/winget-pkgs).

## The parts that still need you

- **Email:** use a paid Proton plan that includes Mail. A personal account must
  use selected custom CivicRelay folders; a dedicated account/address is also supported.
  Open Proton Mail Bridge and sign in there. Then double-click **Open Proton
  Setup.cmd** for first-time CivicRelay enrollment. Enter the generated Bridge
  password and actual IMAP/SMTP ports in that local form; acknowledge mailbox scope
  and review TLS trust and sending enablement. Never enter these in chat or Git.
  [Proton's installation guide](https://proton.me/support/protonmail-bridge-install)
  describes Bridge sign-in; [account configuration](ACCOUNT-CONFIGURATION.md)
  describes CivicRelay's separate enrollment. Existing users should **not**
  re-enroll just because they ran setup. Before reading mail, use **Settings →
  Mail privacy** to preview/apply its scope. History is off by default.
- **Assistant:** install/use your own compatible local assistant client, review
  the generated configuration, open this folder as a trusted project, and
  reconnect the two MCP servers. Setup does not install an LLM, buy a subscription,
  remove host permissions, or launch background MCP servers. Follow
  [the assistant connection check](SETUP.md#check-the-assistant-connection) and
  [README workflow examples](../README.md#using-civicrelay-with-an-llm).
- **GitHub:** only if publishing reviewed issues, authenticate separately with
  `gh auth login` and verify access to the intended destination. Local records,
  templates and private exports do not require GitHub.

## Checking, rerunning and updating

For a source update, follow [UPGRADING.md](UPGRADING.md), with separate Git and ZIP
instructions and accidental-import recovery. Rerunning this installer alone does
not download new CivicRelay source code.

Double-click **Check CivicRelay.cmd** for a read-only prerequisite/dependency
check. It does not install, write configuration, start the app, read mailbox
settings, connect to Bridge, or verify sign-in. Missing optional Bridge/GitHub
binaries are reported but do not prevent the local dashboard check succeeding.
Runtime paths displayed in this local window may contain your Windows username;
review/redact them before sharing diagnostics.

Rerunning setup reuses compatible applications, refreshes only this checkout's
`node_modules` from its lockfile, repeats tests, and saves the selected runtime
paths. Stop the dashboard **server** and this checkout's assistant MCP
connections first; closing its browser tab alone does not stop the server.
Setup refuses to replace dependencies while it detects an active dashboard or
these MCP processes. It never kills processes. See [server startup/shutdown](SETUP.md#runtime-paths).
If a step fails, it stops with a nonzero exit and leaves already-installed
prerequisites in place. Resolve the reported problem and rerun; do not reset
encrypted stores or account history.

Existing `.codex/config.toml` is preserved byte-for-byte and not inspected.
Private mailbox stores, `.private/`, credentials, TLS pins, send quotas, drafts
and receipts are not migrated, reset, read or re-enrolled by setup. Installation
is not an automatic updater or backup. Keep the same Windows user and preserve
ignored configuration when updating source; see [security](SECURITY.md).

### Advanced invocation

From the extracted project folder:

```powershell
# Inspection only; no network requests or installation.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -CheckOnly

# Local records plus optional Codex configuration, no Bridge or GitHub install.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -LocalOnly -ConfigureCodex

# Developer option: also install Chromium and run browser verification.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Developer
```

`-WithGitHub` selects GitHub CLI. `-Yes` accepts the displayed installation plan
and package/source license terms without questions; it also suppresses dashboard
startup. It does **not** authorize mail operations or enroll any account. Without
`-LocalOnly`, this mode includes Bridge; Codex and GitHub are selected only with
their explicit flags. Use interactive setup unless you have reviewed the choices.

## If something is missing

- **WinGet not available:** install/update Microsoft's **App Installer** using
  the Microsoft Store, reopen setup, and try again. See
  [Microsoft's WinGet installation instructions](https://learn.microsoft.com/en-us/windows/package-manager/winget/#install-winget).
  Setup works without WinGet if all selected applications are already installed.
  It does not download and execute a replacement package-manager script.
- **No Store access / managed PC:** use your administrator's approved installers,
  or the official manual downloads below. Then rerun setup to install CivicRelay's
  libraries and check everything. Administrative restrictions are not bypassed.
- **Python lacks Tkinter or `pythonw.exe`:** modify the full Python 3.13
  installation in Windows Installed apps and include Tcl/Tk/IDLE, then rerun.
  Do not use Python's minimal embeddable ZIP. See
  [Python's Windows installer documentation](https://docs.python.org/3.13/using/windows.html).
- **An explicit runtime path is broken:** setup stops instead of choosing a
  different runtime silently. Correct the corresponding environment override or
  executable path in `.local/runtime-paths.json`. This file accepts only
  `schema_version: 1` and `python`, `node`, `gh` absolute local `.exe` paths.
  Explicit process environment values take precedence; otherwise the saved paths
  apply, then the legacy defaults. Do not put credentials or shell commands here.
  For a nonstandard installation, set the three runtime variables shown in
  [setup](SETUP.md#runtime-paths) before running the installer; it will save the
  validated choices for later launches.
- **Bridge installed in an unusual folder:** automatic detection covers normal
  vendor locations. Choose local-only setup and use your existing Bridge manually;
  local enrollment needs its loopback ports, not its application path.
- **Download or self-test fails:** keep the error text, check connectivity and
  disk space, and retry setup. No success is reported until tests pass. An
  `EPERM` child-process error may require a normal local console outside an
  assistant sandbox; it is not a reason to disable app safeguards.
- **Existing assistant config:** setup deliberately does not repair/overwrite it.
  Use the [reviewed configuration upgrade](SETUP.md#upgrading-an-existing-assistant-configuration)
  when paths or tool allowlists need changing.

Official manual downloads: [Python for Windows](https://www.python.org/downloads/windows/)
(select 3.13, full 64-bit installer), [Node.js LTS](https://nodejs.org/en/download),
[Proton Mail Bridge](https://proton.me/mail/bridge), and optional
[GitHub CLI](https://cli.github.com/). No paid software or account is purchased
by CivicRelay setup.

## What the tests prove

`npm.cmd run test:install` exercises Windows PowerShell 5.1 parsing, prerequisite
selection, fixed WinGet arguments, real read-only runtime probes, local path
persistence/validation, ZIP-style fixtures without Git, repeat installs,
preservation of existing configuration, failure handling, and active-process
refusal. System package installation is **mocked**. These tests do not prove a
fresh Windows VM's Store/UAC/vendor installer behavior or actual Proton login.
See the [fresh-checkout rehearsal](FRESH-INSTALL-VERIFICATION.md) and
[full verification limits](TESTING.md).
