# Fresh-install rehearsal

This guide describes the current-source release check, replacing the historical
v0.6.0 rehearsal. Use the [current installation instructions](INSTALL.md), not
an older release archive. The test is a clean source/dependency rehearsal on
Windows with installed prerequisites, not a fresh Windows VM installation.

## Reproducible method

1. Commit the reviewed source, then clone that exact candidate into a new
   disposable directory with `git clone --no-local`. Do not copy a live profile,
   ignored configuration, private exports or `node_modules` into it.
2. Confirm `.private`, `.local`, `.codex` and `node_modules` are absent before
   installation. Select the existing Node and Python executables explicitly
   for this process; do not read the operator's saved runtime configuration.
3. Run `npm.cmd ci --ignore-scripts --include=dev --no-audit --no-fund` from the
   candidate's lockfile, then the installer diagnostic below. This does not
   install system packages, start the dashboard, enroll an account or read mail.
4. Run `npm.cmd test`, `npm.cmd run test:browser`,
   `npm.cmd run publish:check` and `npm.cmd audit --audit-level=low`.
   Browser tests need Playwright Chromium installed separately using
   `npm.cmd exec -- playwright install chromium` when it is not already cached.
5. Confirm the checkout remains clean. Tests must use disposable synthetic
   profiles and fixture servers, never the operator's live profile or dashboard.
   Record the results below and repeat verification for the final source commit.

The read-only installer diagnostic is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -CheckOnly
```

The install regression in `npm.cmd test` separately exercises ZIP-style source
without Git, first/repeat installs, fixed WinGet package arguments, path handling,
failure recovery, active-process refusal and preservation of existing settings.
System package operations are mocked. No real credentials or private records
are needed; no email or public issue is sent.

## Verified on 2026-09-23

The feature candidate `edf5045028fdee5b47519edadb06a217165c35b9` was cloned with
`--no-local` into a new Windows temporary directory. All 163 versioned files
were present; `.private`, `.local`, `.codex` and `node_modules` were absent
before dependency installation. No live settings or account data were copied.

| Check | Result |
| --- | --- |
| Locked dependency installation | 18 packages installed successfully, with lifecycle scripts disabled |
| Read-only installer diagnostic | Passed under Windows PowerShell 5.1 with Node 22.16.0 and Python 3.13.3; Tcl/Tk, SSL, SQLite, ctypes, MCP imports and public catalog checked |
| Node tests, including installer and actual MCP handshakes | 66 passed |
| Application Python tests | 169 passed |
| Connector Python tests | 50 passed |
| Documentation | 28 Markdown files, 152 local links, 29 documented commands and 69 native tool schemas checked |
| Synthetic Chromium workflows | All 9 passed, including map controls, MA review, Settings and municipal sources |
| Publication check | All 163 source files and indexed blobs passed; private paths excluded and catalog snapshot verified |
| Dependency audit | No vulnerabilities reported at the time of the check |
| Final checkout state | Clean; no source changes produced by installation or tests |

The browser runtime was already cached. Neither its download nor any vendor
system installer was exercised in this run. Subsequent changes that record this
evidence are documentation-only; the final publication candidate is checked
again before pushing. GitHub's Windows workflow independently runs the suite
for the pull request and merged `main`.

The actual public `main` ZIP at merge `a9c4f83` was also downloaded and checked
against all 163 committed files using the repository's declared line-ending
rules (Windows launchers use CRLF; catalog identity bytes are preserved).
Locked dependency installation, diagnostics and all 285 self-tests passed with
no `.git` checkout and no Git executable on the test process's PATH.

The initial pull-request Windows run passed. A subsequent hosted runner hit the
synthetic harness's 30-second timeout during its first PowerShell 5.1 launch,
before reporting a parsing result. The follow-up batches the invalid-input
table in one real PowerShell process, retains every assertion, adds PowerShell
checks for malformed/oversized JSON, and allows a bounded 60 seconds per test
process. Runtime, mailbox and installer policy are unchanged. See
[the recorded CI failure](https://github.com/Camreyn/CivicRelay/actions/runs/35954418835).

## Verification limits

- This checks source completeness, locked libraries, Windows runtime probes,
  application behavior and synthetic assistant workflows. Existing compatible
  Node/Python and cached browser installations are not a clean Windows VM.
- WinGet/Store availability, vendor installers, administrator prompts, managed
  PC policies and actual Proton sign-in are not exercised. The full installer
  is not run against a concurrently active live dashboard; its refusal is a
  safety feature, not something to bypass for a rehearsal.
- It does not prove provider delivery, agency procedures, GitHub permissions,
  Codex UI trust/permission behavior or compatibility with every assistant.
- Publication checks cover allowlisted source paths, staged content and limited
  token markers. They supplement, not replace, manual privacy review.

See [testing](TESTING.md) for individual workflow coverage and
[contribution rules](CONTRIBUTING.md) for the publication procedure.
