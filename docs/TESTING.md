# Testing and verification limits

## Requester-default coverage (v0.8.0)

`app/test_general.py` covers all seven saved values and enable switches, strict
partial updates, contact-email/sender separation, old-profile compatibility,
disabled required fields, explicit blanks and frozen cases. Equipment regressions
check the neutral new sign-off and preservation of existing final sign-offs.
`app/requester-defaults.browser.test.mjs` exercises the actual Settings → HTTP →
encrypted synthetic workspace → template → immutable draft flow, including
one-off controls for undeclared built-ins, inherited-value refresh, stale edits,
lost-response recovery, export privacy and mobile layout. No live account or
correspondence is used. The suite includes 333 unit tests and 13 browser workflows.

## Configurable sending-limit coverage (v0.8.0)

`connector/test_send_policy.py` covers default/read-only old-store behavior,
raising and lowering limits, exact window/spacing boundaries, unchanged attempt
history and uncertain states, stale/concurrent edits, current-policy rechecks
after preflight, corrupt-policy rejection, and same-identity credential updates.
`app/test_sending_limits.py` checks strict service arguments, unconfigured behavior,
no network and no implicit sending enablement. Native MCP handshake tests exercise
the getter and safe unconfigured save rejection; configuration tests verify both
new native tools and unchanged host permission choices.

`app/sending-limits.browser.test.mjs` starts a disposable real HTTP/service/store
fixture with ten fictional attempts and all mail transports blocked. It checks
Settings save/reload persistence, invalid input, preserved unsaved edits, stale
revision rejection, lost-response recovery without retry, lower-cap enforcement,
keyboard tabs and a synthetic screenshot. No real Proton limit or delivery is
tested. This is included in `npm.cmd run test:browser`.

Local verification on 2026-10-07: 68 Node tests, 196 app Python tests and 64
connector Python tests passed (328 total), plus all 12 browser workflows.
The first full run exposed a new test-module naming collision; unique test names
fixed discovery and the Python/docs groups then passed. No live mailbox or
provider-account limit was tested.

| Feature boundary | Result and evidence |
| --- | --- |
| Settings renders | Synthetic screenshot reviewed; no browser page errors |
| Settings → HTTP | Exact cap, spacing and revision sent; invalid inputs blocked |
| HTTP → private store | Saved policy persists after reload; prior ten attempts retained |
| Store → send enforcement | Raised/lowered caps, cooldown boundaries and changed-policy final claims tested |
| Response → Settings | Updated usage displayed; stale/lost responses preserve edits without retry |

## User story under test

A fresh Windows user starts blank, configures a workspace, creates and versions
their own template, adds federal/local campaign targets, saves a scoped request,
prepares exact correspondence and tracks replies/coverage independently of
optional publication. Existing users retain legacy identity and request history.

A human or assistant selects a request, saves reviewed local correspondence,
prepares an immutable draft, explicitly requests the authorized external action
without a CivicRelay approval dialog, and reviews the resulting receipt/status.
Replies and source files remain
private until a separately reviewed public intake action.

## Repeatable checks

```powershell
npm.cmd ci --ignore-scripts
npm.cmd test
npm.cmd exec -- playwright install chromium
npm.cmd run test:browser
npm.cmd run publish:check
```

Set the installed Python/Node paths as described in [setup](SETUP.md) first.
`npm.cmd test` includes Node tests, Python tests and documentation checks. No
Bridge account, GitHub authentication, API key or real email is required.

The guided installer runs this same synthetic suite after dependency setup.
`npm.cmd run test:install` can run its Windows bootstrap regression separately:
package-manager actions are mocked, configuration writes use disposable
directories, and actual runtime probes are read-only. It covers first/repeat
installs, ZIP-style source without Git, path handling, failure recovery and
preserved host settings. It is not a fresh-VM/UAC or live-account test.

