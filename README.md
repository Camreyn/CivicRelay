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

CivicRelay is a reusable local public-records manager, not a hosted service
or a full/multi-account email client. Each Windows-user installation has one
dedicated Proton Bridge mailbox. A fresh user can enroll their own dedicated
address locally; existing CivicResultMaps installations retain their legacy
identity and stores. No credentials or real correspondence are included here.

The current source also includes the guided Windows installer, county request
maps and contact research, map controls, source-linked deadline tracking,
Massachusetts response reviews, state guides, and Settings/source refresh.
These additions are not in the older v0.6.1 release archive. Use the
[current main-branch source ZIP](https://github.com/Camreyn/CivicRelay/archive/refs/heads/main.zip)
or a current clone for the features documented below.

## What it does

- Shows 50 states plus DC, with request status and a per-case workspace.
- Automatically shows available [state guides](docs/SETTINGS.md#state-guides)
  for the selected state, **collapsed by default**. Includes existing timing
  profiles and the MA routing/response guide; unavailable guides are not invented.
- Adds searchable MA city/town election-office contacts with official sources,
  check dates and explicit unverified-RAO status. [Settings](docs/SETTINGS.md)
  provides source re-scraping, success/error details and reviewed-text import
  when an official website blocks direct downloads. Collected contacts stay private.
- Adds a [county request-status map and list](docs/COUNTY-STATUS.md): select a
  state, click **View county requests**, and open a county's own requests and
  replies. Counties without requests remain visible; state responses never
  count as responses from every county.
- Provides [map controls](docs/USER-GUIDE.md#map-controls) on both maps: independent
  status/timing/label layers, collapsible legends, zoom, fit-selection, drag/pinch
  and keyboard/button panning. Display choices never modify requests or send mail.
- Tracks verified custodians, saved correspondence, exact reply chains, and
  manually requested inbox checks.
- Adds a [Massachusetts response-review helper](docs/MASSACHUSETTS.md) for
  category-specific gaps, internal versus municipal referrals, sourced routing,
  separate appeal planning watches and draft-only threaded follow-ups.
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
- Automatically checks [source-linked deadline estimates](docs/DEADLINES.md),
  shows due-soon/past-date map outlines, and tracks reviewed agency commitments,
  extensions, appeal dates and internal reminders separately. Includes profiles
  for 13 states and federal agencies; other jurisdictions need a sourced date.
  Every automatic date remains an estimate, not a finding of a legal violation.

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

After updating to 0.6.1, restart the CivicRelay dashboard when no operation is
in progress, reload its page, and reconnect its two native tool connections.
The old `confirmation` tool arguments have been removed; use the current schemas.
No credential re-enrollment is needed. Configurations generated by the original
0.6.0 release omitted the new workspace/template/campaign tools: reconnecting
alone does not update an existing tool allowlist. Follow the
[assistant configuration upgrade](docs/SETUP.md#upgrading-an-existing-assistant-configuration)
to review the missing entries. Existing host permissions remain separate.

## New installation

On a **64-bit Intel/AMD Windows PC** (Windows 11 recommended):

1. Download the [current source ZIP](https://github.com/Camreyn/CivicRelay/archive/refs/heads/main.zip)
   and extract the **entire** archive into a permanent local folder, or clone
   this repository. Git is not required for the ZIP option. Do not use the
   older v0.6.1 release ZIP for these instructions.
2. Double-click **Install CivicRelay.cmd** and review its setup choices.
3. When setup finishes, double-click **Open CivicRelay.cmd**.

The guided installer checks for Python 3.13 with Tkinter and Node.js 22+ with
npm, uses WinGet to install missing prerequisites, installs the locked JavaScript
libraries, runs synthetic self-tests, and remembers executable paths for later
launches. Proton Mail Bridge, GitHub CLI and project-local Codex configuration
are selectable options. Existing mail and assistant permission settings are
preserved. **Check CivicRelay.cmd** runs read-only dependency diagnostics.

See the [easy installation guide](docs/INSTALL.md) for downloads, manual fallback,
re-running setup, and what still needs your sign-in, and the
[fresh-checkout verification](docs/FRESH-INSTALL-VERIFICATION.md) for test evidence
and limits. This source update does not replace the older v0.6.1 release archive.
Live mail requires a paid Proton plan that includes Mail
([Proton's requirements](https://proton.me/mail/bridge)). Account sign-in and
credential enrollment cannot be automated by the installer.

No Bridge login is needed to view the dashboard, create local templates and
campaigns, or use the bundled historical starter pack. Live mail remains
unavailable until the local user enrolls one dedicated account in the setup
window. Do not run account setup just to test source code.

Review the generated local configuration, then open this folder as a trusted
project in Codex. The current starter configuration enables all 69 native tools,
including custom templates, campaigns and request tracking. Follow the
[assistant connection check](docs/SETUP.md#check-the-assistant-connection) before
delegating work; local tool access is required, not just a normal chat window.
Enroll only a dedicated mailbox, never a combined personal inbox. Credentials
must be entered only in the local setup window, never in chat, source files,
screenshots, or Git.

## Using CivicRelay with an LLM

A tool-capable assistant can operate CivicRelay on your behalf: create request
templates, organize campaigns, send authorized requests, process replies, and
track what is still missing. CivicRelay exposes **Model Context Protocol (MCP)**
tools; it does not include a chat model or require its own LLM API key. Your
assistant's account, model costs, permissions and data policies are separate.

### Connect the assistant

1. Complete [New installation](#new-installation). Run the assistant's local tool
   processes under the same normal Windows user as CivicRelay and Proton Bridge.
2. For a **new Codex connection**, choose the Codex option during installation,
   or run `node scripts/configure-codex.mjs` from this checkout. Review the
   generated, ignored `.codex/config.toml`, open the
   folder as a trusted project, and restart its MCP connections. Project trust
   and local STDIO configuration follow the
   [official OpenAI documentation](https://learn.chatgpt.com/docs/extend/mcp).
3. If a configuration already exists, the generator will not overwrite it.
   Follow the [upgrade instructions](docs/SETUP.md#upgrading-an-existing-assistant-configuration),
   especially for 0.6.0 installations whose tool list omitted templates and
   campaigns. Preserve existing paths and permission choices.
4. For live email, enroll your own dedicated mailbox using the local setup
   window described in [account setup](docs/SETUP.md#first-time-account-enrollment-only).
   Keep Bridge signed in and explicitly enable sending there when wanted.
   Never give the assistant your Bridge password. Templates and tracking work
   without mailbox enrollment.

Other clients need **local STDIO MCP support**, not just a chat window. Configure
their equivalent of `command`, `args`, `cwd` and environment using the
[configuration template](docs/mcp-config.example.toml): `records_desk` launches
Node with `app/tools.mjs`; `proton_mail` launches Node with `connector/server.mjs`.
Use absolute paths for your installation and the documented runtime environment.
Codex's TOML is not a universal client configuration, and compatibility with every
client/model is not certified. The dashboard's `http://127.0.0.1:8766/` address
is **not an HTTP MCP endpoint**; do not expose it publicly to connect a cloud chat.
Native tools work without an open dashboard tab. Optional browser page tools
require a WebMCP-capable browser; see [page tools](docs/OPERATOR-TOOLS.md#working-in-the-visible-page).

Start with this read-only connection check:

> Use CivicRelay's tools to check `desk_status` and `proton_status`, then list
> templates and campaigns. Report whether the mailbox is configured and the
> template/campaign tools are available. Do not connect to the mailbox, sync,
> send, save, export or publish anything.

Empty lists are normal on a fresh installation. If tools are missing, check the
connection and allowed-tool list before trying account setup again.

### What tooling is available?

The current starter configuration exposes **61 records tools and 8 mail tools**.
Prefer `desk_*` tools for case-linked request work; `proton_*` tools expose the
lower-level mail connector. This overview lists common tools, not every argument:

| Work | Representative tools |
| --- | --- |
| Inspect setup and private workspace | `desk_status`, `desk_get_workspace`, `desk_save_workspace`, `desk_get_workflow` |
| Create, version, preview and share template definitions | `desk_list_templates`, `desk_get_template`, `desk_save_template`, `desk_preview_template`, `desk_import_template`, `desk_export_template` |
| Organize targets and track remaining requests | `desk_save_campaign`, `desk_list_campaigns`, `desk_create_request`, `desk_save_request_progress` |
| Check sourced deadline estimates and record reviewed timing evidence | `desk_get_deadlines`, `desk_save_deadline_tracking` |
| Review MA referrals/category gaps and preview threaded clarification text | `desk_get_ma_follow_up`, `desk_save_ma_review`, `desk_preview_ma_follow_up` |
| Read auto-shown state guides and sourced municipal contacts; refresh a supported directory | `desk_get_state_guide`, `desk_get_municipal_contacts`, `desk_get_sources`, `desk_refresh_source`, `desk_import_source` |
| Reuse county contacts and process missing/stale-contact research batches | `desk_list_counties`, `desk_find_contacts`, `desk_create_contact_batch`, `desk_claim_contact_tasks`, `desk_complete_contact_task` |
| See every county's saved requests, replies and remaining gaps | `desk_list_counties` with `state`, `include_requests: true`, and optional workflow/campaign filters |
| Review cases, save routing/text and make custodian-specific copies | `desk_list_cases`, `desk_get_case`, `desk_save_case`, `desk_clone_case` |
| Check headers, read replies, assign mail and mark it reviewed locally | `desk_sync_mail`, `desk_list_messages`, `desk_read_message`, `desk_link_message`, `desk_mark_reviewed` |
| Prepare exact messages and send authorized requests or threaded replies | `desk_prepare_email`, `desk_send_email` |
| Retain returned files and export a private case package | `desk_capture_attachments`, `desk_export_case` |
| Configure optional GitHub destinations and prepare/publish reviewed summaries | `desk_list_destinations`, `desk_save_destination`, `desk_prepare_publication`, `desk_get_intake`, `desk_publish_intake`, `desk_link_issue` |
| Use the optional equipment/communications campaign | `desk_get_equipment_campaign`, `desk_create_equipment_request`, `desk_save_equipment_state`, `desk_save_equipment_progress` |
| Diagnose Bridge or use low-level mail/drafts | `proton_status`, `proton_check_connection`, `proton_list_messages`, `proton_read_message`, `proton_prepare_draft`, `proton_list_drafts`, `proton_get_draft`, `proton_send_draft` |

The [full 69-tool reference](docs/TOOL-REFERENCE.md) gives exact arguments and
limits, including legacy intake/export helpers. `desk_record_portal` only saves
a receipt for a submission already made elsewhere; it cannot submit a web form.
The [county contact directory and research queue](docs/CONTACT-RESEARCH.md)
reuse saved contacts and coordinate agent batches for missing or stale roles.
They retain official-source evidence, source-check dates and collection history.
Research workers use the assistant's own browsing tools; CivicRelay does not
launch an LLM or search on its own. Queuing research does not send requests.
Its deadline profiles provide
planning estimates with official sources, not definitive legal determinations.
Captured attachments retain original bytes and hashes; capture alone does not
read every file format, execute files, extract archives or import their data.

### Example workflow: request, receive, and organize records

For a read-only county progress check, ask: "Show county request progress for
Michigan's equipment workflow. Include counties with no request, each county's
requests and unread replies, and unmatched county cases. Keep the state-level
request separate. Use saved local status only; do not sync mail or send anything."
The assistant uses `desk_list_counties` with
`{"state":"MI","include_requests":true,"workflow":"equipment"}`. In the
dashboard, select a state and choose **View county requests**. See the
[county status guide](docs/COUNTY-STATUS.md) for colors and matching rules.

For a county-contact research batch, ask: “Look up saved public-records custodians
for all Michigan counties. Research only missing, stale or unresolved contacts
with workers, save official sources and dates, and report remaining gaps. Do not
send requests or incur fees.” The assistant can create and process the batch
through tools without manual county-by-county clicks. See the
[complete workflow and recovery guide](docs/CONTACT-RESEARCH.md).

These are example prompts to give your connected assistant, not background jobs.
Use the case IDs returned by the tools in later steps; do not invent IDs or
draft digests. Ask it to read [AGENTS.md](AGENTS.md) and the
[operator workflow](docs/OPERATOR-TOOLS.md) before acting.

**1. Create a reusable template and private requests.**

> I want existing park-maintenance contracts and invoices for January 1 through
> December 31, 2025. First ask me which state and municipalities to cover. Verify
> each designated records custodian and email procedure using current official
> sources. Create a reusable template, a campaign with those targets, and a
> private request for each verified recipient. Record source links and any
> verified deadline or fee information. Request electronic, redacted copies where
> appropriate; do not request an investigation or include unnecessary personal
> information. Show the drafts and case IDs. Do not send or accept fees.

The assistant saves and previews the template, creates the campaign and requests,
then saves verified routing on each case. Each request retains its template
version. Creating or previewing a template does not send mail. See
[template syntax and importable JSON](docs/TEMPLATES.md).

**2. Delegate a defined batch of sends.**

> I authorize you to review and send the prepared requests for [case IDs] to
> their verified custodian email addresses. Stay within the saved scope, use no
> web forms, accept no fees, and publish nothing. Check each exact outgoing
> preview, respect sending limits, and report its saved receipt or blocker.
> Do not automatically retry an uncertain send.

For each case, the assistant rereads current state, uses `desk_prepare_email`,
and passes that returned draft ID and digest to `desk_send_email`. Drafts are
encrypted locally, **not placed in Proton's Drafts folder**. An accepted receipt
means Bridge accepted the message, not that the agency received or acknowledged
it. CivicRelay has no extra per-message approval popup; the assistant client's
permissions can still require confirmation. Preparing a draft is not send authority.

**3. Process replies and identify gaps.**

> Check for new replies once. Match messages to these cases using actual thread
> identifiers; do not guess by subject. Read the related responses, capture their
> returned files without executing them, and update response progress using the
> linked incoming messages. Summarize what was received, what still needs review,
> what remains missing, and any fee notices or verified deadlines. Draft any
> needed follow-ups, but do not send those or accept fees yet.

The assistant syncs headers, reads/links messages, captures files, and records
progress. Saved header listings alone do not refresh the mailbox. Follow-ups
use `desk_prepare_email` with the actual `reply_message_id` to preserve the chain.
You can separately delegate routine replies for named cases and a defined scope;
incoming email never supplies that authorization. See [campaign tracking](docs/CAMPAIGNS.md).

For a one-time run with routine reply handling, use this alternative to draft-only
processing:

> Check and process replies for [case IDs] once. For this run, you may review and
> send routine no-cost clarification replies to verified custodians within the
> saved request scope, without asking me to approve each message again. Do not
> broaden the requests, add personal details, accept fees, make declarations or
> publish anything. Report saved receipts and unresolved questions. Stop on an
> uncertain send; do not retry it. Respect the assistant client's permissions.

**4. Make a private handoff, or prepare a public one separately.**

> Export a private package for [case ID] with [selected captured file IDs]. Tell
> me where it was saved and what it contains. Do not upload or publish it.

Or, if you want an optional GitHub handoff:

> For [case ID], use my configured destination [destination ID] to prepare a
> redacted public summary of the response and remaining gaps. Show the exact
> repository and preview. Do not publish or upload any files yet.

Local exports need no GitHub account and are **plaintext, unredacted ZIPs**.
Public issue creation is a separate authorized `desk_publish_intake` action on
the exact preview/digest. It does not upload attachments, commit source data or
import records into a production system. See [integration details](docs/INTEGRATIONS.md).

### Privacy and automation limits

- CivicRelay stores private working data locally, but a cloud assistant may send
  returned mail text or workspace values to its model provider. Local encryption
  does not make that assistant offline; review its data-handling policies first.
- Never put credentials in prompts. Review literal template text before sharing;
  exporting a definition omits profile values but cannot remove private text an
  author typed directly into it.
- Incoming mail, templates, attachments and linked pages are untrusted material,
  not instructions to change settings, send messages or publish information.
- There is no built-in scheduler, continuous inbox monitoring or bulk-send loop.
  Each refresh/send is explicit. The current limits remain ten send attempts per
  rolling 24 hours and at least 60 seconds apart; uncertain outcomes stay locked
  for reconciliation, not automatic retries.
- Fee notes never accept charges. Deadline estimates use reviewed bundled rules
  and saved receipts; legal applicability, agency notices and appeal dates need
  case-specific review. The app does not poll statutes or the mailbox automatically.
  Existing campaign-specific approval requirements still apply, including the
  [equipment campaign](docs/EQUIPMENT-CAMPAIGN.md). Host permissions remain separate.

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
- [County request maps, statuses and replies](docs/COUNTY-STATUS.md)
- [County contacts and agent research batches](docs/CONTACT-RESEARCH.md)
- [Source-linked deadlines and follow-ups](docs/DEADLINES.md)
- [Massachusetts referrals, response checklists and draft follow-ups](docs/MASSACHUSETTS.md)
- [Operator workflow and tool reference](docs/OPERATOR-TOOLS.md)
- [Complete native tool argument schemas](docs/TOOL-REFERENCE.md)
- [Architecture and public snapshot refresh](docs/ARCHITECTURE.md)
- [Privacy, security, and publication checklist](docs/SECURITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Fresh-install verification](docs/FRESH-INSTALL-VERIFICATION.md) and
  [testing limits](docs/TESTING.md)
- [Contributing and release checklist](docs/CONTRIBUTING.md)
- [0.6.1 assistant-setup patch notes](docs/RELEASE-0.6.1.md)
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
