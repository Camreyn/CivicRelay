# CivicRelay 0.6 — general-purpose local records workflows

## Scope

Windows, Proton Mail Bridge, one enrolled mailbox per Windows user. This release
generalizes a public-records workflow manager; it is not a general mail client,
shared cloud service, scheduler, or concurrent multi-account installation.

New: private workspace setup, reusable versioned templates, safe placeholders
and conditionals, definition import/export, generic federal/state/local/other
campaigns and target tracking, explicit response evidence and verified deadline
notes, local case exports without GitHub, and optional configured GitHub issue
destinations. Native and page tools use the same backend validation.

Preserved: original public catalog/form bytes, existing request IDs and stored
content, v1 settings and immutable draft digests, send receipts/quota ledger,
thread matching, attachment provenance, TLS pins, and uncertain-outcome locks.
New v2 draft identity also binds the enrolled display name and profile ID.

## Upgrade and safe activation

1. Preserve uncommitted source work and use a reviewed source update. Keep
   `.private/` and `.codex/` ignored and unchanged.
2. Stop only this checkout's dashboard while no mail/publication operation is
   active, update source, then restart it and reload the page. Reconnect the two
   native tool servers to load their expanded schemas.
3. Do not move private stores, re-enroll the current mailbox, or resend anything
   as an upgrade check. Existing installs retain the legacy storage namespace;
   fresh installs use CivicRelay's namespace. Ambiguous dual stores fail closed.
4. Verify status and the expected workspace identity. Tool/health compatibility
   names remain unchanged even though the release version is 0.6.0.

The update does not edit host permissions or start recurring work. No message,
public issue, fee acceptance, live mailbox check or production import is a
release test. See [testing](TESTING.md), [migration](MIGRATION.md),
[accounts](ACCOUNT-CONFIGURATION.md), and [security](SECURITY.md).

## Acceptance checklist

- Install dependencies from the lockfile in a clean, source-only directory.
- Run `npm.cmd test`, `npm.cmd run test:browser`, and `npm.cmd run publish:check`.
- Confirm blank onboarding works without enrolled mail, GitHub or a parent repo.
- Rehearse custom template → federal/local campaign → exact draft → synthetic
  send/response → independent progress → local export with isolated test data.
- Confirm legacy map/catalog/equipment/send flows still pass their fixtures.
- Inspect complete source diff and public-template content before publication.

Automated tests and their limits are documented separately; passing them is not
proof of real delivery or an independent security audit. Source publication
requires separate authorization, including any previously uncommitted work.

## Verified release evidence — 2026-09-17

- Clean locked dependency installation and empty-profile rehearsal completed.
- `npm.cmd test`: 178 tests passed (45 Node, 83 application Python, 50 connector
  Python), plus generated-schema and documentation checks.
- `npm.cmd run test:browser`: all three suites passed with synthetic stores and
  fake transports, no external browser requests and no console errors.
- `npm.cmd run publish:check` and `git diff --check`: passed. The public catalog,
  form snapshot and map geometry remain unchanged. Generated browser images and
  private operational files stay ignored.
- Independent backend review findings were fixed and covered by regressions:
  blank optional dates, fresh-workspace isolation, receipt-derived status,
  reassigned response evidence, effective request deduplication and frozen scope.

See [fresh-install evidence](FRESH-INSTALL-VERIFICATION.md) and the
[general user guide](GENERAL-USER-GUIDE.md). Testing did not re-enroll or migrate
the existing mailbox, send real messages, accept fees or publish source/records.
