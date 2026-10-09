# CivicRelay 0.8.0 — Your requester defaults and configurable sending limits

## Requester defaults

Use **Settings → Requester defaults** to save your requester name, postal
address, phone, contact email, organization, title/role and signature privately.
Each field has a separate default-use switch and a reusable template variable:
`{{requester_name}}`, `{{requester_address}}`, `{{requester_phone}}`,
`{{requester_email}}`, `{{organization}}`, `{{requester_title}}` and `{{signature}}`.

Enabled defaults appear only where referenced. Disabled or blank defaults do
not substitute a bundled project identity. Preview and new-request forms have
**Use one-off …** controls, including explicit blank overrides. Contact email
does not change the enrolled sending account. The project-specific staff
sign-off and operator identity guidance have been removed from new requests.

Existing template versions, requests and immutable drafts are not rewritten.
Literal names in your own template remain literal; replace them with variables
when you want configurable values. Older profiles retain their saved values and
existing default use without a write-on-read migration. Review the switches
after updating, especially before including personal contact details. A switch
is a default-use preference, not a redaction filter for literal signature text.
See [requester defaults](SETTINGS.md#requester-defaults) and [templates](TEMPLATES.md).

## Sending limits

The sending-limit controls already merged after 0.7.1 are included in this
release. **Settings → Sending limits** can explicitly change the local rolling
24-hour attempt cap and minimum spacing. Defaults remain **10 attempts** and
**60 seconds**; previous attempts, drafts and receipts are preserved. Proton's
independent restrictions still apply. Changing these settings does not enable
sending, retry a message, or start a queue. See [sending limits](SENDING-LIMITS.md).

## Update

Follow the [Git/ZIP upgrade guide](UPGRADING.md). Finish any active operation,
stop old dashboard/tool processes, update the complete source, run **Install
CivicRelay.cmd**, and restart the dashboard and both assistant connections.
Confirm version **0.8.0** in `/health`, `desk_status` or `proton_status`.

Keep your working mailbox scope and credentials. No re-enrollment, account
reset, history rescan or new dependency is needed. Existing assistant allowlists
may need `desk_get_send_limits` and `desk_save_send_limits`; requester defaults
extend the existing workspace tools rather than adding tools. Preserve existing
host permission choices. Updating source does not update an installed app
automatically.

## Verification scope

The synthetic unit and browser suites exercise defaults/flags, strict revisions,
old-profile compatibility, sender separation, one-off overrides, frozen history,
private exports, sending limits and the actual local UI/API/store flow. Release
checks also inspect Git-visible/staged source and byte-preserved historical
assets. Tests use fictional accounts and disposable stores: no real message,
account reset, records publication or live-mail access is a test step.
See [testing details and limits](TESTING.md).
