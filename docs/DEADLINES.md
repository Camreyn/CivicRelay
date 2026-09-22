# Deadlines and follow-ups

CivicRelay automatically recalculates **planning estimates** from saved request
receipts and reviewed timing evidence. It does not determine that an agency
violated the law, award damages, file appeals, accept fees or send follow-ups.
An initial response is not necessarily complete record production.

## In the dashboard

**Deadlines & follow-ups** spans all workflows, including generic campaigns and
the optional starter pack. The default view shows past dates, dates approaching
within two planning business days, and replies needing timing review. Choose
**All requests** to see unsent requests, unsupported jurisdictions and profiles
with no fixed numerical response period.

- **Potentially overdue**: an estimated initial-response date has passed. Verify
  proper filing, actual receipt, applicable calendar and the full conversation.
- **Past recorded date**: an operator-recorded agency, extension, appeal or legacy
  deadline has passed. The app has not independently validated that date.
- **Follow-up reminder due**: an internal reminder, not a statutory deadline.
- **Reply / timing evidence needs review**: incoming mail or changed evidence
  needs assessment; an acknowledgment is not automatically legally sufficient.
- **No fixed statutory day count**: the profile describes a prompt-response
  standard, without inventing a universal number of days.
- **Timing basis needs review**: no applicable automatic profile, a portal start
  date is missing, or a required formal-filing prerequisite remains unverified.

The map keeps its correspondence-status fill colors. A red outline means a
timing date has passed; amber means due today/soon. Map outlines apply to the
selected workflow; the deadline queue always includes all workflows. Labels and
accessible map descriptions convey the same information without relying on color.

Dates refresh every minute while the page is visible, when it becomes visible
again, on normal dashboard refresh, and through **Recheck dates**. Native tool
reads also calculate fresh dates without needing a browser. This is not a
background scheduler: a closed app sends no alerts. No automatic mailbox polling
is added. **Check for replies** remains a separate explicit action.

The queue reports the last inbox sync and warns after 24 hours, if more headers
remain to be synchronized, or if incoming mail is unassigned/conflicting. Even a
recent sync is not proof that every response was delivered or correctly linked.

## Calculation and source limits

The versioned [rule registry](../app/deadline-rules.json) includes legal citations,
official-source URLs, rule descriptions and its review date. **Sources & timing**
shows the applicable source, receipt basis, each checkpoint and warnings.
The app displays links; it does not fetch statutes, ingest web pages, or silently
update law while checking dates. It warns when the bundled review is older than
180 days. Recheck the current statute and the agency's procedures before relying
on a date. The registry is a general current-law profile, not a historical-law
database or coverage of special record types.

Current profiles cover AK, AZ, GA, IN, MA, MI, NC, NV, NY, PA, SD, TX and WI, plus
federal agencies. All other states, DC and unsupported scopes remain explicit
review-needed cases. Alaska's numerical profile is state-agency-only. South
Dakota's formal written-request profile requires an explicit formal-filing
assessment. State profiles are not substitutes for local agency procedures.

