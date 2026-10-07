# Account configuration

CivicRelay supports one Proton Mail Bridge connection for each Windows-user installation, with a reviewed mailbox scope. Use selected custom folders/labels for a personal account, or Inbox/Sent for a genuinely dedicated address. It is a local configuration, not a hosted account system or multi-account client.

Mail enrollment is optional. A fresh user can begin with the blank workspace and
create private templates/campaigns without Bridge, GitHub, or the historical
CivicResultMaps starter pack. The starter pack is optional compatibility content,
not a required account identity.

## Enrolling a fresh installation

Run `Open-Proton-Setup.ps1` in an interactive Windows session. Enter your
Bridge username, a sender display name, the Bridge-generated password, and the
local IMAP/SMTP ports. Credentials are entered only in that Tkinter window and
saved with Windows DPAPI; they are never accepted through dashboard, MCP,
command-line, or environment arguments.

The setup window requires acknowledgment of the mail privacy requirement. It
probes and displays the loopback-only STARTTLS certificates before
authentication. Certificate pins are checked before every authentication. Setup
does not read mail or send mail, and sending remains disabled unless the local
user explicitly enables it. Then open **Settings → Mail privacy** and preview/apply
the allowed folders and history boundary. Remote reads are blocked until then,
including after an upgrade from an older release. The legacy
`project_mailbox_confirmed` credential-setting field remains for compatibility;
it is not permission to read the whole mailbox. See [mail privacy](MAIL-PRIVACY.md).

The display name and a generated profile ID are bound into every new v2 draft digest. A reviewed draft therefore cannot be moved to another sender profile. Existing v1 CivicResultMaps settings and drafts retain their exact legacy digest and wire `From` format; they continue to require their original legacy sender settings.

## Storage selection and migration safety

For a Windows user with existing CivicResultMaps private data, CivicRelay
continues to use `%LOCALAPPDATA%\CivicResultMaps\ProtonConnector` and its paired
`%LOCALAPPDATA%\CivicResultMaps\RecordsDesk` location. Fresh users use
`%LOCALAPPDATA%\CivicRelay\ProtonConnector` and
`%LOCALAPPDATA%\CivicRelay\RecordsDesk`.

The connector selects a namespace using file existence only; it does not decrypt settings to make that choice. If both legacy and CivicRelay namespaces contain mailbox or records data, it fails closed instead of guessing, copying, merging, resetting a quota, or creating a second account. Resolve that condition locally with a reviewed recovery process.

After settings or draft history exists, setup blocks enrollment of a different
email, display name, or v2 profile ID. Re-entering a Bridge password for the same
v2 identity retains its profile ID. Legacy v1 identities, digest bytes, receipts,
and quota remain in place rather than being automatically converted. Do not
delete, copy, or hand-edit private stores to work around the guard.

## Dashboard integration contract

`connector.account_summary(store)` is local-only and credential-free. It returns:

```json
{
  "configured": true,
  "email": "dedicated@example.org",
  "display_name": "Civic Relay",
  "profile_id": "UUID or null for v1",
  "legacy_storage": false,
  "private_storage": "local path",
  "local_only": true
}
```

`proton_status` includes the same sanitized fields and still reports send enablement and the existing quota window only after validated local settings are loaded. Neither interface includes a password, certificate pin, or decrypted credential material. `secure_store.records_root()` exposes the matching records-store root for dashboard/storage integration; it is not an account-selection argument.

No configuration action authorizes delivery, mailbox synchronization, fees, publication, automatic retry, or a different routing channel. The existing loopback-only transport, environment allowlist, TLS pins, send enablement, quota, and uncertain-outcome locks remain in force.

The current source adds a separate **Settings → Sending limits** policy editor.
It requires enrollment but never accepts credentials or changes send enablement.
Saved policy and attempt history survive a same-account credential refresh;
do not re-enroll or delete private files to change the cap. See
[sending limits](SENDING-LIMITS.md).
