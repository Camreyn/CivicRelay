# CivicRelay

A Windows-local dashboard and assistant toolkit for managing public-records
requests through Proton Mail Bridge. It is a standalone project extracted from
CivicResultMaps, not a hosted service or a production election-data importer.

The dashboard supports reusable public-records work: private workspace details,
editable request templates, campaigns and jurisdiction targets, correspondence,
reviewed email drafts, received-file provenance, and publication previews.
Email sends, public issue creation, and local file exports run directly when
requested by the operator or an authorized assistant. CivicRelay has no extra
per-action approval dialogs. Preparing a draft does not send it, and there are
no background sends or automatic retries. Assistant-host permissions are separate.

Version 0.6.0 is a reusable local public-records manager, not a hosted service
or a full/multi-account email client. Each Windows-user installation has one
dedicated Proton Bridge mailbox. A fresh user can enroll their own dedicated
address locally; existing CivicResultMaps installations retain their legacy
identity and stores. No credentials or real correspondence are included here.

## What it does

- Shows 50 states plus DC, with request status and a per-case workspace.
- Tracks verified custodians, saved correspondence, exact reply chains, and
  manually requested inbox checks.
- Prepares immutable email drafts and records accepted/uncertain send outcomes.
- Retains returned attachments encrypted locally, with original-byte hashes and
  provenance; it does not automatically execute or publish those files.
- Preserves the optional historical CivicResultMaps intake workflow for
  compatibility. These source-review tickets are **not automatic data imports**;
  new reusable cases have no publication destination until the local user
  configures one.
- Lets an operator build private, versioned request templates and campaigns for
  federal, state, county, municipal, or other targets. Templates and campaigns
  never send mail, accept fees, or choose a publication destination.
- Exports a reviewed private case package locally without GitHub. Optional
  publication destinations are configured locally and each exact preview is
  invalidated if its configured target changes.
- Tracks a separate nationwide [equipment and communications campaign](docs/EQUIPMENT-CAMPAIGN.md), including remaining states, scoped drafts, sources and response/fee/deadline notes.
- Exposes the same guarded local workflow through dashboard and assistant tools.

The current pilot allows **10 send attempts per rolling 24 hours**, at least
60 seconds apart. An assistant can review and act within a user-delegated records
workflow without a CivicRelay confirmation for each message. This release does
not add a scheduler or unattended bulk-sending loop.

## Start on this PC

Double-click **Open CivicRelay.cmd**. The old **Open Records Desk.cmd** alias also
works. The dashboard remains at
[127.0.0.1:8766](http://127.0.0.1:8766/).

The folder move does not require entering Bridge credentials again. Keep Proton
Mail Bridge running and signed in. Existing credentials, correspondence, drafts,
and receipts remain in their original encrypted Windows-user storage, outside
this Git repository.

After updating to 0.6.0, restart the CivicRelay dashboard when no operation is
in progress, reload its page, and reconnect its two native tool connections.
The old `confirmation` tool arguments have been removed; use the current schemas.
No credential re-enrollment or change to Codex permissions is needed for this
code update. Existing host prompts may still apply.

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

No Bridge login is needed to view the dashboard, create local templates and
campaigns, or use the bundled historical starter pack. Live mail remains
unavailable until the local user enrolls one dedicated account in the setup
window. Do not run account setup just to test source code.

Review the generated local configuration, then open this folder as a trusted
project in Codex. Enroll only a dedicated mailbox, never a combined personal
inbox. Credentials must be entered only in the local setup window, never in
chat, source files, screenshots, or Git.

## Project contents

| Location | Purpose | Git policy |
| --- | --- | --- |
| `app/` | Local HTTP dashboard, case workflow, assistant tools, tests | Versioned source |
| `connector/` | Bridge transport, encrypted draft store and credential setup UI | Versioned source |
| `data/` | Reviewed public request catalog, intake form, source hashes | Versioned public snapshot |
| `scripts/`, `docs/` | Launch, test, maintenance and operator documentation | Versioned source |
| `.private/` | Local research, operational notes, original migration backups | Never commit |
| `.codex/` | Machine-specific absolute tool paths | Never commit |
| `%LOCALAPPDATA%\CivicRelay\` | Fresh-install encrypted account and case storage | Outside repository; never commit |
| `%LOCALAPPDATA%\CivicResultMaps\` | Existing legacy encrypted storage, preserved in place | Outside repository; never commit |

The application does **not** need the CivicResultMaps checkout or its
`node_modules` during normal operation. The historical optional starter pack
contains a byte-preserved snapshot of 14 bundled request drafts across 13 states
and a 50-state-plus-DC workflow map; it is not an app restriction or a claim
about records availability.

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
- [Account and mailbox configuration](docs/ACCOUNT-CONFIGURATION.md)
- [Reusable workspace guide](docs/GENERAL-USER-GUIDE.md)
- [Templates](docs/TEMPLATES.md) and [campaigns](docs/CAMPAIGNS.md)
- [Optional publication integrations](docs/INTEGRATIONS.md)
- [Using the dashboard and understanding statuses](docs/USER-GUIDE.md)
- [Operator workflow and tool reference](docs/OPERATOR-TOOLS.md)
- [Complete native tool argument schemas](docs/TOOL-REFERENCE.md)
- [Architecture and public snapshot refresh](docs/ARCHITECTURE.md)
- [Privacy, security, and publication checklist](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Fresh-install verification](docs/FRESH-INSTALL-VERIFICATION.md) and
  [testing limits](docs/TESTING.md)
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
