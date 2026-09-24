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
