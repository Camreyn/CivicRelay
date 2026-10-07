# CivicRelay 0.7.1 — Empty Proton folder/label compatibility

## Fixed

An empty selected Proton folder or label could cause **Mailbox search failed or
was too large** in the dashboard, or **Bridge search failed or exceeded the
result limit** through assistant tools. Bridge/Gluon can reject UID SEARCH on
an empty mailbox instead of returning no matches.

Both interfaces now check read-only folder metadata first. Empty folders and
empty eligible message ranges return zero messages without searching. Nonempty
searches use a bounded numeric UID range; genuine search errors, malformed
responses, size limits and changed mailbox identity still fail closed.

Existing scope/history choices, credentials, saved requests, drafts, receipts,
quota and local evidence remain unchanged. The next explicit check can import
a new arrival; this patch adds no polling, sending or historical rescan.

## Update

Follow the [Git/ZIP upgrade guide](UPGRADING.md). Stop old dashboard/tool
processes, update the complete source, run **Install CivicRelay.cmd**, and
restart the dashboard and both assistant connections. Confirm version **0.7.1**.

If your 0.7.0 scope is already saved, keep it. Do not reapply a new-only scope,
enable history, add dummy mail, switch to dedicated mode or reset credentials.
Click **Check for replies**: empty labels should show **0 new headers synced.
Mailbox check complete.** No new tool permissions or dependencies are required.

## Verification scope

The regression fixtures reproduce the empty-label rejection before the fix and
cover both mail interfaces, both label roles, subsequent arrivals, safe bounds,
pagination, invalid metadata, search failure and mailbox-identity changes.
The browser regression covers the real dashboard → HTTP → service → disposable
storage flow with a synthetic Bridge. No live mailbox, real email send or
account reset is part of verification. See [test details](TESTING.md).
