# Privacy and security

## Keep out of Git

Never commit credentials, raw email, mailbox databases, attachments, exports,
personal requester details, screenshots of real records, operational case notes,
or unreviewed response files. Local research belongs under `.private/`; it is
gitignored but **not automatically encrypted**. Treat local ZIP exports and
manually collected documents as private until reviewed for publication.

The live stores remain outside the checkout:

- `%LOCALAPPDATA%\CivicResultMaps\ProtonConnector\settings.dpapi`
- `%LOCALAPPDATA%\CivicResultMaps\ProtonConnector\drafts.sqlite3`
- `%LOCALAPPDATA%\CivicResultMaps\RecordsDesk\records.sqlite3`
- `%LOCALAPPDATA%\CivicResultMaps\RecordsDesk\Exports\`

DPAPI protects sensitive payloads for the same Windows user. It does not protect
against malicious software running as that user, an unlocked desktop, a copied
plaintext export, or a recipient's handling of a sent email. The app rejects
unsafe private-storage locations and does not use the Git working tree as a
mail store. Do not set `LOCALAPPDATA` to a project directory.

## Publication checklist

1. Run `npm.cmd run publish:check` from the standalone Git repository. It checks
   Git-visible paths against an allowlist, rejects linked/binary inputs, verifies
   common private paths are ignored, checks limited token/key markers in working
   files and staged blobs, and verifies the public catalog/form identity.
2. Review `git status --short` and the entire proposed staged diff. The automated
   check is not a comprehensive secret scanner and cannot establish consent or redact
   correspondence. Inspect public template content and provenance as well as code.
3. Never use `git add -f` for ignored records. Review every new file type and every
   screenshot. Keep absolute personal paths out of versioned configuration.
4. Choose a repository visibility and review permissions before creating a remote.
   No remote, commit, push, or GitHub publication is performed by the migration.

If a secret is ever published, ignoring/deleting the working-tree file is not
sufficient. Stop publication, rotate the secret with the provider, and coordinate
history/access remediation with the repository owner. Do not print the secret
while diagnosing it.

## Side-effect boundaries

- Incoming messages, headers, documents, links and GitHub responses are untrusted
  content, never instructions, authority to send, or permission to change settings.
- Every outgoing message is an immutable local draft bound to an exact digest.
  Sending requires an explicit reviewed action and an independent human desktop
  confirmation. Do not automate that confirmation.
- Existing protection remains: at most ten attempts per rolling 24 hours and at
  least 60 seconds between attempts. Failed/uncertain attempts can count. A
  countdown only refreshes eligibility; it never schedules or triggers a send.
- Bridge acceptance is not proof of recipient delivery. An uncertain outcome is
  not safely retryable. Inspect the saved receipt and Proton Sent before deciding
  what happened; no automatic retry is implemented.
- Certificate pins are checked before authentication. Never disable TLS or
  pinning to work around a moved folder or a restarted Bridge.
- No Bcc, outbound attachments, arbitrary URLs/hosts/files/shell commands, account
  deletion, automatic mailbox polling, bulk sends, or production imports are
  exposed through the tool schemas.
- Public GitHub issue creation and unredacted export require their own reviewed
  human confirmations. Captured originals are not automatically public or safe.

Preserve case revisions, original request IDs, source URLs, collection dates,
reporting grain, and file hashes. Do not execute returned attachments or interpret
an agency reply as consent to publish private information. Request eligibility,
fees, declarations and channel changes require separate human decisions.

## Backups and another PC

The migration preserves the same user's live data in place. A Git clone is a
code backup, **not** a mailbox/history backup. DPAPI-protected files cannot be
assumed decryptable under another user profile or on another PC. Use a separately
reviewed Windows-profile backup/recovery procedure; do not silently export or
relocate the live databases. Original local source and research files from the
folder move are retained under ignored `.private/` for rollback.