| Profile | Initial planning checkpoint | Official source |
| --- | --- | --- |
| Alaska state agencies | 10 working days; review extensions and fees | [DOJ APRA guidance, 2 AAC 96.325](https://www.law.alaska.gov/doclibrary/APRA.html) |
| Arizona | Prompt response; no general fixed count | [A.R.S. 39-121.01](https://www.azleg.gov/ars/39/00121-01.htm) |
| Georgia | 3 business days for records or applicable written response | [AG statute text, 50-18-71](https://law.georgia.gov/document/here-3/download) |
| Indiana | 7 calendar days for the initial emailed-request response; verify current procedures | [PAC discussion of IC 5-14-3-9(c)](https://www.in.gov/pac/files/advisory/25-FC-127-Frazee.pdf), [DOR email guidance](https://secure.in.gov/dor/legal-records-requests/) |
| Massachusetts | 10 business days; weekend/holiday receipt adjustment | [M.G.L. c. 66, section 10](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleX/Chapter66/Section10), [950 CMR guidance](https://www.sec.state.ma.us/divisions/public-records/download/guide.pdf) |
| Michigan | Email receipt shifts one business day; then 5 business days for response/extension notice | [MCL 15.235](https://www.legislature.mi.gov/documents/mcl/pdf/mcl-act-442-of-1976.pdf) |
| North Carolina | Prompt production; no general fixed count | [N.C.G.S. 132-6](https://www.ncleg.gov/enactedlegislation/statutes/html/bysection/chapter_132/gs_132-6.html) |
| Nevada | 5 business days for access or applicable written notice | [NRS 239.0107](https://www.leg.state.nv.us/NRS/NRS-239.html#NRS239Sec0107) |
| New York | 5 business days for access, denial or acknowledgment with estimate | [Public Officers Law 89(3)(a)](https://www.nysenate.gov/legislation/laws/PBO/89) |
| Pennsylvania | 5 business days following proper officer receipt; extensions separate | [OOR guide to sections 901–902](https://www.openrecords.pa.gov/RTKL/CitizensGuide.cfm) |
| South Dakota | 10 business days for the formal written-request procedure | [SDCL 1-27-37](https://sdlegislature.gov/api/Statutes/1-27-37.html?all=true) |
| Texas | Prompt production; 10-business-day written-availability checkpoint, not a universal production allowance | [Government Code 552.221](https://statutes.capitol.texas.gov/Docs/GV/htm/GV.552.htm#552.221) |
| Wisconsin | As soon as practicable without delay; no general fixed count | [Wis. Stat. 19.35](https://docs.legis.wisconsin.gov/statutes/statutes/19/II/35), [DOJ guide](https://www.wisdoj.gov/Open%20Government/PRL_guide.pdf) |
| Federal agencies | 20 working days for determination, not full production | [5 U.S.C. 552(a)(6)](https://www.justice.gov/oip/freedom-information-act-5-usc-552) |

The engine excludes the receipt/start day. Business-day estimates exclude
weekends, observed [U.S. federal holidays](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/)
and additional nonworking dates recorded for the custodian. This baseline is
**not a verified state/local calendar**. State holidays, optional closures,
special records statutes, after-hours receipt, routing, clarification, fees and
other tolling can change a deadline. Indiana's calendar-day end-date treatment
and current APRA procedures require review. Profiles use a planning time zone;
operators can select the custodian's actual zone. The stdlib implementation uses
post-2007 U.S. daylight-saving rules, not a complete historical time-zone database.

Only the earliest valid **accepted initial draft** starts an automatic email
estimate. Bridge acceptance is not proof of delivery or legal receipt. Drafts,
missing/invalid receipts and uncertain outcomes do not fabricate sent status.
Threaded follow-ups and `last_sent_at` never restart the original clock. Recorded
portal submissions require an explicitly reviewed start date; they do not inherit
the email-receipt adjustment.

## Recording evidence

Open **Sources & timing → Record receipt, response or next checkpoint**:

1. Distinguish a verified formal filing from an information inquiry. A formal
   flag requires saved custodian-routing verification; it is still operator judgment.
2. Optionally enter the **statutory receipt/start date** and evidence basis.
   Include any legally required email adjustment yourself: it is not applied a
   second time to an explicit override. Link the receipt message when available.
3. Review actual linked mail before recording the initial response as satisfied.
   Save the message ID and why the notice meets the requirement. Merely reading
   or marking mail reviewed does not satisfy this checkpoint.
4. Record the next event separately. Agency commitments and extensions require
   the linked notice, official source, checked date and basis. Appeal dates require
   a source and case-specific calculation, not an automatic guess. An internal
   follow-up needs a date and basis but is clearly labeled as nonlegal.
5. Mark a checkpoint completed when appropriate, or replace it with the next
   reviewed event. One explicit next checkpoint is supported per case, alongside
   the original initial-response checkpoint and any legacy recorded date. Each
   saved evidence revision is retained in the private event trail, including
   prior checkpoint dates and the rule-registry version.

New linked mail after review triggers timing review again. Unassigning or
conflicting evidence invalidates its use in the projection. Evidence edits are
revision-controlled and recorded in the existing encrypted case/event store.
Existing correspondence, deadline notes, fee notes and transport receipts are
preserved. Local closure resolves the initial and legacy checks; an explicit
next checkpoint remains until separately completed (an appeal may outlive closure).

Unsaved timing forms survive clock refreshes. Navigation that would replace
them is blocked until saved or explicitly discarded. The evidence picker shows
the latest 30 messages and existing saved evidence IDs; native tools can select
older linked messages after paginating `desk_list_messages`.

## Assistant tooling

`desk_get_deadlines` is read-only and accepts an optional `case_id`. It returns
the queue, rule registry, calculation basis, checks, warnings and mailbox freshness.
`desk_get_case` also includes its `case.deadline` projection.

`desk_save_deadline_tracking` accepts the current `case_id` and `revision`, plus
only the evidence fields being changed. Omitted fields are preserved. To clear a
next checkpoint, clear `next_date` and `next_kind`, and set `next_completed` false.
Changing a reminder alone does not silently review a newer incoming message.
The shared [tool reference](TOOL-REFERENCE.md) defines every field.

Example assistant request:

> Read the deadline queue and explain anything potentially overdue, including
> the linked legal source, receipt assumptions and inbox freshness. Review any
> linked responses before recording an extension or agency-promised date. Keep
> internal follow-up reminders separate from legal deadlines. Do not send,
> accept fees, file appeals or publish anything as part of this check.

New tools are present in the public starter configuration; existing installations
retain their current host configuration. No permissions or live allowlists are
changed by this feature. See [setup](SETUP.md) when refreshing tool configuration.

## Maintaining profiles

Read the current primary source and applicable official guidance before changing
a rule. Update the registry version/review date, legal citation, scope and caveats
together. A rule change requires synthetic calculation tests for receipt timing,
calendar handling and response type. Never claim all-state or jurisdiction-specific
accuracy based on the federal holiday baseline. No mail content may modify the
registry or grant authority to act. See [testing](TESTING.md).
