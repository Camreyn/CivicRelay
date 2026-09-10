# CivicRelay setup

Start from a clone of [Camreyn/CivicRelay](https://github.com/Camreyn/CivicRelay).
An existing installation may still use the folder name `CivicRecordsDesk`;
the checkout's name is not significant. Do not rename its private storage.

## Requirements

- Windows with the same signed-in user profile used for existing encrypted data.
- Python 3.13 with Tkinter and `pythonw.exe`. Default: `C:\Python313\python.exe`.
- Node.js 22 or later. Default for Python-launched work:
  `C:\Program Files\nodejs\node.exe`.
- Proton Mail Bridge already working locally. The connector supports pinned
  STARTTLS on loopback IMAP/SMTP only, not a remotely hosted mail server.
  Live use requires a paid plan including Proton Mail; see
  [Proton's Bridge requirements](https://proton.me/mail/bridge).
- GitHub CLI if using reviewed public-issue intake. Default:
  `C:\Program Files\GitHub CLI\gh.exe`. Authentication is outside this repository.

JavaScript dependencies are pinned in `package-lock.json`. The Python runtime
uses the standard library only. Install JavaScript packages from the project:

```powershell
npm.cmd ci --ignore-scripts
```

On an existing installation, moving this folder does not require account setup.
Do not copy encrypted databases into the repository to make the app portable.

The current source fixes the sender to `CivicResultMaps@proton.me` and the intake
repository to `Camreyn/civicresultmaps`. The sender field in setup is read-only.
Another organization cannot simply enroll an unrelated mailbox; generalizing
account policy/storage is separate reviewed development. Do not remove identity
checks or reuse the real operator's store for a demonstration.

## Runtime paths

Trusted launch configuration may set absolute executable paths:

```powershell
$env:CRM_PROTON_PYTHON = 'C:\Python313\python.exe'
$env:RECORDS_DESK_NODE = 'C:\Program Files\nodejs\node.exe'
$env:RECORDS_DESK_GH = 'C:\Program Files\GitHub CLI\gh.exe'
```

These are not credentials and cannot be provided through tool arguments. The
application deliberately ignores Python startup hooks and does not read `.env`
files. Environment changes in one terminal do not change already-running MCP or
dashboard processes. Restart those processes after a configuration change.

Run `Open CivicRelay.cmd` (or its `Open Records Desk.cmd` alias) for a hidden local server plus a browser tab, or
`npm.cmd start` for a foreground server. The launcher does not kill a process
already occupying port 8766. To stop a foreground server, use Ctrl+C. For a
hidden server, identify its command line and stop only that dashboard process;
never stop all Python or Node processes.

## First-time account enrollment only

1. Use a dedicated project mailbox or Bridge split-address mode that exposes only
   the intended project address. Isolation is user-attested, not independently
   guaranteed by the connector.
2. Run `Open-Proton-Setup.ps1` in an interactive Windows session.
3. Verify the fixed project address matches Bridge's local username, then enter
   its generated Bridge password and the local ports shown by Bridge. Do not use
   the Proton account password. Defaults are IMAP 1143 and SMTP 1025; use the
   actual values in the local Bridge window.
4. Review the displayed certificate-pinning and sending settings in that window.
   Sending remains disabled unless locally enabled.
5. Use `proton_status` and then `proton_check_connection`. The connection check
   authenticates IMAP/SMTP without sending or reading message bodies.

Never paste a Bridge password into chat or commit it to Git. The setup window is
not part of routine startup. A changed Bridge certificate must be investigated
and re-enrolled by the human; do not disable certificate pinning.

If PowerShell's local script policy blocks an operator-reviewed launcher, use a
one-process invocation rather than changing machine-wide policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Open-Proton-Setup.ps1
```

Managed Windows policy may still prohibit execution; do not override organization
policy. No administrator privileges are required by this application.

## Codex registration

Run the configuration generator from this project:

```powershell
node scripts/configure-codex.mjs
```

It generates **only** this folder's ignored `.codex/config.toml`, using absolute
paths for this checkout. It refuses to overwrite an existing configuration. The
reviewable template is [mcp-config.example.toml](mcp-config.example.toml).
It does not change global trust, enroll credentials, launch an MCP server, or
register the unrelated CivicResultMaps data MCP.

Open this folder as a trusted Codex project. If the app already has these tools
running, use Settings → MCP servers → Restart, or reopen the project, to load
updated paths. Keep the configured per-tool approval prompts. Project-scoped
configuration, STDIO `command`/`args`/`cwd`/`env`, and restart behavior follow
[OpenAI's MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp).

The dashboard is optional for native assistant tools: `records_desk` calls the
same Python workflow through STDIO. `proton_mail` provides the lower-level mail
connector. Neither server should be launched as a detached persistent STDIO
process. Codex owns its lifecycle.

The MCP transport is local STDIO, not the dashboard HTTP URL. An ordinary browser
works without WebMCP; page tools appear only when the browser exposes the
supported API. Native tools do not require an open browser tab. CivicRelay itself
does not call a model API, so it has no OpenAI API-key requirement; your assistant
client's account, permissions and availability are separate.

For an intended live mailbox, configure GitHub CLI separately before publishing
an issue. `gh auth status` must confirm authentication to an account with access
to the CivicResultMaps repository. Use the normal `gh` login flow if needed;
never put a GitHub token into the app or its config. Read-only catalog/testing
does not require GitHub authentication.

For the migrated installation, the CivicResultMaps project's two mail-server
entries also point to this sibling project. Thin old-path compatibility shims
temporarily support already-loaded sessions; see [migration](MIGRATION.md).

## Verification

```powershell
npm.cmd test
npm.cmd exec -- playwright install chromium
npm.cmd run test:browser
```

The first command uses isolated temporary Windows profiles and mocked network
operations; real DPAPI tests protect synthetic values only. The browser test uses
an ephemeral local synthetic API, blocks non-fixture traffic, closes its browser,
and writes only gitignored synthetic screenshots. It does not open real approval
windows or touch the configured mailbox.

`npm.cmd run test:live-readonly` is a separate, explicit operator check. It
expects the existing Pennsylvania case/draft, verifies the map and send-status
controls, and allows only local GETs and two read-only case/status operations.
It does not sync mail, save forms, open approval, send, or capture real records
screenshots. A fresh installation without that case should use the synthetic test.

If Windows sandbox policy prevents child-process creation (`spawn EPERM`), rerun
the same reviewed tests in a normal local console. Do not weaken application
validation or send controls to make a test pass.