| Boundary | Evidence supplied by the suite | Limit |
| --- | --- | --- |
| UI → local API | Real Chromium with the actual static app and synthetic loopback responses; map, navigation, form preservation, countdown and errors | No real account or agency action |
| MCP → worker | Actual STDIO handshakes, public schemas, strict arguments and isolated unconfigured profiles | Tests do not enroll a real mailbox |
| Generated config → MCP | Actual generated TOML parsed, complete tool allowlists checked, both servers launched from generated paths/environment, private template/campaign workflow exercised | SDK rehearsal, not a Codex UI/trust/permission test |
| Workflow → storage | Synthetic case/mail/artifact records, revision/lease behavior and restart tests | Does not audit the live operator's database |
| Encryption/storage guards | Windows DPAPI round trips using synthetic values, tamper/link/repository-path rejection | Not a third-party cryptographic/security audit |
| Send → receipt | Direct send without Tkinter/confirmation arguments, mocked SMTP, exact digest, quota, concurrency, uncertain outcomes and duplicate prevention | No real message sent; delivery is not tested |
| Intake → public issue/export | Direct actions without approval modules, mocked GitHub, exact form/snapshot identity, private-link guards and uncertain-publication handling; synthetic ZIP byte checks | No public issue or real-record export created by tests |
| Docs → implementation | Local links/npm commands checked; 76-tool reference compared to source schemas | External pages and prose still need human review |
| Fresh workspace → templates → campaign | Synthetic strict-schema, safe-rendering, immutable-version, private-field, idempotency, target retention and linked-evidence tests | Literal template text still needs privacy and procedural review |
| Configured destination → exact preview → receipt | Synthetic destination-revision invalidation, exact repository URL verification, unresolved-attempt locks and local case ZIP checks | Remote form schema/labels are not fetched or validated automatically |
| Account profile → storage/draft | Synthetic v1 compatibility, fresh v2 identities, display-name/header and profile digest binding, ambiguous-store refusal | No new real account is enrolled or used by tests |
| Equipment campaign UI → HTTP → database | Actual handler and isolated synthetic store; 51-state tracker, remaining-state filter, saved notes survive reload, unverified dates rejected | No actual agency deadline, fee acceptance or email delivery tested |
| Deadline queue → API → saved evidence | Synthetic clocks, map outlines, official links, dirty-form preservation, recorded commitments survive reload and automatic read-only refresh | Not a legal opinion, complete state/local holiday calendar or live statutory-change monitor |
| Source → publication | Git-visible path allowlist, regular-file checks, limited token/key markers, staged blobs and catalog/form integrity | Not comprehensive redaction, secret detection or permission review |

The browser fixture binds to an ephemeral port, denies non-fixture network
requests, closes its browser/server, and produces only ignored synthetic
screenshots. A fixture's “send call” means a call to the fake local handler,
not an email. Tests use temporary profiles for worker mail operations; do not
replace those fixtures with the operator's real account.

The separate [README screenshot fixture](SCREENSHOTS.md) serves the real UI with
invented data, disposable storage, a read-only operation allowlist and blocked
outbound transports. Its three manually reviewed documentation images are the
only binary publication exceptions, pinned by exact hashes. Unit tests reject
changed/unlisted images and check JPEG metadata; they do not detect visual PII.

## Windows test startup

Windows PowerShell 5.1 validation inputs are batched within one disposable test
process to avoid repeated cold starts on hosted runners. Each test process has
a bounded 60-second startup/execution budget. This does not skip validation,
retry failed checks, or change the installer's or mail connector's timeouts.

## Reply send-status regression

`app/test_send_reconciliation.py` covers consecutive accepted messages, recovery
of older stale status, one-time legacy identity backfill, preserved operator
stages, idempotence, invalid/uncertain receipts across case families, read-only
campaign projection, and note edits after recovery. Its fixtures are synthetic
and forbid transport. `app/test_records_desk.py` also sends an initial request
and a threaded reply through mocked SMTP without an intervening sync, checks
the latest receipt/status, and confirms duplicate sending remains blocked.
These tests run in `npm.cmd test`; no real email or account data is used.

## Assistant configuration regression

`scripts/configuration.test.mjs` is part of `npm.cmd test` and the Windows CI
suite. It covers the configuration a new user actually generates, not just
tools advertised directly by the servers:

- Parses generated TOML with Python's standard-library `tomllib`; requires all
  68 records and 8 mail tools exactly once. Negative fixtures detect missing,
  duplicate, stale or disabled tools and a disabled server.
- Checks absolute local entry points and the existing host permission defaults
  and per-tool overrides without opening or changing any real `.codex` file.
- Runs the actual setup CLI in a disposable fixture. The first run produces a
  complete configuration; repeated runs and an overwrite flag cannot replace it.
- Starts both real STDIO servers from those generated settings in legacy and
  automatic protocol negotiation modes. An isolated synthetic profile exercises
  workspace settings, template import/preview/version/export, campaigns and
  remaining targets, request progress, a private publication preview, a local
  synthetic ZIP and equipment/inbox status. The mailbox remains unconfigured.

To run just this regression:

```powershell
node --test scripts/configuration.test.mjs
```

These tests reproduced the original 0.6.0 omission before the fix: only 20 of
40 records tools were enabled. They now guard future additions to either server.
They do not exercise Codex's UI, project trust, permission prompts or a particular
model's reasoning. No mailbox is enrolled or contacted, no real message is sent,
and no GitHub issue is created. SMTP and publication behavior remain covered by
the separate mocked tests above, not by a live delivery claim.

## County research regression

County contact research adds synthetic source/date/role validation, fresh/stale
coverage, exact county leads, research leases, idempotent batches, interruption,
revision conflicts and atomic result/receipt rollback tests. The actual MCP
handshake exercises a research batch in both supported protocol modes. The
contact browser story uses the real HTTP handler and disposable storage to test
lookup, selected counties, two worker claims, saved evidence, unresolved outcomes,
history, preserved unsaved edits and reload. No live mailbox, real county search,
model invocation or external write occurs. See [contact research](CONTACT-RESEARCH.md).

## County request-status regression

