# Historical standalone extraction — 2026-09-10

The project is now published as **CivicRelay**. The original operator's local
folder remains `CivicRecordsDesk` to preserve existing shortcuts and configuration.
This page describes that installation's move, not a required step for new clones.
A public clone has no private migration backups, research or original-path shims.

## Scope

The dashboard and Proton connector were extracted from the CivicResultMaps
checkout into a sibling **CivicRecordsDesk** project. The extraction adds its own
package manifest/lockfile, runtime paths, public template snapshot, launchers,
tests, documentation, local Git repository and ignored machine configuration.
It does not publish code, send mail, submit records, or import election data.

| Previous location | New location |
| --- | --- |
| `CivicResultMaps/local-records-desk/` runtime | `CivicRecordsDesk/app/` |
| `CivicResultMaps/tools/proton-mail-connector/` | `CivicRecordsDesk/connector/` |
| Runtime reads from parent TypeScript/data | Reviewed `CivicRecordsDesk/data/` snapshot |
| Local research collection and helper scripts | `CivicRecordsDesk/.private/` |
| Custodian research and operational notes | `CivicRecordsDesk/.private/operations/` |
| Original source, private screenshots and old documentation | `CivicRecordsDesk/.private/migration-backup/` |
| Live encrypted account/case storage | Unchanged, outside both repositories |

No private database, DPAPI key material, or mailbox credentials are moved or
decrypted by the migration. Existing case/draft/message IDs, catalog hash,
receipts and send-limit ledger are preserved. The local URL and public issue
intake target are unchanged.

## Compatibility

The CivicResultMaps project's two mail-tool configurations are redirected to
the sibling project without changing enabled tools or approval requirements.
The standalone project's own ignored `.codex/config.toml` registers only those
two mail-related servers.

That describes the extraction's original behavior. Version 0.4.0 subsequently
removes CivicRelay's per-action send, public-issue and local-export dialogs and
the approval-only tool arguments. It does not change the host's permission
configuration or migrate private stores. See [setup](SETUP.md) and
[operator tools](OPERATOR-TOOLS.md) for the current workflow.

Small, ignored forwarding files remain at the two old paths for already-loaded
MCP sessions and old launch shortcuts. They contain no mailbox data, credentials,
or second copy of the application. Restart the two mail MCP connections to load
the direct new paths. Do not launch a detached STDIO server or stop unrelated
project MCP processes. Remove the shims only after all old sessions/shortcuts
have been retired and no old worker path is in use.

The app still uses `%LOCALAPPDATA%\CivicResultMaps\...` when that legacy
namespace already contains connector or records data. That name is an existing
data namespace, not a runtime dependency on the old source checkout. Do not
rename it as a cosmetic cleanup. Fresh v0.6.0 installations use the separate
`%LOCALAPPDATA%\CivicRelay\...` namespace. If both contain data, startup fails
closed rather than selecting, copying, or merging a store.

The source baseline and legacy v1 data are preserved, not automatically
converted. v1 draft IDs, digests, `From` representation, receipts, and quota
remain valid under legacy settings. v2 settings add a profile-bound draft
identity and require current code for v2 drafts. Do not downgrade to older code
after enrolling v2 settings unless you have reviewed compatibility; do not use
rollback as a way to re-enroll or reset an account.

## Preserved research

Original collection files keep their bytes and recorded source provenance.
Historical manifests or encrypted case notes may contain old absolute local
paths. Resolve those using the migration mapping above instead of rewriting
recorded acquisition evidence. The private migration inventory records old/new
paths and hashes for local verification; it is not a public artifact.

## Rollback

1. Stop use of both mail-tool connections. Ensure no send, publication, approval
   window or mail operation is in progress. Stop only the identified dashboard.
2. Preserve any new code/private work in this project. Never delete or replace
   the live `%LOCALAPPDATA%` stores.
3. Inspect `.private/migration-backup/` for the original app/connector/config.
   Restore their files to the exact original paths only after reviewing the
   forwarding shims and any later edits. Check the recorded original file hashes.
4. Restore only the two relevant configuration sections, preserving unrelated
   project changes. Restart the two mail MCP connections and original dashboard.
5. Verify catalog identity, compact case statuses, local send policy, and a
   read-only Bridge connection check. Do not send a test email as part of rollback.

Rollback is a reviewed manual operation, not an automatic script. Do not use a
recursive delete, broad process kill, reset, or database restore to implement it.
After future schema changes, old application code may no longer support current
data; in particular, v2 mailbox settings require code that understands their
profile-bound draft format. Assess compatibility before rolling back a later
release.
