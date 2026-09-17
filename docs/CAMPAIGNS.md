# Generic campaigns

A generic campaign groups local targets under a template and date range. Targets
may be federal, state, county, municipality, or other; a state code is optional
but, when supplied, must match the bundled state/DC list. Campaign coverage is a
local planning record, not a claim of geographic completeness.

Saving a campaign requires revision control and an active template. Targets that
already have saved cases cannot be removed. The campaign listing reports target
progress and remaining targets without contacting mail or any external service.

Creating a request freezes the selected template's current latest
version/hash, rendered subject/body, declared values, campaign dates, target and
agency data. This release retains older versions for history but does not offer
choosing one for a new generic request. Subsequent template edits, imports,
archiving, or campaign edits do not invalidate that saved case. Repeating the
same campaign/target/template/agency/value request is idempotent and returns the
existing private case rather than creating a second initial request.

Progress separates agency response research from transport status. A response
stage other than `none` or `closed` requires an exact saved incoming message that
is already linked to that case. Fee, procedure and deadline notes are private;
recording them does not accept a fee. Deadlines require kind, official source,
basis and checked date. Sending remains receipt-derived through the existing
reviewed correspondence workflow; no campaign status can claim that a request was
sent.

Publication is independent of response progress. Generic cases use an explicitly
configured private publication destination and do not inherit a template's
destination or publication authority.
