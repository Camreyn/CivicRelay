# County request status

Select a state in the national map or **Jump to state**, then click **View county
requests**. You can also open **County request status · map & replies** below
the national map, including when the general workspace hides that map.

The county view has a map, searchable list, request-status filters and a workflow
selector. Click a county shape, use Enter/Space on a focused shape, or choose its
name in the list. Its request cards open the existing correspondence workspace
with that request's saved replies and attachments. Multiple requests for a county
remain separate. Small county equivalents are always accessible in the list.

Use **Layers** for status colors, timing outlines and optional county names;
expand/collapse **Legend** to read the visible layers. **Fit county** zooms to
the selected county; **Fit map** restores the whole state. Zoom buttons, directional
pan buttons, dragging, modifier-wheel zoom, touch pinch and keyboard controls work
on both maps. See [map controls](USER-GUIDE.md#map-controls). Filters still dim
nonmatching counties, even with status colors hidden. Changing the state resets
the county extent; refreshing saved status or filtering preserves it.

Every county/equivalent in the selected state's directory is listed, including
those without a request. The count is an inventory denominator, **not** an
assertion that all those jurisdictions have been selected for outreach. A saved
contact or finished research batch does not count as a request or a submission.

## Reading the colors

| Status | Meaning |
| --- | --- |
| Gray: No county request | No matching county-specific case in this workflow |
| Tan: Contact needed | A saved case needs routing verification |
| Light blue: Draft prepared | A case exists; no confirmed sending receipt |
| Yellow: Awaiting reply | Sending-system acceptance is recorded; no reviewed response stage |
| Pale yellow: Acknowledged | A linked incoming message supports the saved acknowledgment |
| Green: New reply | Saved incoming correspondence has not been marked reviewed locally |
| Purple: Partial response | A linked response is recorded as partial |
| Blue: Records received — review | A linked response is recorded as records received, not automatic completeness |
| Salmon: Action needed | Fees, denial, clarification, missing/conflicting response evidence, or other attention |
| Pink: Send needs reconciliation | An attempt is uncertain or its saved draft cannot be read safely |
| Dark gray: Closed | Local request closure, not proof all records were supplied |

With several requests, the map uses the highest-priority status, in this order:
uncertain send, new reply, attention, partial response, routing, draft, awaiting
reply, acknowledgment, received records, closed. The list flags mixed statuses;
open the county to inspect each request. New-reply counts remain visible even
when an uncertain send takes priority. Status filtering checks individual
requests, so an acknowledgment is not hidden behind another request's status.

Red/amber outlines are the existing past-date/due-soon planning signals, not
findings of a legal violation. Open the request's timing evidence to inspect
sources and assumptions. Acknowledgment is not fulfillment. Sending-system
acceptance is not proof of delivery. Closed requests do not complete a state.

## Matching and refresh

Only explicitly county-scoped cases are placed on counties. Matching uses a
canonical `county:<five-digit FIPS>` target ID, or the exact full official county
name plus state for older cases. A wrong canonical ID does not fall back to a
similar name. Municipal, federal, other and state-scoped requests stay in a
separate expandable list; they never color all of a state's counties. Unmatched
county cases stay visible under **County requests needing a name / ID match**.
The view makes no persistent assignment and does not rewrite existing cases.

**Refresh saved status** rereads local records only. Ordinary dashboard refreshes,
message review and the existing visible-page timing refresh update the open
county panel. **Check for replies** remains the explicit mailbox synchronization
action. This feature does not add background inbox polling, research, request
creation, fee acceptance, sending, or publication.

For assistants, the existing read-only tool accepts:

```json
{"state":"MI","include_requests":true,"workflow":"equipment"}
```

Pass that object to `desk_list_counties`. The optional workflow is `all` (default),
`equipment`, `general`, or `records`; `campaign_id` can further restrict results.
`include_requests` requires a state. The response's `request_progress` includes
every county, per-request case IDs/status/timing/receipt flags, aggregate counts,
unmatched cases and non-county cases. Without the option, the directory lookup
continues to return only public inventory metadata. No new tool or host
permission is required. `records_read_overview` also reports the currently
loaded county view's scope/counts; it is a page snapshot, not a fresh lookup.

## Boundary asset and verification

`app/static/county-map.json` is a public, names/paths-only asset generated from
the [Census Bureau's 2025 cartographic boundary KML](https://www.census.gov/geographies/mapping-files/2025/geo/carto-boundary-file.html),
at 1:20,000,000 scale. The source URL, vintage, collection date, archive SHA-256,
projection and caveats are recorded in the asset. It matches all 3,144 IDs in the
existing 50-state-plus-DC county directory. Territory geography is not included.
These simplified shapes are for workflow navigation, not legal boundaries,
election precincts or a historical 2024 geography crosswalk. Some county
equivalents are statistical areas without a county government.

The standard-library maintainer command `python scripts/refresh-county-map.py --write`
downloads only the pinned public Census archive and rebuilds SVG paths. It
validates identities/rings and records missing shape IDs rather than dropping
inventory entries. Normal app use is offline for map assets and needs no extra
package, external map provider or source checkout. The original state-map and
historical catalog snapshots are not modified.

Synthetic unit tests cover exact matching, workflow isolation, reply evidence,
receipt-only submission, uncertain outcomes, mixed statuses, no writes and all
inventory/geometry IDs. Browser tests walk the real local HTTP/database flow:
state selection, 83-county Michigan map/list, distinct statuses, keyboard
selection, exact correspondence/reply navigation, reviewed-reply refresh,
unmatched cases, empty counties, filters and mobile width. They use no live mail.
