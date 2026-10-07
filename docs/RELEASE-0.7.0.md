# CivicRelay 0.7.0 — Mailbox privacy and recovery

## Fix

Previously the initial sync began at UID zero in Inbox and Sent. The dedicated-
mailbox setup warning did not prevent unrelated historical headers from entering
the app when a personal account was enrolled. Bodies could then be retrieved by
the user or a connected assistant. This was a mailbox-selection gap, not an
upload of private mail into the public Git repository.

- Require a reviewed scope before remote mail reads, including on upgrades.
- Default new scopes to the preview's UID boundary; history is an explicit opt-in.
- Support exact custom incoming and optional Sent folders/labels for personal
  accounts; enforce the same boundary in dashboard and low-level assistant tools.
- Pause rather than silently rescan if a mailbox UIDVALIDITY changes.
- Hide out-of-scope unassigned local imports; preserve case-linked local evidence.
- Add preview/digest-bound, atomic local cleanup of unrelated imports, with
  conservative evidence/draft-chain protection and header-hash exclusions.
- Add Settings → Mail privacy, a setup banner, five native tools and recovery docs.

Also includes the current guided Windows installer, county maps/contact tooling,
source-linked deadlines, state guides, MA review tooling, map controls and
fictional README screenshots that were added after the old 0.6.1 archive.
The development-only MCP client is updated to 2.3.1 to address its OAuth advisory;
the application uses local STDIO, not that OAuth client flow. No runtime transport
permissions, credentials, send quotas or TLS protections were removed.

## Update

Read [UPGRADING.md](UPGRADING.md) for Git and ZIP installations. Stop old dashboard
and tool processes, update source, rerun **Install CivicRelay.cmd**, restart, and
choose a scope in **Settings → Mail privacy**. Existing Bridge credentials and
private stores stay in place. Cleanup is separate and never deletes Proton mail.

## Important limitations

- Dedicated mode still trusts the operator's assertion that the selected address
  is dedicated; use custom-folder mode for a personal account.
- Only chosen folders are watched on an explicit check. CivicRelay does not move
  messages or set Proton filters. A blank Sent path disables remote Sent inspection.
- No automatic polling, background sending, retries, or cross-account migration.
- Cleanup does not erase exports, backups, copied notes or prior model transcripts.
- A UID-reset recovery preview can skip pending mail if “start from now” is chosen;
  inspect the source folder and deliberately choose history if needed.
- Tests use synthetic mail and mocked IMAP; no real mailbox or send is a test.

See [MAIL-PRIVACY.md](MAIL-PRIVACY.md) for full behavior and safeguards.
