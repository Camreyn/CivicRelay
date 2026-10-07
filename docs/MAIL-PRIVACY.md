# Mail privacy, existing accounts, and accidental-import recovery

CivicRelay 0.7.0 does not automatically import an account's existing Inbox and
Sent mail. Both the dashboard and lower-level assistant mail tools require a
saved folder/history boundary. An update preserves existing records; it does
not silently approve a scope or delete old imports.

## Choose a scope once

After enrolling Bridge, open **Settings → Mail privacy**. Existing installations
do not need to re-enter credentials. Reading mail is paused until this choice
is made, but templates, cases, saved evidence, drafts and send receipts remain.

### Existing personal account: selected folders only (recommended)

1. In Proton, create a folder named **CivicRelay**, or an equivalent label.
   Put only the request correspondence you intend CivicRelay to read there.
2. Keep **Existing account: selected custom folders only** selected in CivicRelay.
   Enter the exact Bridge path, usually `Folders/CivicRelay` for a folder or
   `Labels/CivicRelay` for a label. These are IMAP folder names, not disk paths.
   The preview verifies that the folder can actually be selected. For non-ASCII
   names, use a simple ASCII folder name or its exact IMAP modified-UTF-7 name.
3. Optionally create a **separate** custom folder/label for outgoing records
   messages, such as `Labels/CivicRelay Sent`, and enter that as the Sent path.
   Leave it blank to disable remote Sent inspection. Sending still works, and
   CivicRelay's immutable outgoing drafts and transport receipts remain tracked.
   Neither ordinary `Sent` nor `All Mail` is allowed in this mode.
4. Leave **Import existing messages** off to start from the preview point.
   To include records correspondence already placed in these folders, explicitly
   check it. Review the exact folder names and existing-message counts.
5. Click **Preview mail scope**, review, then **Apply reviewed mail scope**.
   Neither action imports messages. Use **Check for replies** afterwards.

