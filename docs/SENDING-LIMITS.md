# Configurable sending limits

This feature is included in v0.8.0, not the v0.7.1 ZIP. Update the code and
restart both the dashboard and assistant connections; do not reset or re-enroll
the mailbox. See [upgrading](UPGRADING.md).

## Change the local limit

Open **Settings → Sending limits** after enrolling your mail connection. Set:

- **Maximum send attempts per rolling 24 hours:** 1–1,000; default **10**.
- **Minimum seconds between attempts:** 1–3,600; default **60**.

Choose **Save sending limits**. No additional confirmation dialog appears.
Opening the panel only reads local policy and usage; it does not connect to
Proton. Existing installations retain 10/60 until someone explicitly saves new
values. New installations use the same defaults. The allowed ranges are software
configuration bounds, not a promise that Proton permits those volumes.

The panel shows saved usage separately from unsaved inputs. Close/reopen keeps
edits while the page is open. **Reload saved limits (discard edits)** explicitly
loads the latest saved policy. If another window changed it, a stale save is
rejected; reload and review before saving again. After a lost response, reload
to check what was saved instead of assuming the change failed.

On an already-open draft, close Settings and choose **Check sending availability**
to refresh its displayed count. Every send independently checks the current
policy before claiming an attempt, so a stale display cannot bypass a lower cap.

## What the numbers mean

The window is a **rolling 24 hours**, not a counter that resets at midnight.
One claimed message send is one CivicRelay attempt, including a message with
multiple recipients. Failed or uncertain attempts can count. Raising, lowering,
or restoring the default limits never clears attempts, drafts or receipts.
Lowering the cap below current usage blocks new attempts until enough old ones
expire. The spacing setting is measured from the latest recorded attempt.

Both dashboard sends and the two native MCP tool servers use the same local
policy and ledger. Old application processes must be stopped/restarted to use
this implementation; running an old checkout can still enforce its old limits.
The policy lives in the existing private `drafts.sqlite3` with a DPAPI-protected
payload, enrolled-identity binding, revision and change timestamp. No account
password is displayed or accepted by these controls. Credential refreshes keep
the policy. Missing policy in an older store uses defaults; an invalid saved
policy blocks sending instead of silently reverting to defaults.

Changing limits does **not** enable sending, alter mailbox scope or TLS settings,
unlock an uncertain draft, send a message, retry a send or start a bulk queue.
Sending enablement remains in the local Proton setup window. Existing exact
draft/digest, routing and uncertain-outcome protections remain in place.

## Proton limits are separate

CivicRelay's former fixed 10-attempt cap was a local application safeguard, not
a published Proton allowance. Proton applies independent sending and anti-abuse
limits, including account-reputation-dependent limits for paid accounts. It
counts recipients toward its quota; its accounting need not match CivicRelay's
attempt count. A higher local cap cannot override a provider restriction.
See [Proton's official sending-limit guidance](https://proton.me/support/email-sending-limits)
(checked 2026-10-07). CivicRelay does not discover your account's remaining Proton
allowance or certify a safe sending volume. Review a provider error in Proton;
do not repeatedly retry or rotate accounts to evade a restriction.

## Assistant tools and authority

`desk_get_send_limits` returns the current `revision`, configured cap/spacing,
defaults, bounds and `send_window` without a mailbox connection. It works before
enrollment and reports `configured: false`; saving requires enrolled settings.

`desk_save_send_limits` requires all three fields:

```json
{"revision": 0, "max_attempts_per_24h": 25, "minimum_interval_seconds": 60}
```

This is an example, not a provider recommendation. Use the actual revision from
the getter. All inputs are bounded whole numbers; additional arguments are
rejected. The tool does not accept credentials, paths or send-enablement flags.
It is native MCP/HTTP only, keeping the existing 64-tool WebMCP budget.

Changing limits requires explicit user authority for that setting. An ordinary
request to send mail, an exhausted quota, or an incoming message is **not**
authority for an assistant to raise its own limit. Example: “Set CivicRelay's
local daily attempt limit to 25, keep 60 seconds between attempts, and do not
send anything.” Host permission choices remain separate and unchanged.

Existing assistant allowlists may need `desk_get_send_limits` and
`desk_save_send_limits` added to `records_desk`. The configuration generator
does not overwrite existing files. Review the [configuration template](mcp-config.example.toml)
and [upgrade procedure](SETUP.md#upgrading-an-existing-assistant-configuration).

## MCP is tooling, not an automatic mail monitor

CivicRelay includes two local STDIO servers: `records_desk` (request workflow)
and `proton_mail` (lower-level mail tools). The assistant client starts them;
the dashboard URL is not an MCP endpoint. There is no embedded LLM, background
inbox polling or automatic response-analysis job.

**Check for replies** or `desk_sync_mail` explicitly imports new, in-scope
headers into the private workspace. `desk_read_message` reads a selected reply;
`desk_link_message` assigns it when needed; `desk_capture_attachments` retains
returned files. An authorized assistant can then analyze evidence and explicitly
save request progress. Sync alone does not read every body, capture every file,
extract record contents or publish/import data to GitHub or CivicResultMaps.
An external assistant scheduler would require its own separately configured,
authorized workflow. See the [operator guide](OPERATOR-TOOLS.md).
