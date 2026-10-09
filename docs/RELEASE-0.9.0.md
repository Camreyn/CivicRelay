# CivicRelay 0.9.0 — guided updates

- **Settings → Updates** shows installed/latest versions and literal release notes.
- Optional automatic checks start disabled, check public metadata at most daily
  while the dashboard is visible, and never download/install automatically.
- The operator approves an exact version/package download, then confirms installation
  in **Update CivicRelay.cmd**. Changed or invalid packages fail closed.
- The installer verifies archive/file hashes and commit identity, refuses active
  old-installation dashboard/MCP/worker processes, installs into a new versioned
  sibling folder, installs locked dependencies without lifecycle scripts, and runs
  synthetic checks. Switching dashboard/assistant paths remains a guided manual step.
- Existing private stores, reusable templates, requester defaults, immutable drafts,
  mail scope, credentials, receipts and limits are never opened or modified by the
  updater. Local edits/config/research remain in the untouched old folder.
- Failed installs retain the current app and incomplete candidate; no automatic
  activation, database rollback, process killing, mailbox operation or host-permission
  change is introduced. No new dependencies or native/page tools are added.

The dedicated release package is verified against the official GitHub SHA-256
metadata and internal manifest over HTTPS, not an independent publisher-key
signature. Read [guided updates and recovery limits](UPDATES.md). Versions before
0.9.0 need one [manual upgrade](UPGRADING.md) to obtain the updater.

This release retains all 0.8.0 requester-default and sending-limit behavior, the
mailbox privacy policy, and the byte-preserved historical starter snapshot. It
does not rewrite user templates or historical case/draft text.
