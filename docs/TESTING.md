# Testing and verification limits

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

| Boundary | Evidence supplied by the suite | Limit |
| --- | --- | --- |
| UI → local API | Real Chromium with the actual static app and synthetic loopback responses; map, navigation, form preservation, countdown and errors | No real account or agency action |
| MCP → worker | Actual STDIO handshakes, public schemas, strict arguments and isolated unconfigured profiles | Tests do not enroll a real mailbox |
| Workflow → storage | Synthetic case/mail/artifact records, revision/lease behavior and restart tests | Does not audit the live operator's database |
| Encryption/storage guards | Windows DPAPI round trips using synthetic values, tamper/link/repository-path rejection | Not a third-party cryptographic/security audit |
| Send → receipt | Direct send without Tkinter/confirmation arguments, mocked SMTP, exact digest, quota, concurrency, uncertain outcomes and duplicate prevention | No real message sent; delivery is not tested |
| Intake → public issue/export | Direct actions without approval modules, mocked GitHub, exact form/snapshot identity, private-link guards and uncertain-publication handling; synthetic ZIP byte checks | No public issue or real-record export created by tests |
| Docs → implementation | Local links/npm commands checked; 48-tool reference compared to source schemas | External pages and prose still need human review |
| Fresh workspace → templates → campaign | Synthetic strict-schema, safe-rendering, immutable-version, private-field, idempotency, target retention and linked-evidence tests | Literal template text still needs privacy and procedural review |
| Configured destination → exact preview → receipt | Synthetic destination-revision invalidation, exact repository URL verification, unresolved-attempt locks and local case ZIP checks | Remote form schema/labels are not fetched or validated automatically |
| Account profile → storage/draft | Synthetic v1 compatibility, fresh v2 identities, display-name/header and profile digest binding, ambiguous-store refusal | No new real account is enrolled or used by tests |
| Equipment campaign UI → HTTP → database | Actual handler and isolated synthetic store; 51-state tracker, remaining-state filter, saved notes survive reload, unverified dates rejected | No actual agency deadline, fee acceptance or email delivery tested |
| Source → publication | Git-visible path allowlist, regular-file checks, limited token/key markers, staged blobs and catalog/form integrity | Not comprehensive redaction, secret detection or permission review |

The browser fixture binds to an ephemeral port, denies non-fixture network
requests, closes its browser/server, and produces only ignored synthetic
screenshots. A fixture's “send call” means a call to the fake local handler,
not an email. Tests use temporary profiles for worker mail operations; do not
replace those fixtures with the operator's real account.

## GitHub Actions

[Windows verification](../.github/workflows/ci.yml) runs on pushes to `main` and
pull requests. It uses pinned official actions, Windows, Node 22, Python 3.13,
read-only repository permission and no persisted checkout credentials. It runs
synthetic tests, documentation checks, publication checks and the browser fixture.
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
