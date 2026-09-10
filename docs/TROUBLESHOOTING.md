# Troubleshooting

Do not send a real test email to diagnose an installation problem. Start with
local status and synthetic tests; inspect receipts before retrying an operation.

| Symptom | What to check |
| --- | --- |
| Page does not open | Use `http://127.0.0.1:8766/`, not `localhost`, another hostname or a LAN address. Run `npm.cmd start` in a terminal to see bounded startup errors. |
| Port belongs to another/legacy dashboard | Identify the process command line and stop only the unwanted dashboard when no mail operation is active. The launcher deliberately refuses to reuse a different checkout. |
| Python or Node cannot be found | Use full installed executable paths through `CRM_PROTON_PYTHON` and `RECORDS_DESK_NODE`. Python needs Tkinter/pythonw; a Windows Store alias alone is not a full installation. |
| Tools do not appear | Generate and review the ignored project configuration, open the folder as trusted, then restart its MCP connections. STDIO tools do not use the HTTP dashboard URL. |
| Web page tools are unavailable | An ordinary browser may lack WebMCP. The dashboard and native MCP tools still work without that feature. |
| Mail is not configured | Only the intended project's human operator should run local setup. A public clone contains no enrollment or mailbox credentials. |
| Bridge connection fails after reboot | Start Bridge in the same Windows session and verify it remains signed in. Use `proton_check_connection`; it authenticates without reading bodies or sending. |
| Certificate pin mismatch | Investigate Bridge/account changes with the human operator. Do not turn off STARTTLS or pin validation; re-enroll only after verifying the legitimate local Bridge. |
| Send is disabled or counting down | Inspect local sending policy and the rolling quota. Nothing is queued. Cancelled pre-approval operations and uncertain transport outcomes are different states. |
| Send outcome is unknown/uncertain | Stop. Read the immutable draft receipt and reconcile with Proton Sent. Do not create a replacement draft or automatically retry to bypass a lock. |
| Approval window expired/cancelled | Review the returned result. An explicit cancellation before sending leaves the draft available; it does not authorize a later automatic send. |
| Case changed or unsaved edits block an action | Reread the case/workspace revision and preserve the human's unsaved work. Do not overwrite it with a stale tool snapshot. |
| An email is unassigned | Check exact message/thread identifiers and the responding office. Subject similarity alone is deliberately insufficient. |
| Missing states/requests | The map covers all states, but cases come from a reviewed public snapshot. Refreshing it is a maintainer operation; do not invent requests to fill the map. |
| Catalog/form hash mismatch | Stop and review the snapshot and Git attributes. Do not edit hashes or normalize the form's line endings to suppress an error. |
| GitHub intake fails | Check `gh auth status` and the configured absolute `RECORDS_DESK_GH` path. Preserve the prepared preview/receipt and determine whether an issue already exists before any retry. |
| Private storage is rejected | The stores must be outside Git working trees and must not use symlinks, junctions or hardlinks. Do not point `LOCALAPPDATA` at this checkout. |
| Data is unavailable under a different Windows user | DPAPI is tied to the user's Windows context. A code clone is not a data backup; do not export/copy private stores into Git. |
| Tests fail with `spawn EPERM` | A shell sandbox may prevent child processes. Run the same reviewed synthetic tests in a normal local console; do not weaken runtime guards. |
| Browser executable is missing | Run `npm.cmd exec -- playwright install chromium`, then retry the synthetic browser test. |

## Runtime settings and launch context

Environment values set in a PowerShell window affect processes launched from
that window. They do not update an already-running Codex process or a shortcut
launched by Explorer. Start from the configured terminal, or configure only the
non-secret executable paths in the Windows user's environment and restart the
affected app. Never put account secrets in environment examples or config files.

Keep Bridge, dashboard and assistant tools under the same normal Windows user.
An elevated, service, cloud, or different-user session can lack the intended
desktop approval/DPAPI context. Do not work around that by bypassing confirmation.

## Report a reproducible bug

Include Windows/Python/Node versions, the command or UI step, expected behavior,
the fixed/non-secret error text, and whether a synthetic test reproduces it.
Use fake addresses and synthetic examples. Omit real message bodies, full
screenshots of cases, credentials, database files, exported attachments and
personal paths. Use [CivicRelay issues](https://github.com/Camreyn/CivicRelay/issues)
for software bugs and [security guidance](../SECURITY.md) for sensitive findings.
