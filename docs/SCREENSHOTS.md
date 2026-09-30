# README screenshots

The README images are direct browser captures of the actual CivicRelay UI,
not mockups and not redacted captures of an operator's mailbox. They were
captured on September 29, 2026, from the disposable
[screenshot fixture](../app/screenshots_fixture.py). The requests, email headers,
acceptance receipts, dates and statuses are **invented examples**. Geography and
bundled guide text are public application assets, not evidence of outreach.

| Image | What it shows |
| --- | --- |
| [National overview](images/demo-national-overview.jpg) | Equipment workflow, state status colors, map controls and example scope notes |
| [County progress](images/demo-county-progress.jpg) | Michigan county map/list with six fictional request statuses and unrequested counties |
| [Request template](images/demo-request-template.jpg) | Reusable park-maintenance wording, placeholders and version/export controls |

## Run the isolated demo

After installing the development requirements, run this from the project folder
with your configured Python executable (the command below assumes `python` is
on PATH):

```powershell
python -E -s -S app/screenshots_fixture.py
```

Open the **random loopback URL printed by this command**, not the live dashboard
on port 8766. The real application files are served unchanged. Storage is created
in a disposable system temporary directory, using the same synthetic protector
as the tests. It is not a production encrypted store. No account is enrolled and
no existing Windows-user store is opened. Only a small read/preview allowlist is
available; saves, mailbox checks, sends, exports, publication and source refresh
are disabled. Outbound sockets and mail/GitHub transport are also blocked within
the demo process. Do not enter real information into it.

1. The equipment workflow opens with fictional state statuses. Scroll to the
   national overview. The published capture has timing outlines turned off using
   **Layers**; status colors and place labels remain on.
2. Select **Michigan**, then **View county requests**. Capture the county map,
   its status list and legend. The six counties are test scenarios, not real cases.
3. Change **Workflow** to **General records desk**, then open
   **Park maintenance contracts**. Capture the template definition and controls.
4. Capture only the app tab, excluding browser chrome, other tabs, desktop
   notifications, downloads and filesystem paths. The current images use the
   browser's native JPEG output and default 1265 × 712 viewport; do not stretch
   images or edit real records to create an example. A different window size may
   need different scrolling. No visual changes to the production UI are needed.
5. Visually inspect every saved image, including all visible text. Confirm there
   are no real names, email addresses, home addresses, record identifiers,
   credentials, private documents or machine paths. Also inspect image metadata;
   the checked-in captures contain no EXIF, comments or appended payloads.
6. Close the demo tab and stop the foreground command with **Ctrl+C**. Its
   temporary storage is discarded; the live app and mailbox remain untouched.

## Publication review

Ordinary screenshots and binary files remain blocked by the publication policy.
Only the three exact image paths and **reviewed SHA-256 byte hashes** in
[the screenshot allowlist](../scripts/reviewed-screenshots.mjs) are admitted.
Replacing even one byte requires a fresh visual/metadata review and an intentional
hash update. This prevents an accidental replacement from silently passing the
existing publication check; it is not automated PII detection or proof of consent.

For an intentional refresh, review the new image first, compute its hash with
`Get-FileHash -Algorithm SHA256`, and update only its allowlist entry. Never
broaden the policy to accept every image in a folder or bypass it with force-add.
Run `npm.cmd test` and `npm.cmd run publish:check`, then review the complete diff
and each image before committing or publishing. The fixture tests verify that
non-allowlisted operations are rejected and no mailbox account is enrolled.
