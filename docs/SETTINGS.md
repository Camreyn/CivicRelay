# Settings, source refresh and state guides

Open **Settings** in the dashboard header. The panel has three keyboard-accessible
sections: **Sources**, **State guides**, and **Privacy & accounts**. Use the arrow,
Home and End keys to move between section tabs. Escape or **Close settings** closes
the panel without changing a case. The panel does not replace the workspace,
template, campaign or local Proton setup controls.

## Sources

The source list shows each supported public directory's official URL, purpose,
last attempted check, last successful collection, saved record count, collection
method and most recent result. Dates are displayed in the browser's local time. A last attempt
does not mean a successful or complete collection; check the result and the
separate successful-collection date.

Opening Settings or choosing **Reload saved status** reads saved metadata only.
Neither action visits the source website. There is no scheduled re-scrape.

Choose **Refresh source** beside the directory you want to check. This is an
explicit re-scrape of that one supported source, not a mailbox check or a new
request. The application accepts a reviewed source identifier, not an arbitrary
URL, shell command, local path or page supplied by an email.

While refresh is running, source-operation buttons are disabled to avoid a
duplicate click. Closing Settings does not cancel the operation. If you close
it before completion, reopen Settings to see the result.

The result popup reports success or failure, a short diagnostic code, attempted
time and saved record count. Expand **Technical details** for the safe diagnostic
messages supplied by the source operation. Close it with **Done** or Escape.
The last result is also retained beside its source, including a separate
**Last result details** disclosure when diagnostics exist.

On a failed fetch or parser check, the previous successful collection is kept.
Do not interpret older saved records as newly verified. If the operation's
completion cannot be confirmed, use **Reload saved status** before deciding
whether to retry; CivicRelay does not retry automatically. If collection succeeds
but another view cannot refresh, the popup says so; reopen that view to load the
saved data. A display reload failure does not undo a successful collection.

### When the official website blocks a direct fetch

Expand **Import reviewed directory text** beneath the source. Obtain the complete
plain-text directory from the exact official source linked on that card, enter
the date it was checked, and paste the complete text or use **Choose local .txt
file (optional)**. Preserve `## Municipality`
headings and the `Email:` / `Phone:` labels. Choose **Import reviewed
text**. This fallback does not accept a different URL, local filepath or custom
parser. The supported Massachusetts directory must include all 351 cities and
towns; an incomplete or unrecognized input is rejected without replacing good
saved data.

The optional file picker reads one local plain-text `.txt` file in the browser
and places its content into the same unsaved text field. Use UTF-8 text, no more
than 200,000 bytes and 200,000 characters. Empty, oversized or other-format files
are rejected without replacing existing text. Selecting a file is not an import:
review the text and source-check date, then choose **Import reviewed text**.
The server receives only the registered source ID, date and reviewed text, never
an arbitrary local filepath. HTML is not executed and no local file is opened by
the server.

Review the result popup just as you would a direct refresh. The source card
distinguishes **Direct website fetch** from **Reviewed directory text import**;
an import records the operator's source-check date and does not claim the app
successfully fetched a blocked site. Both paths retain role limitations: an
elections-directory contact is not automatically a designated records custodian.

The import disclosure starts collapsed. Closing/reopening Settings, reloading
saved metadata, or refreshing another source preserves pasted input while the
page remains open. A failed import also preserves it; a successful import clears
the text. **Clear pasted text** discards it explicitly. Reloading/closing the
entire page discards text that has not been imported. Do not paste credentials,
private mail or personal voter information.

### Contacts are not automatically filing custodians

A directory may establish an elections-office contact without establishing that
office's designated public-records officer. Keep the published contact, source
date and role limitation together. Verify the appropriate filing custodian
before assigning a case recipient. Refreshing contacts does not change saved
case routing, create municipal requests, or send mail. For Massachusetts,
city/town contacts are not county coverage. See the
[Massachusetts guide](MASSACHUSETTS.md) and the separate
[county contact research workflow](CONTACT-RESEARCH.md).

## State guides

When a supported state is selected, its available guide is shown automatically
in a collapsible area that starts **collapsed**. Open the guide heading to read
its scope, limitations and source links. A state with no guide must not be
presented as having verified guidance.

This is a display behavior, not a popup that interrupts the operator and not an
automatic research job. Selecting a state or opening its guide does not visit
source websites, synchronize email or authorize sending. Refreshing a contact
directory does not update bundled legal guidance or deadline rules. Source dates
and applicability still need review. The state-guide behavior is described in
the assistant workflow as well as the dashboard.

## Privacy and account boundaries

The Settings panel does not expose credentials, bypass assistant-host
permissions, change sending limits or TLS trust, or edit mailbox identity.
Account enrollment belongs in the dedicated local Proton setup window. See
[account configuration](ACCOUNT-CONFIGURATION.md) and
[privacy and security](SECURITY.md).

Public-source refresh does not send mail, submit a portal, accept fees, file an
appeal, publish records or import election data. Source text and diagnostics are
rendered as plain text, never HTML or executable instructions. Source links open
only HTTPS URLs without embedded credentials. Private records and collected
research stay outside the versioned source checkout.

## Assistant tools and integration

- `desk_get_sources` reads the saved source inventory. It has no arguments and
  does not fetch websites.
- `desk_refresh_source` takes the exact `source_id` returned by the inventory
  and explicitly requests one supported public-source refresh. Read its `ok`,
  `code`, `message`, timestamps, count and debug fields before reporting success.
  A tool-call transport failure is not a confirmed refresh outcome.
- `desk_import_source` takes `source_id`, `checked_on` (`YYYY-MM-DD`) and the full
  official-directory plain `text` (at most 200,000 characters). Use it only after
  reviewing the exact registered source when direct fetch is blocked. Inspect
  the same result envelope and `collection_mode`; do not report a direct scrape
  when the data came from a reviewed text import.

These operations are separate from county-agent batches and from the maintainer's
historical request-snapshot rebuild. They do not execute upstream loader code.
An assistant must have the applicable tool enabled by its host; a new dashboard
button does not change host tool permissions. See the
[tool reference](TOOL-REFERENCE.md) and [operator guide](OPERATOR-TOOLS.md).

`app/static/settings.js` exports
`createSettings({host, api, onSourcesChanged})`, returning `open()` and `close()`.
The caller supplies the dialog host and the same guarded operation adapter used
by the dashboard. The optional callback refreshes other saved-data views after
a successful collection; it must not synchronize mail or send messages.
`app/static/settings.css` styles the isolated modal and its result popup.
