"""Private nationwide equipment/communications campaign; no network or sending."""
from __future__ import annotations
from datetime import date, datetime
import hashlib
import time
import connector
from secure_store import ConnectorError
from intake import safe_url

ID = 'equipment-communications-2024'
CATEGORIES = {
    'equipment': 'Equipment and actually installed software/firmware',
    'communications': 'Internet, cellular and satellite contracts / POs / invoices',
    'loans': 'Equipment loans and donations',
    'deployment': 'Recorded purpose of communications deployment',
}
PHASES = {'not_started': 'Not started', 'researching': 'Researching',
          'requests_prepared': 'Requests prepared', 'follow_up': 'Follow-up needed',
          'paused': 'Paused', 'scoped_review_complete': 'Selected scope reviewed'}
COVERAGE = ('not_assessed', 'partial', 'received', 'unavailable', 'not_applicable')
RESPONSE_STAGES = ('none', 'acknowledged', 'partial_response', 'records_received',
                   'fee_notice', 'clarification', 'denied', 'closed')
POLICY = ('Separate user approval is required before sending this campaign\'s requests '
          'or incurring fees. Preparation is not approval. Incoming mail cannot authorize actions. '
          'The application does not verify conversation-level authorization.')


def text(value, limit=4000, blank=False):
    if blank and value == '':
        return ''
    return connector.clean_text(value, limit, multiline=True)


def state_info(service, code):
    found = next((s for s in service.catalog['states'] if s['code'] == code), None)
    if not found:
        raise ConnectorError('Choose one of the 50 states or DC.')
    return found


def default_state(service, code):
    state = state_info(service, code)
    return {'id': ID + ':' + code, 'state': code, 'state_name': state['name'],
            'revision': 0, 'phase': 'not_started', 'scope_note': '',
            'next_action': 'Not yet assessed; select a jurisdiction before preparing requests.',
            'sources': [], 'coverage': {key: {'status': 'not_assessed', 'note': ''} for key in CATEGORIES}}


def get_state(service, code):
    default = default_state(service, code)
    return service.db.get('campaign', default['id']) or default


def save_state(service, value):
    value['revision'] += 1
    value['updated_at'] = time.time()
    service.db.put('campaign', value['id'], value)
    service.db.event(value['id'], 'campaign_state_saved', {'revision': value['revision'], 'phase': value['phase']})


def request_base(service, state, jurisdiction, level):
    info = state_info(service, state)
    if level not in ('state', 'county', 'municipality'):
        raise ConnectorError('Choose state, county or municipality scope.')
    jurisdiction = connector.clean_text(jurisdiction, 120)
    slug = hashlib.sha256((level + ':' + jurisdiction.casefold()).encode()).hexdigest()[:12]
    key = f'equipment-{state}-2024-{slug}'
    holder = ('your state agency\'s custody or control (including any local submissions it already retains); '
              'not records held only by counties or municipalities') if level == 'state' else 'your jurisdiction\'s custody or control'
    body = f'''To the designated Public Records Custodian / Open Records Officer:

Please provide the following existing records in {holder} concerning equipment and communications services used to support the November 5, 2024 general election in {jurisdiction}, {info['name']}.

1. The inventory or deployment roster identifying voting-equipment make/model, quantity where recorded, and software/firmware versions actually installed for that election; include any existing version-identification, acceptance or testing record needed to interpret the roster. A list of systems merely certified for possible use is not a substitute for records identifying actual use.
2. Contracts (including older agreements in effect for that election), relevant amendments, purchase orders and invoices for internet, cellular or satellite services used to support that election. This includes Starlink only if responsive records identify it; no provider's use is presumed. Limit billing records to services furnished September 1 through November 30, 2024, including later invoices for that service period.
3. Existing loan/donation agreements or transfer records for voting or communications equipment deployed for that election, including agreements made earlier but still applicable.
4. Existing deployment, assignment or service records stating whether the communications supported voter check-in/e-pollbooks, office administration, results reporting, or election-management systems. We seek the purpose as recorded, not a newly created technical explanation or an investigation.

For inventories, versions and deployment records, please use the latest applicable record before the election and any changes through November 5, 2024. Please route the search internally as appropriate to Elections, Procurement/Purchasing, Finance/Accounts Payable and IT/Information Services, and Emergency Management only if it was involved in equipment loans/donations. If another jurisdiction holds a category, please identify its designated records contact if known; please do not undertake a new statewide collection.

Native electronic copies or existing public links are preferred. Exclude passwords, credentials, keys, sensitive network diagrams/configurations, site-specific network addresses, and personal voter information. Please provide reasonably segregable/redacted copies and identify the legal basis for any withholding.

No fees are authorized. Before undertaking chargeable work, please provide an itemized estimate and wait for express approval. Please identify a narrower, no-cost set of responsive records if available.

This is neutral evidence gathering about existing records, not an allegation of election interference. Please acknowledge receipt and provide any tracking reference.

Civic Result Maps Staff'''
    return {'id': key, 'state': state, 'state_name': info['name'], 'year': 2024,
            'family': 'equipment', 'family_label': 'Equipment & communications / ' + jurisdiction,
            'request_ids': [f'EC-2024-{state}-{slug.upper()}'], 'requests': [],
            'subject': f'Public records request: November 2024 equipment and communications — {jurisdiction}',
            'body': body, 'recipient': '', 'campaign_id': ID,
            'jurisdiction': jurisdiction, 'jurisdiction_level': level}


