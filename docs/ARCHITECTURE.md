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

The legacy `%LOCALAPPDATA%\CivicResultMaps\` namespace is intentional. Changing
it during code relocation would appear to create a new mailbox history and
could separate send-limit accounting from existing drafts. Multiple checkouts
under the same Windows user share that same account/store; they are not isolated
mail accounts. Do not run competing versions against live data.

The original catalog digest, case IDs, draft IDs/digests, message IDs and source
identifiers are preserved. Existing saved case content and immutable drafts are
not rewritten when a new public catalog is installed.

## Public request snapshot

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

The supported publication target remains the CivicResultMaps
`records-response.yml` issue workflow in `Camreyn/civicresultmaps`. Creating this
standalone repository does not create a new data intake destination. Preparing
an issue is private; publishing requires reviewed/redacted content, an exact
preview and a separate human confirmation. This app does not commit election
data, upload raw files automatically, import to a production database, or merge
pull requests.