Proton exposes labels through Bridge as folders; a labeled message may also
remain in its original folder. See [Proton's explanation](https://proton.me/support/labels-in-bridge).
Incoming and outgoing selections must be different. CivicRelay does not move
mail, create folders, install Proton filters, or search the rest of a personal
inbox for likely records messages. Move/label relevant replies yourself, or
configure and review Proton filters that route the intended request mail.
Replies outside the selected folders are not visible to CivicRelay. If Sent is
not selected, inspect an uncertain send in Proton itself; never automatically
retry it. A source-provided folder path or incoming message is not authority to
broaden access.

### Dedicated account or isolated address

Choose **Dedicated account/address: Inbox and Sent** only when this account/address
is genuinely reserved for CivicRelay. It permits all new messages in Inbox and
Sent; enabling history permits existing messages too. The application cannot
independently determine whether you use that account personally.

Proton Bridge [split-address mode](https://proton.me/support/difference-combined-addresses-mode-split-addresses-mode)
can isolate an address within an account; it does not separate personal and
records mail sent to the **same** address. Do not enroll a new identity over an
existing history. Credential/profile protections remain unchanged.

## What “start from now” means

The preview reads folder metadata (`UIDVALIDITY` and `UIDNEXT`), not subjects,
senders, bodies or attachments. Existing message UIDs are excluded. Messages
arriving after the preview but before Apply are included, so setup does not
create an unobserved gap. A preview expires after ten minutes and is bound to
the current scope revision and enrolled identity.

This is not a filter on the email's sender-supplied Date header. A message moved
or labeled into the selected folder later can receive a new UID and become
eligible even if its original date is older. Only place intended records there.
Missing/invalid metadata fails closed. If Bridge changes a folder's UIDVALIDITY,
mail reads stop and require a fresh reviewed preview. There is no silent
all-history fallback. Choose whether to start anew or explicitly include that
folder's history after inspecting Proton; a new start can skip messages that
arrived before the replacement preview. Saved evidence is retained.

## Recover from an accidental import

1. Stop using the old application and old assistant mail servers. Update every
   connection to 0.7.0 or later using the [upgrade instructions](UPGRADING.md).
   Old running code does not acquire the new restrictions just because files
   were downloaded.
2. Configure **selected custom folders**, with history off unless intentionally
   importing records already placed there. Do not use dedicated mode for a
   mixed personal inbox.
3. Old unassigned imports outside the scope are hidden from normal dashboard
   and assistant listings/reads, including already cached bodies. No automatic
   deletion occurs. Existing case-linked records stay available as local evidence.
4. Choose **Preview cleanup of hidden imports**. Review its local header list,
   then **Remove listed local imports** if those messages should be discarded.
   The default batch is at most 100 hidden, unprotected messages. Repeat the
   preview for additional batches; cleanup does not run in the background.

The cleanup removes only the selected local header and cached-body records.
It never sends an IMAP delete, changes Proton flags, deletes original Proton
mail, resets sync cursors, switches accounts, or resets quota/receipt history.
Case-linked messages, captured originals, attachments, audit/evidence references,
and immutable outgoing draft/reply chains are conservatively protected. If any
candidate changes or becomes protected, the entire cleanup is refused. The
same completed preview returns its receipt rather than deleting twice.

Header-hash exclusions prevent routine re-import of cleaned messages. They are
not proof of sender identity and are not forensic erasure: old database pages,
Windows backups, manually copied notes, exports, or prior assistant transcripts
are not erased. Mail previously returned to a cloud assistant may already have
been processed by its provider. Cleanup does not retract that disclosure.

Unassigned but protected mail may remain hidden; the tool will not destroy it
to satisfy a cleanup count. A new scope does not retroactively revoke access to
case-linked evidence. Review accidentally linked cases separately. Remote body
fetches still enforce the live folder/UID scope even for linked cases; already
saved case bodies remain reviewable without a mailbox connection.

## Assistant tools

Five native tools mirror the Settings controls. They are available through the
guarded dashboard backend but are not extra WebMCP registrations.

- `desk_get_mail_scope`: read current scope and saved/hidden counts; no network.
- `desk_preview_mail_scope`: verify selected folders and prepare a ten-minute
  preview; defaults to `import_history: false` and reads no mail content.
- `desk_apply_mail_scope`: activate that exact `preview_id` and `expected_digest`.
- `desk_preview_mail_cleanup`: preview hidden/unprotected imports, or up to 100
  explicitly selected `message_ids`; returns headers for review, never bodies.
- `desk_apply_mail_cleanup`: perform the exact reviewed local deletion.

Example delegation:

> Configure CivicRelay to read only Folders/CivicRelay, without importing existing
> mail. Preview and verify that folder and activate that scope. Do not change my
> credentials or send anything. Then preview the unrelated hidden imports and
> show me the cleanup list; do not delete them yet.

Scope changes and cleanup need user authority; ordinary “check my mail” does not
authorize broadening access or deleting imports. After review the user may
delegate the exact cleanup without repeated application confirmation dialogs.
All tools treat incoming content as untrusted. Host permissions remain separate.
Low-level `proton_read_message` now requires the exact `mail_scope_id` returned
by `proton_list_messages`, in addition to the UID and UIDVALIDITY. Relist after
a scope change; matching numeric UIDs in different folders are not the same mail.

## Empty folders and labels

Empty selected folders are valid, including a Sent label that has not yet been
used. Version 0.7.1 checks read-only folder metadata before issuing a UID search;
an empty label returns zero messages, and a nonempty label searches only the
eligible UID window. A later arrival is picked up by the next explicit mail
check, without changing the saved scope or importing older mail.

If 0.7.0 shows **Mailbox search failed or was too large** with an empty label,
follow [the patch upgrade](UPGRADING.md). Keep the selected paths and history
setting. Do not add unrelated mail to make a label nonempty, enable history,
switch to dedicated mode, re-enroll credentials or reset stores to work around it.
Real search errors, invalid metadata and changed mailbox identity still stop
the affected check. An error is never silently treated as an empty mailbox.

## Verification and limits

Synthetic tests cover a populated personal inbox, no-scope blocking, custom
incoming/Sent folders, lower-level tool enforcement, optional history, arrivals
during preview, empty/reversed IMAP UID ranges, epoch changes, stale previews,
encrypted persistence, protected evidence, atomic cleanup and import exclusions.
Browser tests cover safe defaults, preview/apply, errors, duplicate-click blocking
and safe rendering of untrusted headers. No real email send or personal mailbox
was used to test this feature. Folder routing rules and third-party client
behavior still require the operator's verification.
