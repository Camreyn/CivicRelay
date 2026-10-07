# Updating CivicRelay to 0.7.1

This release contains the guided installer and the mailbox-privacy fix. The old
0.6.1 release ZIP does not. Updating code alone neither deletes accidental mail
imports nor chooses a new mailbox scope.

**Already on 0.7.0?** This patch fixes mail checks on empty selected Proton
folders/labels. Follow steps 1–3, then keep your saved scope and click **Check for
replies**. Empty labels should report **0 new headers synced. Mailbox check
complete.** Do not re-preview/apply a working scope just for this patch: that
would move a new-only boundary and could skip mail that arrived since setup.
There are no new tools, dependencies, data migrations or permission changes.

## 1. Stop the old code

Finish any active send/publication operation first. Stop the dashboard server and
both CivicRelay assistant MCP connections. Closing a browser tab alone is not
enough. For a foreground dashboard, use Ctrl+C in its terminal. For a hidden
dashboard, identify the process whose command line points to this installation's
`app/server.py` and stop only that process; never kill all Python or Node processes.
See [runtime paths and shutdown](SETUP.md#runtime-paths).

Use the same normal Windows user. Do not delete, reset, move or copy the live
AppData databases to “start fresh.” They contain private cases, sender identity,
drafts, receipts and quota accounting. Preserve ignored `.codex/`, `.local/` and
`.private/` directories. A Git clone is not a backup of your records; any backup
must preserve the Windows-user recovery context described in [security](SECURITY.md).

## 2. Install the new code

### If installed with Git

In your CivicRelay folder:

```powershell
git status --short
git switch main
git pull --ff-only origin main
```

Stop if Git reports local changes or diverged branches; do not discard them or
use a hard reset. Have those changes reconciled before continuing. This is for
the normal `Camreyn/CivicRelay` clone, not the separate CivicResultMaps repository.

### If installed from a ZIP

Download the **Source code (zip)** for [v0.7.1](https://github.com/Camreyn/CivicRelay/releases/tag/v0.7.1).
Extract the entire archive into a new, permanent local folder. Keep the old
installation as a rollback/reference copy, but do not run its old mail tools.
Move/copy no private AppData databases into either checkout.

Preserve your local research and configuration. If keeping the new folder name,
update existing assistant connection paths (`command`/`args`/`cwd`) to this
installation and add the five privacy tools if desired, keeping existing
permission choices. Do not create duplicate connections or replace your whole
configuration with a placeholder. Alternatively, with all old processes stopped,
place the new source at the original installation path and retain the old ignored
configuration/research directories there. Do not merge old source files into the
new release; retain only those local ignored directories.

## 3. Refresh requirements and restart

Double-click **Install CivicRelay.cmd** in the updated folder. It refreshes the
locked dependencies, checks runtimes and runs synthetic tests. It does not
re-enroll Bridge, reset data or overwrite an existing assistant configuration.
The installer is not an automatic source updater.

Open **Open CivicRelay.cmd**, reload the page, and restart the assistant
connections using the updated paths. Use `desk_status` (or `/health`) to confirm
`tooling_version: 0.7.1`; `proton_status` also reports `version: 0.7.1`.
If it reports an older version, an old process/connection is still in use.

Assistant allowlists from before 0.7.0 may need these additions (unchanged in 0.7.1):

```text
desk_get_mail_scope
desk_preview_mail_scope
desk_apply_mail_scope
desk_preview_mail_cleanup
desk_apply_mail_cleanup
```

See the complete [configuration template](mcp-config.example.toml) and
[assistant configuration upgrade](SETUP.md#upgrading-an-existing-assistant-configuration).
The new total is 66 records tools plus 8 mail tools; the WebMCP budget stays 64.
Low-level `proton_read_message` additionally requires `mail_scope_id` from the
latest `proton_list_messages` result. Restart connections to load the new schema.

## 4. Make the one-time privacy choice

Skip this step if your reviewed 0.7.0 scope is already saved and still valid.
Otherwise open **Settings → Mail privacy**. Older installs pause remote mail reads
until a scope is previewed and applied. This is intentional; the old account
attestation did not reliably protect a personal inbox.

- **Personal account:** choose custom CivicRelay folders only. Never select
  dedicated mode for that account. Default is no historical import.
- **Genuinely dedicated account:** choose Inbox and Sent. If preserving access to
  old unassigned correspondence is intentional, explicitly include history;
  otherwise the new boundary hides it without deleting it. Existing case-linked
  evidence remains locally available either way.
- **Accidental old imports:** configure the correct scope, then separately review
  and apply the local cleanup preview. It never deletes Proton originals.

Follow the [mail privacy and recovery guide](MAIL-PRIVACY.md), including its Sent
folder, filtering, UID-reset, evidence-protection and prior-disclosure limitations.
No need to buy another account or re-enter Bridge credentials just to update.
Do not downgrade to an old mail connector that lacks these scope checks.