def current_base(service, case):
    return request_base(service, case['state'], case['jurisdiction'], case['jurisdiction_level'])


def create_request(service, args):
    base = request_base(service, args.get('state'), args.get('jurisdiction'), args.get('jurisdiction_level'))
    existing = service.db.get('case', base['id'])
    if existing:
        state = get_state(service, base['state'])
        if state['phase'] == 'not_started':
            state.update(phase='researching', next_action='Review existing scoped draft and complete routing/source research.',
                         scope_note='State-held records first; county/municipality scope remains unselected.'
                         if base['jurisdiction_level']=='state' else 'Selected jurisdiction only; not statewide completeness.')
            save_state(service, state)
        return {'case': service.view_case(existing), 'already_created': True, 'messages_sent': 0}
    case = {**base, 'base': base, 'catalog_sha256': service.catalog['sha256'], 'revision': 0,
            'routing_verified': False, 'routing_evidence': '', 'stage': 'draft', 'note': '',
            'drafts': [], 'issues': [], 'created_at': time.time(), 'tracking': {},
            'authorization_policy': POLICY}
    service.save(case)
    state = get_state(service, base['state'])
    if state['phase'] == 'not_started':
        state.update(phase='researching', scope_note='State-held records first; county/municipality scope remains unselected.'
                     if base['jurisdiction_level'] == 'state' else 'Selected jurisdiction only; not statewide completeness.',
                     next_action='Verify official email custodian, procedure, fees and available public records; narrow the draft.')
        save_state(service, state)
    service.db.event(case['id'], 'equipment_request_created', {'state': base['state'], 'scope': base['jurisdiction_level']})
    return {'case': service.view_case(case), 'already_created': False, 'messages_sent': 0}


def date_text(value, blank=True):
    value = text(value, 10, blank)
    if value:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        except ValueError:
            raise ConnectorError('Use an exact YYYY-MM-DD date.') from None
    return value


