# Generic request templates

Generic templates are private, encrypted local records. They are reusable draft
definitions, not email permissions, filing destinations, legal advice, eligibility
determinations, or fee authority. Creating, previewing, importing, exporting, or
archiving a template does not send email or contact an agency.

## Definition format

Definitions use `schema_version: 1` and contain a title, fields, subject, body,
and dated official sources. Each field has a lowercase ID, label, explicit
`required` boolean, and `text` or `multiline` type. A source has `title`, HTTPS
`url`, and `review_date` in `YYYY-MM-DD` form. Imports reject unknown schema
members, unsupported schema versions, unsafe URLs, and invalid dates. They do
not inspect author-written literal text for personal information, so review an
import before saving or sharing it.

The only rendering syntax is `{{field}}` and a non-nested conditional block,
`{{#if field}}...{{/if}}`. It is not an expression language: no evaluation,
includes, lookup, scripts, or unrecognized placeholders are allowed. Missing
required values and unknown values are errors.

The explicit built-ins are `organization`, `signature`, `requester_email`,
`agency`, `jurisdiction`, `state`, `date_start`, and `date_end`. Personal
requester name, address, or phone data is private workspace data. It is injected
only when the template has a required field with the exact corresponding ID; it
is never added by default.

Saving a changed definition creates a hashed, immutable version snapshot;
re-saving an unchanged definition keeps its current version. Archive by saving
the definition with `archived: true`; prior versions remain in history and
already-created cases retain their saved snapshot. New generic requests use the
active template's latest version; this release does not offer choosing an older
version for a new request. To duplicate a template, save the desired definition
without a template ID. Export returns only the current definition and never
workspace data, profile values, or values entered for a particular request. A
definition can still contain author-written literal text, so review an export
before treating it as safe to share.

## Minimal importable example

Save this as a UTF-8 `.json` file and use **Import definition**. It is a generic
draft example, not a legal form. Replace the topic and verify the actual agency,
submission procedure and applicable rules before sending. Empty `sources` is
allowed; add dated official-source entries after researching your jurisdiction.

```json
{
  "schema_version": 1,
  "title": "Existing records request",
  "category": "General records",
  "fields": [
    {"id": "topic", "label": "Precisely describe the existing records", "required": true, "type": "multiline"}
  ],
  "subject": "Public records request for {{jurisdiction}}",
  "body": "To {{agency}}:\n\nPlease provide electronic copies of these existing records:\n{{topic}}\n\n{{#if date_start}}Start date: {{date_start}}.{{/if}} {{#if date_end}}End date: {{date_end}}.{{/if}}\n\nPlease provide redacted copies where appropriate. Please notify me of proposed charges before proceeding; no fees are authorized by this request.\n\n{{signature}}",
  "sources": []
}
```

## Review before use

Treat cited URLs as routing/research evidence that needs review on the recorded
date. A template cannot make a recipient current or verified. Review exact
recipient, routing, request text, any personal details, eligibility and fees for
each case before an outside action.
