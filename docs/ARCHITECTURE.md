# Architecture

## Runtime boundaries

The browser uses the loopback-only Python HTTP server in `app/server.py`.
The server and native MCP adapter `app/tools.mjs` call `app/worker.py`, which
dispatches an explicit operation allowlist. The lower-level mail adapter
`connector/server.mjs` calls `connector/worker.py`. Python enforces workflow and
side-effect checks independently of JavaScript schemas.

`app/runtime.py` loads `data/catalog.json` through `app/catalog.mjs` and imports
the sibling `connector/` package. No runtime import reaches into the
CivicResultMaps source checkout. All npm imports resolve in this project's own
installation. `app/static/map.json` is a prebuilt display asset.

The Windows bootstrap (`scripts/install.ps1`) detects compatible runtimes,
installs selected missing vendor applications through fixed WinGet package IDs,
installs locked npm dependencies, and runs synthetic tests. It does not enroll
mail, change assistant-host trust, or start background MCP servers. It saves
only executable paths to ignored `.local/runtime-paths.json`, consumed by the
PowerShell launchers and `runtime-config.mjs`; explicit environment overrides
still win. These are trusted local launch settings, never tool arguments.
The Python worker environment allowlists are unchanged. See [installation](INSTALL.md).

The HTTP server retains its fixed `127.0.0.1:8766` origin, Host/Origin checks,
session cookie and mutation protections. No public interface, authentication
service, tunnel, or remote deployment is provided. Do not expose it to the LAN
or internet. The public app/package is CivicRelay (`civic-relay`). Legacy health
identity, MCP server/tool names and storage namespaces remain for compatibility;
they are not a dependence on the original repository.
The health response additionally identifies the distribution and a path-derived
installation fingerprint so the launcher cannot silently reuse the legacy app
or another checkout. That non-secret fingerprint is not authentication.

## Storage and identity

`app/storage.py` retains the case/message/artifact workflow database.
`connector/secure_store.py` retains encrypted settings, immutable drafts,
send-attempt accounting and receipts. Sensitive payloads use Windows DPAPI under
the current user. Some database bookkeeping metadata may remain visible; these
files must all be treated as private, not as fully opaque encrypted disks.