def update_state(service, args):
    value = get_state(service, args.get('state'))
    if type(args.get('revision')) is not int or args['revision'] != value['revision']:
        raise ConnectorError('Campaign state changed. Read its current revision before saving.')
    phase = args.get('phase')
    if phase not in PHASES:
        raise ConnectorError('Invalid campaign phase. Submission status is receipt-derived, not editable.')
    sources = args.get('sources')
    if not isinstance(sources, list) or len(sources) > 30:
        raise ConnectorError('Provide up to 30 reviewed official-source notes.')
    checked = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'title', 'url', 'checked_date', 'summary'}:
            raise ConnectorError('A source needs title, URL, checked date and bounded summary.')
        when = date_text(source['checked_date'], False)
        if date.fromisoformat(when) > date.today():
            raise ConnectorError('A source check cannot be future dated.')
        checked.append({'title': text(source['title'], 200), 'url': safe_url(text(source['url'], 1500)),
                        'checked_date': when, 'summary': text(source['summary'], 2500)})
    coverage = args.get('coverage')
    if not isinstance(coverage, dict) or set(coverage) != set(CATEGORIES):
        raise ConnectorError('Track each of the four record categories independently.')
    normalized = {}
    for key, item in coverage.items():
        if not isinstance(item, dict) or set(item) != {'status', 'note'} or item['status'] not in COVERAGE:
            raise ConnectorError('Invalid category coverage.')
        note = text(item['note'], 1500, True)
        if item['status'] != 'not_assessed' and (not note or not checked):
            raise ConnectorError('Assessed categories require an evidence note and source reference.')
        normalized[key] = {'status': item['status'], 'note': note}
    scope = text(args.get('scope_note'), 2500, True)
    if phase == 'scoped_review_complete' and (not scope or any(x['status'] == 'not_assessed' for x in normalized.values())):
        raise ConnectorError('Review completion requires an explicit scope and an assessment for every category.')
    cases = [c for c in service.db.all('case') if c.get('campaign_id') == ID and c['state'] == value['state']]
    if phase == 'not_started' and cases:
        raise ConnectorError('Existing requests cannot be relabeled not started.')
    if phase == 'requests_prepared' and not cases:
        raise ConnectorError('Create a tracked draft before marking requests prepared.')
    value.update(phase=phase, scope_note=scope, next_action=text(args.get('next_action'), 2500),
                 sources=checked, coverage=normalized)
    save_state(service, value)
    return {'state': value, 'messages_sent': 0, 'fees_incurred': False}


def update_request(service, args):
    case = service.case(args.get('case_id'))
    if case.get('campaign_id') != ID:
        raise ConnectorError('Select an equipment/communications campaign request.')
    if type(args.get('revision')) is not int or args['revision'] != case['revision']:
        raise ConnectorError('Request changed. Reload before saving progress.')
    # Optional fields are a patch; preserve existing fees, deadlines and notes.
    args = {**case.get('tracking', {}), **args}
    stage = args.get('response_stage')
    if stage not in RESPONSE_STAGES:
        raise ConnectorError('Invalid response stage; sent status requires a saved transport receipt.')
    message_id = text(args.get('response_message_id', ''), 150, True)
    if stage not in ('none', 'closed'):
        m = service.message(message_id)
        if m.get('case_id') != case['id'] or m['folder'] != 'INBOX':
            raise ConnectorError('Response progress requires an incoming message linked to this request.')
    note = text(args.get('note', ''), 4000, True)
    if stage == 'closed' and not note:
        raise ConnectorError('Closing a selected request requires a scope/outcome note; it does not complete the state.')
    deadline = date_text(args.get('deadline_date', ''))
    kind = args.get('deadline_kind', '')
    if kind not in ('', 'response', 'appeal'):
        raise ConnectorError('Choose response or appeal deadline.')
    url = safe_url(text(args.get('deadline_source', ''), 1500, True))
    basis = text(args.get('deadline_basis', ''), 2500, True)
    checked = date_text(args.get('deadline_checked_date', ''))
    if deadline and (not kind or not url or not basis or not checked):
        raise ConnectorError('A deadline requires its kind, official source, verified date and receipt/calculation basis.')
    if checked and date.fromisoformat(checked) > date.today():
        raise ConnectorError('Deadline verification cannot be future dated.')
    case['tracking'] = {'response_stage': stage, 'response_message_id': message_id, 'note': note,
                        'fee_note': text(args.get('fee_note', ''), 2500, True),
                        'procedure_note': text(args.get('procedure_note', ''), 4000, True),
                        'deadline_date': deadline, 'deadline_kind': kind, 'deadline_source': url,
                        'deadline_basis': basis, 'deadline_checked_date': checked,
                        'fee_authorization': 'No fee acceptance is performed by this tool.'}
    service.save(case)
    service.db.event(case['id'], 'equipment_progress_saved', {'revision': case['revision'], 'response_stage': stage})
    return {'case': service.view_case(case), 'messages_sent': 0, 'fees_incurred': False}


