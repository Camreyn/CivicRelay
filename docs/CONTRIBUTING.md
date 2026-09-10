# Development and release checklist

## Small, reviewable changes

Read [architecture](ARCHITECTURE.md), [privacy/security](SECURITY.md) and the
[operator workflow](OPERATOR-TOOLS.md). Preserve user edits and immutable saved
identities. Keep tests synthetic. Do not change confirmation, quota, TLS,
environment, storage or publication boundaries as a convenience fix.

Source layout is described in the root README. Python uses the standard library;
JavaScript packages are locked. Node/MCP tests require the configured Python
executable, not a hardcoded runner location. Supported operation is Windows
under a normal interactive user; Linux/macOS/cloud runtime support is not claimed.

When changing a native schema, update the Python allowlist/validation and shared
page schema consistently, then run:

```powershell
npm.cmd run docs:generate
npm.cmd test
```

Review the generated reference, rather than hand-editing it. If UI behavior
changes, also run `npm.cmd run test:browser`. Do not use screenshots of real
correspondence as fixtures, documentation images or bug-report attachments.

Snapshot refresh is a separate reviewed action; see [architecture](ARCHITECTURE.md).
Do not update the expected digest just to make a test pass. Preserve source
authority, identifiers and caveats. The example map is not an official boundary
product. A records-data source update does not authorize production publication.

## Before committing

1. Run `npm.cmd test`, `npm.cmd run test:browser` and `npm.cmd run publish:check`.
2. Run `npm.cmd audit` and review any dependency findings; a zero count is not a
   comprehensive security audit. Avoid unnecessary dependency upgrades.
3. Review `git status --short` and all proposed source/docs changes. Use explicit
   source paths when staging; never force-add ignored files or stage `.private`.
4. Review `git diff --cached` and run the publication check again. It inspects
   both working files and staged blobs so an unsafe staged version cannot hide
   behind a cleaned-up working copy. No check substitutes for human review.
5. Confirm generated snapshots keep exact bytes, machine configuration is absent,
   and no real mail, export, requester detail or credential is in the commit.

## Before pushing a release

- Confirm the destination is `Camreyn/CivicRelay` and inspect existing branches.
  Never force-push or replace another contributor's work.
- Rehearse the exact commit in a fresh checkout with the documented install/test
  commands. A successful test in an old, dependency-rich checkout is insufficient.
- Publish only the reviewed source commit. Code publication is separate from
  permission to send email, submit records, create data issues or change accounts.
- Verify the remote commit and Windows CI result. Record any verification limits;
  do not claim real delivery or production ingestion based on mocked tests.

The source repository's `private: true` npm flag prevents accidental npm package
publication; it does not make the GitHub repository private. Assume every pushed
file, branch name, commit message and author field is public.

## Existing operator installations

The original folder may remain named `CivicRecordsDesk`. Preserve its ignored
configuration and research directories during updates. Do not rename the legacy
Windows storage namespace or re-enroll Bridge because the public app was renamed.
Stop only the identified dashboard, and only while no mail/approval operation is
active, if a server restart is required. Native tool connections may also need a
restart after tool-code/schema changes. Do not start detached STDIO servers.