One Windows-user installation has one dedicated mailbox profile. Fresh installs
use `%LOCALAPPDATA%\CivicRelay\ProtonConnector` and its paired
`%LOCALAPPDATA%\CivicRelay\RecordsDesk` database. If legacy connector or records
data exists, the application instead preserves `%LOCALAPPDATA%\CivicResultMaps\`
in place, including v1 sender identity, immutable drafts, receipts, and send
quota. It does not copy, decrypt, or convert those stores during root selection.

If both namespaces contain data, root resolution fails closed rather than
choosing, merging, resetting quota, or creating another mailbox history. DPAPI
is tied to the Windows user; a code checkout is not a portable mailbox backup.
Multiple checkouts under one Windows user therefore share the same selected
store and must not compete over live mail operations.

v2 settings bind a display name and generated profile ID into each new draft
digest. The configured email, display name, and profile ID must match before a
v2 draft can be sent. v1 draft digest and wire identity remain byte-compatible
and require legacy settings. The connector does not support arbitrary storage
paths or multiple accounts through dashboard/MCP arguments.

The original catalog digest, case IDs, draft IDs/digests, message IDs and source
identifiers are preserved. Existing saved case content and immutable drafts are
not rewritten when a new public catalog is installed.

### Send-status reconciliation

`app/send_state.py` identifies a reconciled outcome by both immutable draft ID
and send state. An accepted reply is a new event even when the original request
was also accepted. Only a valid receipt with a matching Message-ID and timezone-
aware acceptance timestamp advances the case to `waiting` and updates
`last_sent_at`; invalid or uncertain outcomes require attention.

Send completion and `desk_sync_mail` reconcile saved receipts under the mutation
lease. Older cases without `latest_send_draft_id` use the saved acceptance
timestamp to distinguish an already-consumed receipt from a stale earlier send.
The draft marker is backfilled once without reopening deliberately closed or
reviewed cases. Repeated reconciliation is a no-op. Generic campaign reads use
the same identity check without writing revisions. This never sends mail,
changes immutable drafts, or restarts the original deadline clock.

## Reusable workspace and historical starter pack

The private workspace stores versioned reusable templates, campaigns, target
progress, and locally configured publication destinations in the encrypted
records database. Templates are rendered as data, never as executable code.
Imported definitions and literal template text are untrusted until the operator
reviews them. A workspace's private requester fields are supplied only when a
template explicitly declares the corresponding required field; they are not
silently added to template exports or public previews.

The CivicResultMaps request snapshot remains a historical optional starter pack.
Its catalog, form, map, and provenance bytes remain preserved for compatibility;
the general workspace does not require the source repository, its GitHub intake,
or those bundled cases.

## Source-linked timing projections

`app/deadlines.py` reads the versioned `app/deadline-rules.json` registry and saved
case/draft/mail metadata. `desk_get_deadlines` and `case.deadline` are read-only,
recomputed projections; they do not bump revisions or write derived statuses.
The clock anchors the earliest valid accepted initial draft, not `last_sent_at`.
Rules have scoped receipt adjustments and official citations. Calendar/time-zone
coverage is intentionally disclosed as a planning estimate, not legal verification.

Reviewed inputs live in the existing encrypted `case.deadline_tracking` object
and case event trail, with no schema migration or change to old tracking fields.
`desk_save_deadline_tracking` is revision-controlled. Linked evidence must belong
to the case and have no thread conflict. Evidence reassignment and new messages
invalidate the relevant review assumptions without editing transport receipts.
The initial checkpoint, explicit next checkpoint and legacy recorded dates remain
distinct. The module never reads bodies, calls a model or accesses the network.

`static/deadlines.js` provides an all-workflow queue, source details and a separate
evidence editor. Its one-minute visible-page timer reads only `desk_get_deadlines`;
it preserves unsaved inputs and never synchronizes mail, sends or files appeals.
Browser and native schemas share `static/deadline-contracts.mjs`. See
[deadline behavior and limitations](DEADLINES.md).

## MA response review helper

`app/ma_follow_up.py` combines a reviewed public routing profile with encrypted
per-case `ma_response_reviews`. The three native operations are also served by
the guarded HTTP dispatcher; `static/ma-follow-up.js` embeds the editor in the
case workspace. `desk_get_case` includes its read-only MA projection. Reviews
and event snapshots commit atomically under the normal mutation lease. No
original case stages, send receipts, deadlines or routing fields are rewritten.
Read-only text previews bind the reviewed message/case revision and require
existing correspondence/immutable-draft tools for any subsequent send.
`static/ma-contracts.mjs` marks these tools native-only for page registration,
preserving the 64-tool WebMCP budget. See [MA workflow](MASSACHUSETTS.md).

## Public request snapshot

### State guides and reviewed public-directory collection

`state_guides.py` exposes read-only available guides from the existing timing
registry and MA routing profile. `static/state-guides.js` automatically displays
them when the selected state changes, collapsed by default. No guide is invented
for an uncovered state. Source refresh never edits bundled legal rules.

`public_sources.py` registers a single reviewed Massachusetts elections directory.
`desk_refresh_source` uses a fixed HTTPS host/path, standard TLS verification,
no proxies/cookies/credentials/redirects, 12-second socket timeout, bounded total
reading and a 2 MB ceiling. HTML is parsed as text only. A complete 351-name
roster check rejects missing/duplicate sections; malformed/blocking pages never
replace the last good collection. `desk_import_source` is a separately labeled
operator-reviewed complete plain-text fallback (200,000-character bound), not
independent confirmation that the app fetched the official page. Older imported
check dates cannot replace newer saved checks.

Snapshots, full source text/hash, source-check and server-side collection dates,
method, contacts and attempt history are encrypted as `source` / `source_snapshot`
records. Pointer and snapshot save atomically under the normal mutation lease.
At 100 attempts the source refuses further writes without discarding history.
The public `ma-municipalities.json` contains names only, not contact observations.
The paginated municipality lookup never maps town names onto county IDs or
promotes holder contacts to verified RAOs. No case/mail/routing records change.

`static/settings.js` supplies accessible source controls and safe result/debug
dialogs, rendered with textContent. Opening Settings only reads saved metadata;
explicit refresh is separate from reload. `source-contracts.mjs` marks five tools
native-only to preserve the page-tool budget. The dashboard serves the same
guarded operations. See [Settings](SETTINGS.md) and [MA workflow](MASSACHUSETTS.md).

### Historical starter snapshot

The historical snapshot remains distinct from local reusable templates and
campaigns. Refreshing it is a maintainer operation and does not replace locally
saved cases, templates, identities, drafts, or receipts.

The versioned snapshot contains public template content, state metadata and the
public `records-response.yml` intake form from CivicResultMaps. It never queries
the private workflow database or Bridge. Its provenance file records each source
path, byte count, SHA-256, source commit when available, and generation time.

Normal startup validates the catalog's self-consistency and exact form digest.
Hashes detect accidental drift, not malicious changes by someone who can edit
the code and recompute hashes. Requester placeholders are a guardrail, not a
general personal-data detector. Review all generated content before committing.

To refresh deliberately from a reviewed, trusted CivicResultMaps checkout:

```powershell
npm.cmd run snapshot:refresh -- 'C:\path\to\CivicResultMaps' --trusted-source
```

This is a **maintainer operation**, not an assistant tool or automatic update. It
executes the two known TypeScript request loaders and state metadata module in
the provided checkout, using this project's pinned TypeScript compiler. Trust
and review that source before running the command. No credentials or private
mailbox inputs are needed. Stop the dashboard and mail-tool use during refresh
to avoid reading between the generated file replacements.

The builder validates inputs before generating the catalog, form, workflow map,
and provenance. Review all four changed outputs, current official routing, and
any changed form fields. The standalone test pins the extraction's original
catalog digest; an intentional refresh requires reviewing and updating that
fixture. Do not blindly update the expected digest merely to pass a test.

`.gitattributes` preserves the catalog, form and generated map byte-for-byte.
Do not normalize those artifacts' line endings: the form has an exact SHA-256
identity. Use the refresh command and review the resulting digest instead.

The map is derived from the source checkout's county display geometry. It is a
workflow navigation illustration, not a new official boundary release. This
extraction does not collect, normalize, or publish new election boundaries.

`static/map-controls.mjs` is a shared, dependency-free SVG display controller for
the national and county maps. It owns bounded viewBox navigation, pointer/pinch,
modifier-wheel and keyboard handling, layer switches and a synchronized legend.
Old SVG listeners are aborted on redraw; the viewport survives same-scope
refreshes and selection, but resets when the county state's geometry changes.
Only boolean layer/legend preferences are kept in browser localStorage under
versioned per-map keys; no case/mail/identity payload is stored there. Preference
storage failure does not block the map. The read-only page overview includes the
display snapshot. No map control calls a backend mutation or changes source assets.

## County request-status projection

The separate read-only county status projection in `app/county_progress.py`
uses saved cases, exact county identities, linked response evidence, receipts
and existing deadline projections. `desk_list_counties` can include it for one
state without adding a tool. `static/county-progress.js` renders the map/list
and opens the existing case workspace. The public Census-derived
`static/county-map.json` is separate from the byte-preserved legacy state map;
no runtime remote maps or geography writes occur. See [county status](COUNTY-STATUS.md).

## County contact research

`app/contacts.py` owns the county/role directory and leased agent research queue;
`app/static/contact-contracts.mjs` registers the same 11 operations for native
MCP and WebMCP. `app/static/contacts.js` provides the dashboard view. See
[contact research](CONTACT-RESEARCH.md) for schemas, evidence semantics and recovery.

The public `app/counties.json` is a pinned, reproducible Census names/IDs baseline,
not contact data or a jurisdiction-to-government crosswalk. Saved observations
use encrypted `contact` records keyed by exact county ID/role. Each retains
immutable history, source-check dates and server-side collection timestamps.
Existing exact county-scoped case recipients are read-only leads with no inferred
role verification. A lookup includes missing inventory entries, not only saved rows.

Each encrypted `contact_batch` embeds bounded state/role tasks. The existing
cross-process operation lease serializes local mutations; separate 20-minute
task leases coordinate research outside the app. `Database.put_many` atomically
commits a returned observation and completion receipt, preserving encryption,
identity and capacity checks. Workers never hold the database operation lock
during web research. County research has no embedded model, URL-fetch endpoint or
auto-send path; the separate public-source collector fetches only its registered
directory. Native host allowlists remain operator-managed; the shipped example is
kept consistent with the complete public tool schemas.

## Public intake is a separate action

For cases from the optional legacy starter pack, the publication target remains
the CivicResultMaps `records-response.yml` issue workflow in
`Camreyn/civicresultmaps`. Creating this standalone repository does not create
a new data intake destination. Preparing
an issue is private; publishing requires reviewed/redacted content, an exact
preview/digest and a separate explicit action by the operator or authorized
assistant. There is no additional CivicRelay confirmation dialog. This app does not commit election
data, upload raw files automatically, import to a production database, or merge
pull requests.

An operator may save a local GitHub owner/repository destination and prepare a
preview for it. The destination definition is copied into the immutable preview
digest. Editing, disabling, or replacing that destination invalidates the old
preview; prepare a new exact preview before publication. Local private exports
are independent of GitHub and never upload, publish, or create a destination.

## Direct actions in 0.4.0

The HTTP, native MCP and page-tool paths all use the same guarded Python workflow.
Send/publish calls retain required identity and digest arguments; their former
approval-only `confirmation` arguments are removed and rejected as unknown fields.
Exports require the selected issue identity and revalidate its snapshot before
writing a private ZIP. No per-action Tkinter approval module is loaded. Tkinter
remains only for local credential enrollment and certificate trust decisions.

User authorization can delegate a workflow to an assistant; the application does
not itself evaluate conversation-level authority. The dashboard trusts its local
session and MCP tools rely on their host's permissions. The host configuration
is unchanged. This change adds no scheduler, automatic retries or blanket
authority derived from incoming email. See [security boundaries](SECURITY.md).
