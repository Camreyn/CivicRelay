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

## Public request snapshot

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
