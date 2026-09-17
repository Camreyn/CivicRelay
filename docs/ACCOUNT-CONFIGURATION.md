# Account configuration

CivicRelay supports one dedicated Proton Mail Bridge mailbox for each Windows-user installation. It is a local configuration, not a hosted account system and not a multi-account mail client.

Mail enrollment is optional. A fresh user can begin with the blank workspace and
create private templates/campaigns without Bridge, GitHub, or the historical
CivicResultMaps starter pack. The starter pack is optional compatibility content,
not a required account identity.

## Enrolling a fresh installation

Run `Open-Proton-Setup.ps1` in an interactive Windows session. Enter a dedicated
Bridge username, a sender display name, the Bridge-generated password, and the
local IMAP/SMTP ports. Credentials are entered only in that Tkinter window and
saved with Windows DPAPI; they are never accepted through dashboard, MCP,
command-line, or environment arguments.

The setup window requires an isolation attestation: use a dedicated mailbox or
Proton Bridge split-address mode that exposes only the intended address. It
probes and displays the loopback-only STARTTLS certificates before
authentication. Certificate pins are checked before every authentication. Setup
does not read mail or send mail, and sending remains disabled unless the local
user explicitly enables it.

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
