# CivicRelay

*Public records. From request to result.*

A Windows-local dashboard and assistant toolkit for managing public-records
requests through Proton Mail Bridge. It is a standalone project extracted from
CivicResultMaps, not a hosted service or a production election-data importer.

The dashboard shows state request status, correspondence, reviewed email drafts,
received-file provenance, and previews for CivicResultMaps' public GitHub intake.
Email sends, public issue creation, and unredacted exports retain their existing
independent desktop confirmations. There are no automatic sends or retries.

This release is purpose-built for the dedicated `CivicResultMaps@proton.me`
mailbox and CivicResultMaps' records-response intake. It is **not yet a
general-purpose or multi-account email client**. A fresh clone can run the
dashboard and synthetic tests without access to that mailbox; using a different
sender requires a reviewed code change. No credentials or real correspondence
are included in this public repository.

## What it does

- Shows 50 states plus DC, with request status and a per-case workspace.
- Tracks verified custodians, saved correspondence, exact reply chains, and
  manually requested inbox checks.
- Prepares immutable email drafts and records accepted/uncertain send outcomes.
- Retains returned attachments encrypted locally, with original-byte hashes and
  provenance; it does not automatically execute or publish those files.
- Prepares reviewed public GitHub intake issues for CivicResultMaps. These are
  source-review tickets, **not automatic data imports**.
- Exposes the same guarded workflow through 20 records tools and 8 mail tools.

The current pilot allows **10 send attempts per rolling 24 hours**, at least
60 seconds apart, with a separate human confirmation for each message. It
organizes work across many requests; it is not an unattended bulk sender.

## Start on this PC

Double-click **Open CivicRelay.cmd**. The old **Open Records Desk.cmd** alias also
works. The dashboard remains at
[127.0.0.1:8766](http://127.0.0.1:8766/).

The folder move does not require entering Bridge credentials again. Keep Proton
Mail Bridge running and signed in. Existing credentials, correspondence, drafts,
and receipts remain in their original encrypted Windows-user storage, outside
this Git repository.

## New installation

Requires Windows, Python 3.13 with Tkinter, Node.js 22 or later, and an already
working Proton Mail Bridge account for live mail. Bridge requires a paid Proton
plan that includes Mail ([Proton's requirements](https://proton.me/mail/bridge)).
GitHub CLI is optional unless publishing
reviewed intake issues. See [setup](docs/SETUP.md) for executable paths, credential
enrollment, and assistant-tool registration.

```powershell
git clone https://github.com/Camreyn/CivicRelay.git
Set-Location CivicRelay
# Select the actual installed runtimes; see setup for the supported versions.
$env:CRM_PROTON_PYTHON = (Get-Command python.exe).Source
$env:RECORDS_DESK_NODE = (Get-Command node.exe).Source
npm.cmd ci --ignore-scripts
npm.cmd test
node scripts/configure-codex.mjs
npm.cmd start
```

No Bridge login is needed to view the prepared catalog or run the synthetic
tests. Live mail operations remain unavailable until the intended account is
enrolled locally. Do not run account setup just to test the source code.

Review the generated local configuration, then open this folder as a trusted
project in Codex. Do not enroll a personal mailbox alongside the intended project
mailbox. Credentials must be entered only in the local setup window, never in
chat, source files, screenshots, or Git.

## Project contents

| Location | Purpose | Git policy |
| --- | --- | --- |
| `app/` | Local HTTP dashboard, case workflow, assistant tools, tests | Versioned source |
| `connector/` | Bridge transport, encrypted draft store, setup and approval UI | Versioned source |
| `data/` | Reviewed public request catalog, intake form, source hashes | Versioned public snapshot |
| `scripts/`, `docs/` | Launch, test, maintenance and operator documentation | Versioned source |
| `.private/` | Local research, operational notes, original migration backups | Never commit |
| `.codex/` | Machine-specific absolute tool paths | Never commit |
| `%LOCALAPPDATA%\CivicResultMaps\` | Existing encrypted account and case storage | Outside repository; never commit |

The application does **not** need the CivicResultMaps checkout or its
`node_modules` during normal operation. Its current public snapshot contains
14 bundled request drafts across 13 states and a 50-state-plus-DC workflow map. A map region without a
template is not a statement about a state's records availability.

## Commands

```powershell
npm.cmd start                  # Foreground dashboard; Ctrl+C stops it
npm.cmd test                   # Synthetic Node/Python tests; no live mail
npm.cmd run test:browser       # Synthetic browser workflow; no live mail
npm.cmd run test:live-readonly # Explicit read-only check of this PC's running desk
npm.cmd run publish:check      # Git-visible path and public-template checks
```

Browser tests need Chromium installed for the pinned Playwright version; see
[setup](docs/SETUP.md). The live check is operator-specific and is not a test to
run against another person's mailbox. Do not run two dashboards on port 8766.

## Documentation

- [Setup and assistant tools](docs/SETUP.md)
- [Using the dashboard and understanding statuses](docs/USER-GUIDE.md)
- [Operator workflow and tool reference](docs/OPERATOR-TOOLS.md)
- [Complete native tool argument schemas](docs/TOOL-REFERENCE.md)
- [Architecture and public snapshot refresh](docs/ARCHITECTURE.md)
- [Privacy, security, and publication checklist](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Testing and verification limits](docs/TESTING.md)
- [Contributing and release checklist](docs/CONTRIBUTING.md)
- [Migration, compatibility, and rollback](docs/MIGRATION.md)

## Git and publication

This repository contains versioned source and public templates only. No remote
service is required for local operation. Before committing or publishing, run
`npm.cmd run publish:check`, review `git status --short`, and review the complete
staged diff. Never force-add ignored files. The check is a path/schema guard,
not a comprehensive secret scanner or permission to publish private records.

Report software bugs in [CivicRelay issues](https://github.com/Camreyn/CivicRelay/issues).
Reviewed records responses still belong in CivicResultMaps' intake, not in this
app's issue tracker. For security concerns, read [SECURITY.md](SECURITY.md).

Code is distributed under [Apache-2.0](LICENSE); see [NOTICE](NOTICE) for extraction
and source-snapshot attribution. Licenses for dependencies remain their own.
CivicRelay is not affiliated with or endorsed by Proton or OpenAI.