The county projection tests cover canonical/exact-name matching, workflow
isolation, all 3,144 inventory/geometry IDs, uncertain sends, linked response
evidence, closure, mixed requests and read-only operation. The county browser
story exercises the real local HTTP handler and disposable database: 83 Michigan
county shapes/list entries, distinct statuses, keyboard selection, exact case and
reply opening, reviewed-reply refresh, search/filters, state/workflow changes,
unmatched cases, state-response separation and mobile layout. Both are included
in the normal unit/browser commands. No real inbox or county outreach is used.
See [county status](COUNTY-STATUS.md) for interpretation limits.

`app/map-controls.test.mjs` checks extent validation, bounded/aspect-correct zoom
and pan, fit-selection padding and display-preference validation. The county
browser story also uses `app/map-controls.browser.mjs` for both maps: real pointer
drag versus selection, modifier-wheel zoom, keyboard navigation/focus retention,
touch pinch, zoom limits, fit controls, layer/legend persistence, workflow/state
scope, mobile overflow and preservation of unsaved correspondence. The timing
browser story verifies rendered outline visibility without changing saved dates.
These checks use only isolated synthetic profiles and bundled geography.

## MA response-review regression

The MA response-review regression covers strict category/evidence validation,
revision conflicts, workflow separation, preserved submission dates, independent
appeal watches, reassigned/new-message invalidation, atomic saves and read-only
previews. Its browser story uses the actual handler and isolated synthetic store
to save/reload reviews, preserve dirty edits, and stage a threaded follow-up
without saving/sending it. No real inbox, case assessment or appeal is used.
See [MA helper limits](MASSACHUSETTS.md).

## State guides, municipal sources and Settings regression

`app/test_public_sources.py` uses synthetic directory entries and mocked HTTPS.
It covers complete-name validation, multi-purpose emails, missing email gaps,
duplicate/partial/block pages, freshness, pagination, old-import rejection,
source history preservation, request isolation, strict schemas and bounded
fetch behavior. It never contacts an official site during automated tests.

`app/settings.browser.test.mjs` tests keyboard tabs, local source status,
explicit refresh/import, safe diagnostics, no auto-retry, input preservation,
close/reopen behavior and mobile layout. `app/sources.browser.test.mjs` runs the
actual dashboard and HTTP handler over a disposable store: selected-state guides
are automatic/default-collapsed, source links and municipal search render, and
failed refreshes retain the good collection across reloads. All external
requests and mail/publication operations are forbidden in these fixtures.

## Empty-label mail regression

`app/test_mail_privacy.py` models Bridge returning `NO no such message` if UID
SEARCH is attempted on an empty selected folder. It exercises both desk sync
and the lower-level assistant listing, selected incoming/Sent labels, preserved
scope/cursors, subsequent arrivals, pagination and fail-closed identity/metadata
checks. `connector/test_connector.py` independently checks search bounds,
malformed/oversized results, genuine failures and post-SELECT arrivals.

`app/mail-sync.browser.test.mjs` runs the actual dashboard, HTTP handler, service
and disposable storage with synthetic IMAP only. It previews/applies empty
labels, checks the visible zero-result success, imports the first arrival once,
displays a real search failure and recovers without skipping that message.
Personal Inbox/Sent fixtures remain outside the scope. SMTP is forbidden;
the real Bridge, operator account and running dashboard are never used.

## GitHub Actions

[Windows verification](../.github/workflows/ci.yml) runs on pushes to `main` and
pull requests. It uses pinned official actions, Windows, Node 22, Python 3.13,
read-only repository permission and no persisted checkout credentials. It runs
synthetic tests, documentation checks, publication checks and the browser fixture.
It also runs the new setup script's read-only prerequisite check under Windows
PowerShell 5.1. WinGet installation, license/UAC dialogs and Proton sign-in are
not run in CI; the installer unit tests mock system package changes.
No mail credentials, Bridge enrollment, secrets, live browser smoke or artifact
uploads are configured in CI.

## Fresh-checkout release rehearsal

Before release, clone the reviewed local commit into a new disposable directory
outside any live/private folder. Use `--no-local` for a local Git source so the
rehearsal does not depend on object hardlinks. Install from the lockfile and run
the checks above with an isolated test profile. Verify that the public snapshot
still passes after an actual Git checkout; byte-preserved `.gitattributes` matter.
The fresh checkout must not contain `.private`, `.codex/config.toml`, live stores,
or preexisting `node_modules`.

## Optional operator-only live check

`npm.cmd run test:live-readonly` checks the already-running desk. It expects the
original operator's Pennsylvania draft/case, verifies 51 map shapes and the
visible send-status controls, and permits only read-only case/status operations.
It does not sync mail, save forms, send, or photograph
real records. Do not run it in generic CI or treat a missing operator-specific
draft on a new installation as a software failure.

`proton_check_connection` is a separate, authorized live connectivity check.
It verifies pinned IMAP/SMTP authentication but neither reads message bodies nor
sends. Successful authentication does not prove recipient delivery. Always
report the difference between synthetic behavior, live connectivity, Bridge
acceptance, verified public issue creation and production data integration.