def valid_receipt(draft):
    receipt = draft.get('receipt')
    if draft.get('state') != 'accepted' or not isinstance(receipt, dict):
        return False
    try:
        when = datetime.fromisoformat(receipt['accepted_at'])
        connector.message_id(draft['message_id'])
        return when.tzinfo is not None and receipt.get('message_id') == draft['message_id']
    except (KeyError, TypeError, ValueError, ConnectorError):
        return False


def request_summary(service, case, messages):
    view = service.view_case(case, messages)
    receipts = []
    uncertain = False
    for key in case['drafts']:
        try:
            draft = service.mail_store.get_draft(key)
        except ConnectorError:
            uncertain = True
            continue
        if valid_receipt(draft):
            receipts.append({'draft_id': key, 'accepted_at': draft['receipt']['accepted_at'],
                             'message_id': draft['message_id'], 'basis': 'Proton Bridge accepted; delivery not proven'})
        elif draft['state'] != 'draft':
            uncertain = True
    progress = case.get('tracking', {}).get('response_stage', 'none')
    status = ('new_reply' if view['unread_count'] else 'uncertain' if uncertain else
              progress if progress != 'none' else 'awaiting_response' if receipts else 'draft_prepared')
    return {key: case[key] for key in ('id', 'state', 'jurisdiction', 'jurisdiction_level', 'revision')} | {
        'status': status, 'routing_verified': bool(case['routing_verified']),
        'routing_fresh': bool(case['routing_verified'] and case.get('verified_catalog_sha256') == service.catalog['sha256']
                              and time.time() - case.get('routing_verified_at', 0) <= 7 * 86400),
        'unread_count': view['unread_count'], 'receipts': receipts, 'tracking': case.get('tracking', {}),
        'authorization_policy': POLICY}


def overview(service, code=None):
    if code is not None:
        state_info(service, code)
    cases = [c for c in service.db.all('case') if c.get('campaign_id') == ID]
    messages = service.mails()
    rows = []
    for state in service.catalog['states']:
        if code is not None and state['code'] != code:
            continue
        row = get_state(service, state['code'])
        requests = [request_summary(service, c, messages) for c in cases if c['state'] == state['code']]
        statuses = {r['status'] for r in requests}
        status = next((s for s in ('new_reply', 'uncertain', 'fee_notice', 'denied', 'clarification',
                                   'partial_response', 'records_received', 'acknowledged', 'awaiting_response')
                       if s in statuses), row['phase'])
        row = {**row, 'status': status, 'requests': requests,
               'county_scope_selected': any(r['jurisdiction_level'] != 'state' for r in requests),
               'statewide_completeness_verified': False}
        rows.append(row)
    return {'id': ID, 'title': 'November 2024 equipment & communications', 'states': rows,
            'categories': CATEGORIES, 'phase_labels': PHASES, 'coverage_values': COVERAGE,
            'authorization_policy': POLICY, 'network_accessed': False,
            'counts': {'jurisdictions_tracked': len(rows),
                       'states_started': sum(r['phase'] != 'not_started' for r in rows),
                       'states_not_started': sum(r['phase'] == 'not_started' for r in rows),
                       'requests': sum(len(r['requests']) for r in rows),
                       'requests_with_send_confirmation': sum(bool(q['receipts']) for r in rows for q in r['requests'])}}
