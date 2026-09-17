# Optional publication and local export

CivicRelay works without GitHub. A workspace, custom templates, campaigns,
correspondence, captured files and local exports do not require a repository,
GitHub login, or the CivicResultMaps source checkout.

## Local-only records package

Use **Export private case package** or `desk_export_case` with a case ID and
optional captured artifact IDs. This exports the saved request and saved
correspondence, a provenance manifest, and the selected original bytes. It does
not retrieve unread bodies or new attachments, upload anything, or create a
public issue. A request with no attachments can still be exported.

The ZIP is written under the selected private store's `RecordsDesk/Exports/`
directory, never to a caller-supplied path. It is **plaintext and unredacted**.
Inspect files before sharing and remove unnecessary personal details. Keep
exports out of Git. The originals remain encrypted locally. A package supports
records handoff, not automatic restoration of credentials or send history.

Limits: 30 selected files, 50 MiB of original bytes, 500 saved messages, and
65 MiB for the resulting package. Excesses fail without silently truncating.
ZIP entry names are sanitized and each selected file is rechecked against its
retained SHA-256 and case assignment.

## Configure a GitHub destination

Publication is a separate explicit action. Use **Publication destinations** or
`desk_save_destination` to configure:

- A display name and exact `owner/repository` on `github.com`.
- An optional issue-form filename, such as `records.yml`.
- Labels already appropriate for that repository.
- Field IDs, headings, input/textarea/dropdown types, required flags and options
  matching the intended form. The setting stores a local mapping; it does not
  fetch or verify the remote form automatically.
- Whether that destination is enabled.

This release supports GitHub.com, not an arbitrary API hostname or Enterprise
server. GitHub CLI authentication is used only when publishing or verifying an
issue. Never put a token into destination fields. Template imports cannot create
or select a publication destination.

Choose the destination explicitly when preparing a public preview using
`desk_prepare_publication`. Supply only a reviewed/redacted summary. The
repository, form mapping, labels and destination revision become part of the
immutable preview digest. Changing or disabling the destination blocks an old
prepared preview; prepare a new one after reviewing the new target. Read the
exact target and content in the preview before `desk_publish_intake`.

Selected artifacts contribute filenames/hashes to the public manifest, not
uploaded files. To publish a preview that lists artifacts, include a stable,
reviewed public file link in a destination field with ID `response_url`; raw
private attachments are never uploaded automatically. Signed/private URLs are
rejected by a limited tripwire, not guaranteed redaction.

GitHub API issue creation uses the reviewed headings and content. It does not
execute the repository's issue form or automatically attest to form checkboxes.
If the target needs attestations, eligibility or other required procedures not
represented by this mapping, resolve them before publication. No template or
incoming message supplies that authority.

## Receipts and uncertainty

The returned issue URL must match the exact reviewed repository. An unexpected
response or lost outcome becomes **uncertain**, never a safe automatic retry.
Verify/link the matching existing issue with `desk_link_issue`. Reconciliation
uses the saved target snapshot, so a historical receipt can still be resolved
after current destination settings change. Another unresolved attempt on the
same case blocks creating a replacement publication.

For generic requests, publication status is independent of correspondence and
records coverage. Publishing a handoff does not mean an agency has responded,
that the records request is complete, or that data has been imported.

## Existing CivicResultMaps intake

The optional CivicResultMaps starter pack preserves its reviewed
`records-response.yml` snapshot and original request IDs. Its established
`desk_prepare_intake`, `desk_publish_intake`, `desk_link_issue` and
`desk_export_package` tools remain compatible. `desk_export_package` exports a
legacy prepared issue's selected files; `desk_export_case` requires no issue.
The CivicRelay software repository is not automatically a records destination.
