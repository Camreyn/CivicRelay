# Guided application updates

Version 0.9.0 adds **Settings → Updates**. Older installations need one manual
[Git/ZIP upgrade](UPGRADING.md) to obtain this feature. It updates application
code, not the mailbox, public-source directories, or saved request definitions.

## Checks and approval

**Check for updates** contacts the fixed public `Camreyn/CivicRelay` GitHub release
service. Optional automatic checks are **off by default**. If enabled and saved,
they run while the dashboard page is visible, at most once per 24 hours (including
failed checks), on startup/return to the page or the hourly eligibility check.
They do not run when the app is closed. The Settings button marks a newer release.
Manual checks are independent of this interval. Turning the preference off stops
future automatic checks; an already-started check can still finish.

Checks send no credentials, requester details, mailbox data, local paths or
installation IDs. GitHub sees the ordinary public request, including its source
IP. No account login is needed. Checks never download or install software,
poll mail, send requests, or change assistant permissions. Failures keep the
previous release information visible and perform no automatic retry.

Review the version and release notes, then choose **Approve and download update**.
The exact version, tag commit and SHA-256 package digest are rechecked before
download. Changed releases require a new review. Only a published stable release
with the dedicated `civicrelay-vX.Y.Z.zip` asset and valid GitHub digest is accepted;
the automatically generated source ZIP is not a fallback. Release notes display
as literal text, never executed HTML or instructions.

The downloaded ZIP is checked against GitHub's SHA-256 metadata, an internal
per-file manifest, the source commit, package versions and required files.
Private paths, duplicates/case collisions, Windows reserved names, traversal,
linked/encrypted entries and oversized archives are refused. Metadata and downloads
use standard HTTPS verification, fixed hosts, no environment proxies, credentials
or cookies, and bounded time/size. Only GitHub's official release-asset redirect
is allowed. This provides integrity tied to the official repository over HTTPS;
it is **not** an independently signed publisher package and does not protect
against a compromised maintainer account, GitHub or same-user malicious software.

A ready/extracted plan cannot be silently replaced by another approval. Cancel
a ready plan explicitly before choosing a different download. Failed/cancelled
plans and their archives are retained in local receipt history when retrying;
an extracted plan requires completion review, not a blind retry. Dashboard writes
and installer extraction/completion use a shared OS-level updater lock.
Receipt history has a 100-entry/2 MB limit checked before writing. Capacity
failures retain the existing readable state and require a reviewed manual upgrade.

## Install and switch over

Downloading does **not** install the update. Follow the visible steps:

1. Finish active operations. Close the dashboard **server**, not merely its tab,
   and stop both CivicRelay assistant MCP connections. See
   [shutdown guidance](SETUP.md#runtime-paths). Never kill all Python/Node processes.
2. In the **current** app folder, double-click **Update CivicRelay.cmd**. Review
   the approved version and destination, then type `INSTALL` to approve installation.
   Cancellation changes no installation files. Busy dashboard/MCP/worker processes
   are refused, not stopped. The check also identifies standard absolute-path
   processes from other CivicRelay folders by their public package identity, and
   conservatively refuses ambiguous relative app/tool paths. Renamed/custom
   wrappers cannot be conclusively identified: still stop all CivicRelay
   connections yourself. This helper has no unattended/yes mode.
3. The installer re-verifies and extracts into a **new sibling folder**, installs
   locked dependencies with lifecycle scripts disabled, and runs synthetic tests.
   It reuses compatible runtimes; it does not install system prerequisites, enroll
   mail, read/copy private stores, or generate assistant configuration. Only validated,
   non-secret executable paths are saved in the new folder.
4. Wait for the explicit success report. Open **Open CivicRelay.cmd** in the new
   permanent folder and update your shortcut yourself. Review existing assistant
   `command`/`args`/`cwd` paths for that folder, preserving allowlists and permissions;
   reconnect both connections. Do not create duplicate connections or run both versions.
5. Confirm the new version through `/health` or `desk_status`, and inspect your
   saved workspace/templates. No credential re-enrollment or mailbox-scope reset
   is needed. The updater adds **no native or page tools**.

## Data preservation and recovery

Templates, requester defaults, campaigns, cases, correspondence, immutable drafts,
receipts, send-attempt accounting, mailbox scope and credentials remain in the
same encrypted Windows-user AppData stores. The installer never opens, copies,
exports, migrates, resets or deletes them. Use the same Windows user and retain
the existing storage namespace. A source update is not a data backup.

The original application folder is untouched, including local code edits and its
`.private`, `.local` and `.codex` directories. These directories are **not copied**
to the new installation: old research remains available in its original folder;
existing host configuration is manually reviewed rather than silently duplicated.
Update preferences/cache are installation-local; the new folder starts with
automatic checks disabled. Existing destinations are never overwritten.

Failed installation leaves the current installation untouched and retains an
incomplete new folder for review, without automatic activation, deletion or retry.
Reload update status to inspect the saved stage. Approve a fresh download to retry.
An `extracted` stage is not a success receipt; rerun/review the installer outcome.
The old code is retained for **reviewed** recovery, not automatic downgrade:
older code may not support newer identity/schema/privacy rules. Never roll back
or copy the live databases automatically. Review release-specific compatibility
before returning to an older application. Keep old privacy-unsafe versions stopped.

## Maintainer release package

After the normal [release checks](CONTRIBUTING.md), commit all reviewed source
changes and use a clean checkout of the exact release commit:

```powershell
npm.cmd run release:package
npm.cmd run test:update-package
```

The builder validates public paths/bytes, reads only tracked Git blobs from that
commit, and writes the deterministic asset under ignored `.local/release/`.
It includes a version/commit/per-file-hash manifest and verifies its own archive.
No working-tree/private data, dependencies or machine configuration are packaged.
The rehearsal uses the actual archive/installer, locked dependency setup and unit
tests with fictional AppData/config/research sentinels. Live process detection is
mocked (covered separately by installer tests); no dashboard/MCP is activated.
Rehearse that exact asset in a disposable installation, then upload it to the
matching stable GitHub release tag. Confirm GitHub exposes its matching `sha256:`
asset digest before announcing guided-update availability. Do not substitute
another commit's asset, use a draft/prerelease, or force-replace a released tag.
See [GitHub asset metadata](https://docs.github.com/en/rest/releases/assets).
