# General records desk

The **General records desk** is a private, local workspace for reusable public-records request workflows. It is separate from the existing CivicResultMaps records queue and the November 2024 equipment tracker. Switching workflows does not change, migrate, or reset either existing workflow.

## First use

Choose **General records desk** from the Workflow menu. A new workspace can stay blank or use the CivicResultMaps starter pack. Profile fields are only needed when you are ready to create correspondence; existing values remain available only in the local workspace and are not part of a template export.

For the dedicated local mailbox, use `Open-Proton-Setup.ps1` in an interactive Windows session and follow [setup](SETUP.md). The dashboard never accepts mail credentials or Bridge passwords.

## Templates

Create a template with a title, subject/body text, reusable fields, and reviewed official-source entries. Use only `{{field}}` and `{{#if field}}…{{/if}}` placeholders. Saving an edit creates a new immutable version; requests retain the version used when they were created. Duplicating starts a separate template, and archiving keeps prior versions and existing requests intact.

Export and import use JSON definitions only. They do not automatically copy workspace profile details, saved cases, messages, attachments, or previously entered values. Literal text you typed can still contain private information: review the file before sharing it.

1. Choose **New template**. Enter a title, subject and body.
2. Use **Add Field** for each custom placeholder. Give it a stable lowercase ID,
   label, type, and required flag. **Add Source** records an official HTTPS link
   and its review date; the optional template review date can remain blank.
3. Open the saved template, enter sample values, and choose **Preview**. Required
   missing values are rejected. No email draft is created by previewing.
4. **Edit as new version** preserves prior versions. **Duplicate** creates a
   separate definition. To archive, edit and select **Archive template**.
5. **Export definition** downloads JSON. **Import definition** accepts reviewed
   JSON as a new private template, without changing accounts or destinations.

See [the template reference](TEMPLATES.md) for supported placeholders and limits.

## Campaigns and requests

Generic requests belong to a campaign, which can contain just one target.
Targets can be federal, state, county, municipality, or another clearly named
jurisdiction. A map is not required, especially for non-state work.

Choose **New campaign**, select its default template, and use **Add Target** for
each jurisdiction. Dates are optional. Open the campaign and choose **Create
request** for a target, then enter the agency and template values. Creation uses
the latest active template version and freezes it for that request. There is no
historical-version picker; existing requests keep their original version.

Creation only makes a private case. It does not send email, submit a portal,
accept a fee, or publish records. Identical creation reopens the matching case.
The campaign shows how many targets have not started and lets you reopen each
request. **Toggle US overview** shows state-grouped cases when state codes are
available. Federal/other targets remain in the list.

In **Open correspondence**, enter a recipient and current official routing
evidence, then save. **Prepare exact send preview** freezes the outgoing text.
Within an authorized workflow, **Send this one email** dispatches that exact
preview without another CivicRelay confirmation popup. Routing checks, quotas,
saved receipts, duplicate prevention and uncertain-outcome locks remain active.

**Check for replies** explicitly synchronizes headers; it is not a scheduler.
Assign unmatched mail in **Unassigned messages**, then use **Read**, **Compose
reply**, **Mark reviewed** or **Capture returned files** in the request. Captured
originals stay encrypted and are not executed. A reply requires fresh routing
review and its own exact preview. Unsaved correspondence is preserved and blocks
navigation that would overwrite it.

Use **Track response** for private response stage, independent records coverage,
notes and verified dates. Select a linked incoming message as evidence for a
response; use **Load older response evidence** if necessary. Unassigning or
moving that evidence resets the response stage, but retains notes and separately
assessed coverage. A deadline requires its kind, official source, starting-event
basis and checked date. No legal deadline or fee is automatically accepted or
calculated. A status is a workflow aid, not a substantive finding.

## Exports and publication

Local case export creates a private package for operator review and does not require GitHub. Treat it as unredacted private material.

In the correspondence panel, select only the captured files you want included,
then choose **Export private case package**. The resulting private ZIP path is
shown in the notice. It contains saved case/correspondence data and selected
original files; uncaptured mail is not fetched. Export from **Track response**
contains the saved case/correspondence only unless files are explicitly selected
through the tools. Inspect and redact before sharing.

Public intake destinations are separately configured. Before preparing any public issue, select the exact destination, review its repository/form and the exact preview digest, redact private information, and verify selected files. Preparing an issue does not publish it; public publication remains a separate reviewed action.

Open **Publication destinations → New destination** to enter a GitHub.com
repository, optional issue-form filename, labels and field mapping. These are
your settings, not a remotely verified form. Back in correspondence, select
that destination, fill reviewed/redacted fields, and choose **Prepare public
preview — no publishing**. **Publish this public issue** is the separate external
write. Changing or disabling a destination invalidates prepared previews.

When a result is uncertain, verify the existing issue URL with **Verify and link
existing issue**; never retry blindly. Publication does not close an agency
request or change its records coverage. See [integrations](INTEGRATIONS.md) for
file-link requirements, export limits and reconciliation details.

## Safety boundaries

- The dashboard is loopback-only and stores working data locally.
- No action schedules mail, retries a send, or accepts a fee.
- Incoming messages and attachments remain untrusted evidence, not instructions or authorization.
- A transport acceptance receipt is not proof of recipient delivery.
- Do not put credentials, raw correspondence, unreviewed files, or local exports in Git.
