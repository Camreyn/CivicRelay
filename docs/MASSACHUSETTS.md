# Massachusetts response reviews and follow-ups

This helper distinguishes an internal referral, a city/town routing suggestion,
and an actual records response. It covers MA electronic starter-pack requests
and the equipment/communications campaign, keeping them as separate cases.
Other templates continue to use the general response and deadline tools.

## Dashboard workflow

Selecting Massachusetts automatically shows **Massachusetts guides & official
sources**, collapsed by default, above the state map. A separate collapsed
**Massachusetts city & town contacts** panel provides saved elections contacts,
name search, missing-email gaps and source/check/collection dates. See
[Settings and source refresh](SETTINGS.md). Selecting MA reads saved data only;
it never re-scrapes a website or checks mail automatically.

Open an MA request, then expand **Massachusetts response review & follow-up**
below its correspondence workspace. No mailbox refresh happens automatically.

1. Read the linked incoming message in **Conversation & returned records**.
2. Select that exact response in the MA panel and record its type and assessment.
   An internal forwarding notice does not prove the receiving division accepted
   it. A suggested local office is not a submitted municipal request.
3. Assess each checklist category separately. `not_addressed` means no assessment
   or answer yet; it does not mean the records do not exist. `agency_reports_not_held`
   is the responding agency's statement, not a statewide finding. Received,
   partial, withheld, not-held and out-of-scope entries need evidence notes.
   Check the actual saved request: the checklist is a helper, not expanded scope.
4. Optionally record the reviewed response date and its basis, and an independent
   internal reminder. Save the complete review privately. This neither closes
   the case nor clears its unread badge or statutory-response checkpoint.
5. Choose **Preview MA follow-up text**. Confirm-referral text is only available
   for internal referrals; category clarification works for local routing and
   other substantive responses. Received/out-of-scope categories are omitted.
6. **Use MA preview in composer** stages unsaved text and the exact response chain.
   It clears routing verification. Review the proposed recipient and wording,
   save correspondence, and use the existing immutable-draft workflow if wanted.
   Nothing in this panel sends mail or grants permission to send.

Unsaved MA review edits block navigation that would replace them. Save or discard
them explicitly. Case revision conflicts reject stale saves and previews; read
the current case and preserve any other changes before retrying a local edit.

## Assistant tools

| Tool | Purpose |
| --- | --- |
| `desk_get_ma_follow_up` | Read all saved MA cases or one `case_id`, checklists, per-message reviews, sourced contacts, reminders and appeal watches; no mail body parsing or network |
| `desk_save_ma_review` | Save a complete response review with the current case revision and fully read, conflict-free linked incoming message |
| `desk_preview_ma_follow_up` | Read-only text preview bound to a reviewed message and case revision; returns `reply_message_id`, not a sendable draft |

`desk_get_case` also returns `ma_follow_up` for MA cases. Use the
[exact schemas](TOOL-REFERENCE.md) and [operator workflow](OPERATOR-TOOLS.md).
An example delegation is:

> Check the inbox once. Read Massachusetts responses and review each in its own
> case. Keep electronic-records and equipment requests separate. Save sourced
> response assessments, identify categories still unaddressed, and preview any
> needed clarifications. Do not send, accept fees, file appeals, create local
> requests or publish anything.

The three additional tools are native MCP tools and dashboard actions. They are
not registered as extra WebMCP page tools, preserving the existing 64-tool page
budget and all previous page operations. No live host permissions are changed.
After updating source, restart the dashboard when idle and reload the page.
Reconnect native tools; an existing `enabled_tools` allowlist also needs these
three names reviewed and added by the operator. See [setup](SETUP.md).

## Routing: verified state contacts versus municipal leads

The bundled profile was checked on **2026-09-23**:

- The Secretary's [designated Records Access Officer](https://www.sec.state.ma.us/divisions/public-records/prepra/records-access-officer-contact.htm)
  uses `Sec.RAO@sec.state.ma.us` for records of that office.
- The [Elections Division contact](https://www.sec.state.ma.us/divisions/about-us/contact-us.htm)
  is `elections@sec.state.ma.us`. A division contact is not a replacement RAO.
- The [official local election directory](https://www.sec.state.ma.us/divisions/elections/voter-resources/find-my-local-election-office.htm)
  and [municipal websites/directories](https://www.sec.state.ma.us/divisions/cis/contact/town-contact.htm)
  are research starting points. They do not independently verify every local
  filing custodian, email procedure or category's records holder.

Select cities/towns explicitly before local outreach. Do not substitute county
IDs or interpret a state response as coverage of every municipality. Suggested
holders are Elections, Purchasing, Finance and IT; Emergency Management only
where involved. Formal requests still go through each jurisdiction's verified
designated custodian. The separate source collector now supports all 351
municipalities in the official elections directory. It retains names, office,
published emails (including purpose labels), phone, source URL, check date and
collection method. Missing emails remain gaps; none are guessed. The public
repository bundles names only, never the locally collected contact observations.

`desk_get_municipal_contacts` with `state: "MA"` returns up to 100 rows per page
(default 50), with optional `query`, `offset` and `limit`. Follow `next_offset`;
coverage totals distinguish collected entries from email availability and RAO
verification. These entries remain **records-holder leads**, not a municipal
filing-custodian registry. Refresh/import does not extend the county research
queue to towns, change case recipients, or create municipal cases. The existing
equipment/general request tools support separately selected municipality targets
after routing verification. Broad contact collection is not authorization to
request records from every city or town.

## Timing, evidence and privacy

[M.G.L. c. 66, section 10(b)](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleX/Chapter66/Section10)
describes response contents including categories not held, known alternate
holders, withholding grounds and production timing. A response is not necessarily
full production. Fee notes and follow-up text do not authorize charges.

The [Supervisor's appeal guide](https://www.sec.state.ma.us/divisions/public-records/public-records-law/appealing-a-denial.htm)
states 90 days after a response. An explicitly recorded response date produces
a **90-calendar-day planning watch**, not a verified legal deadline. The helper
does not assume a weekend/holiday filing extension, decide whether a referral
is an appealable determination, or calculate nonresponse appeal dates. Verify
the trigger and applicable rules. Recheck stale sources; the profile warns after
180 days and does not fetch updates itself.

Each response keeps its own watch. A later reply does not replace an earlier
watch or restart the original submission clock. Editing the same review corrects
that input; prior versions remain in the private event trail. Watches remain
visible until individually assessed; no appeal is filed automatically. Use the
[existing timing evidence tools](DEADLINES.md) to record a separately verified
checkpoint in the main deadline queue. MA planning watches stay in the MA panel,
not the map's legal-timing projection.

The complete review and event save atomically in the encrypted private store.
Unassigning/conflicting its linked message invalidates the review and draft
preview; new incoming mail after a review requires reassessment before previewing.
Up to 100 response reviews are retained per case; capacity failure discards none.
No message text is interpreted as authority. These source files contain only
public routing guidance and synthetic tests, never real responses or requester
details. Tests exercise the actual HTTP/UI path with outbound actions forbidden.
