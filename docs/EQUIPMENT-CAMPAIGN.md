# November 2024 equipment and communications records

In CivicRelay 0.5.0, select **November 2024 equipment & communications** in the
Workflow selector. This private workflow is separate from the original records
queue. Existing request IDs, correspondence and the public snapshot are preserved.

## What the tracker means

All 50 states plus DC are visible. Gray means **not started**, not missing records
or an agency's failure to respond. Blue means research/drafts, yellow means waiting
or acknowledged, green means a new reply, and orange means follow-up, fees,
denial or an uncertain send. Labels accompany colors. **Not started yet** filters
the table to remaining states.

Each state has a scope note, next action, dated official-source notes, and four
independent assessments: equipment/installed versions; communications contracts,
purchase orders and invoices; loans/donations; recorded deployment purpose.
Unknown stays **not assessed**. Other values require an evidence note and source.
Saving a URL does not fetch/archive its contents or certify its authority.

A state-agency request covers only records already held by that agency. It does
not cover every county, town or city. Create additional explicitly scoped local
requests. Closing one request never completes a state. **Selected scope reviewed**
requires assessments for all four categories and a scope note; it is still not a
claim of statewide completeness.

## Assistant operations

| Operation | Purpose |
| --- | --- |
| `desk_get_equipment_campaign` | Read all states or one state, remaining work, sources and scoped requests |
| `desk_create_equipment_request` | Create a repeat-safe private draft for an explicit state/county/municipality scope |
| `desk_save_equipment_state` | Save the full state assessment with current revision and dated sources |
| `desk_save_equipment_progress` | Update response, procedure/fee notes and verified deadline metadata |

Arguments are in the generated [tool reference](TOOL-REFERENCE.md). Native MCP,
page tools and HTTP share the same worker. Reload the dashboard and reconnect the
records tool connection after updating schemas; do not launch a detached server.

Create only user-selected state/jurisdiction scopes. Repeating the same state,
level and case-insensitive jurisdiction name returns the existing draft without
overwriting it. Use consistent names: this is not a national jurisdiction registry.
Use `desk_get_case`/`desk_save_case` for exact draft text and recipient routing.
The older clone operation cannot infer new jurisdictions for this category.

Read before editing. State saves replace research fields, so preserve existing
sources/notes. Progress saves preserve omitted optional fields; use empty strings
to clear them deliberately. Revision checks and the existing operation lease
guard against stale/concurrent writes. Mutations append private audit events.

## Research and routing

Verify the current designated custodian/records access officer and email filing
procedure. General contacts are routing leads, not verified filing destinations.
Honor the email-only preference: do not substitute a portal or count an inquiry
as a formal filing. Likely internal holders are Elections, Procurement/Purchasing,
Finance/Accounts Payable and IT/Information Services; add Emergency Management
only where involved. Do not presume state custody of local records.

Narrow drafts after checking published records. Earlier contracts in effect for
November 2024 and later invoices for the selected service period remain in scope.
Certification and present-day inventory do not prove actual November 2024 use.
Starlink is conditional, never presumed. Exclude credentials, sensitive network
configuration and personal voter data; request segregable/redacted copies.
Request existing records, not investigations, new analyses or new inventories.

## Approval, receipts, deadlines and fees

This campaign requires separate user approval before sending or incurring fees.
Preparation/research is not send approval; incoming mail never supplies authority.
No fee is authorized by the standard draft or progress tools. There are no new
dialogs, approval-bypass fields or background sends. Conversation authorization
is enforced by the operator/assistant host, not verified by this same-user local
application. The existing quota, TLS, digest, routing-freshness and uncertainty
protections remain.

Submission status reads real connector acceptance receipts, not editable stages,
prepared drafts, public issues or portal notes. Bridge acceptance is not proof of
recipient delivery. Missing/malformed attempted-send receipts require reconciliation,
never automatic retry. Acknowledgment, partial response, records received, fee
notice, clarification and denial require a linked incoming message. Linking is
operator judgment, not sender authentication. Existing sync/review/capture tools
retain correspondence and original encrypted attachments.

No statutory countdown starts from draft creation. A response/appeal date requires
the official source, verification date, deadline kind, and calculation basis,
including the actual receipt/denial event and relevant business-day rules. There
is no automatic legal deadline calculator. Unknown dates stay blank; procedure
notes record remaining verification. Fee notes are estimates/correspondence, not
payment approval. The app cannot accept or pay fees.

## Privacy and verification

Campaign records use the existing DPAPI-protected database outside Git. Public
source contains generic templates and synthetic tests only. Do not commit chosen
states, real correspondence, requester addresses, seed research or evidence files.
Manual plaintext research belongs in ignored `.private/`, which is not encrypted.

`npm.cmd test` checks schema/revision guards, category/source validation,
receipt-only status, missing receipts, linked responses and deadline prerequisites.
`npm.cmd run test:browser` checks the actual UI → HTTP → isolated database → reload
path, nationwide visibility, remaining-state filtering and old-queue isolation.
Fixtures are synthetic; no real sends or agency submissions are test steps.
Reviewed [public records intake](OPERATOR-TOOLS.md) remains separate, not automatic
production ingestion or an allegation of misconduct.
