"""Read-only county request projections. No guessed geography or status writes."""
from collections import Counter
import time

import contacts
import equipment
from secure_store import ConnectorError

LABELS = {'none': 'No county request', 'routing': 'Contact needed', 'draft': 'Draft prepared',
          'waiting': 'Awaiting reply', 'acknowledged': 'Acknowledged', 'new': 'New reply',
          'partial': 'Partial response', 'received': 'Records received — review',
          'attention': 'Action needed', 'uncertain': 'Send needs reconciliation', 'closed': 'Closed'}
PRIORITY = ('uncertain', 'new', 'attention', 'partial', 'routing', 'draft', 'waiting', 'acknowledged', 'received', 'closed')


def identity(case, rows):
    """Only explicit county scope plus canonical ID or exact full official name."""
    target = case.get('target', {})
    level = target.get('level', case.get('jurisdiction_level'))
    if level != 'county':
        return None
    code = target.get('id', '')
    if code.startswith('county:'):
        return next((c['id'] for c in rows if c['id'] == code), None)
    name = target.get('label', case.get('jurisdiction', ''))
    return next((c['id'] for c in rows if c['name'].casefold() == name.strip().casefold()), None)


def request_summary(service, case, messages):
    view = service.view_case(case, messages)
    linked = [m for m in messages if m.get('case_id') == case['id'] and m.get('folder') == 'INBOX']
    tracking = case.get('tracking', {})
    stage = tracking.get('response_stage', 'none')
    evidence = next((m for m in linked if m['id'] == tracking.get('response_message_id') and not m.get('thread_conflict')), None)
    review_needed = any(m.get('thread_conflict') for m in linked) or (stage not in ('none', 'closed') and not evidence)
    receipts, uncertain = [], False
    for key in case.get('drafts', []):
        try:
            draft = service.mail_store.get_draft(key)
        except ConnectorError:
            uncertain = True
            continue
        if equipment.valid_receipt(draft):
            receipts.append(draft['receipt']['accepted_at'])
        elif draft.get('state') != 'draft':
            uncertain = True
    status = ('uncertain' if uncertain else 'new' if view['unread_count'] else
              'attention' if review_needed else
              'closed' if case.get('stage') == 'closed' else
              {'fee_notice': 'attention', 'denied': 'attention', 'clarification': 'attention',
               'partial_response': 'partial', 'records_received': 'received', 'acknowledged': 'acknowledged',
               'closed': 'closed'}.get(stage) or
              ('attention' if view['status'] == 'attention' else 'waiting' if receipts else
               'routing' if not case.get('routing_verified') else 'draft'))
    deadline = view['deadline']
    return {'id': case['id'], 'title': case.get('family_label') or case.get('subject') or case['id'],
            'jurisdiction': case.get('target', {}).get('label') or case.get('jurisdiction') or case.get('state_name', ''),
            'status': status, 'label': LABELS[status], 'response_stage': stage,
            'response_review_needed': bool(review_needed), 'unread_count': view['unread_count'],
            'mail_count': view['mail_count'], 'coverage': tracking.get('coverage'),
            'fee_note': tracking.get('fee_note', ''), 'last_activity_at': max([case.get('updated_at', 0), case.get('created_at', 0)] + [m.get('synced_at', 0) for m in linked]),
            'send_confirmed': bool(receipts), 'send_uncertain': uncertain, 'accepted_at': min(receipts) if receipts else None,
            'deadline': {k: deadline.get(k) for k in ('status', 'label', 'due_date', 'kind', 'basis')},
            'revision': case['revision']}


def overview(service, state, workflow='all', campaign_id=None):
    if workflow not in ('all', 'equipment', 'general', 'records'):
        raise ConnectorError('Choose all, equipment, general or records workflow.')
    if campaign_id is not None and (not isinstance(campaign_id, str) or not 1 <= len(campaign_id) <= 150):
        raise ConnectorError('Choose a saved campaign ID.')
    rows = [c for c in contacts.inventory()['counties'] if c['state'] == state]
    cases = [c for c in service.all_cases() if c.get('state') == state]
    if workflow == 'equipment':
        cases = [c for c in cases if c.get('campaign_id') == equipment.ID]
    elif workflow == 'general':
        cases = [c for c in cases if c.get('general_campaign_id')]
    elif workflow == 'records':
        cases = [c for c in cases if not c.get('campaign_id')]
    if campaign_id:
        cases = [c for c in cases if c.get('general_campaign_id', c.get('campaign_id')) == campaign_id]
    groups = {c['id']: [] for c in rows}
    messages = service.mails()
    unmatched, other = [], []
    for case in cases:
        level = case.get('target', {}).get('level', case.get('jurisdiction_level', 'state'))
        summary = request_summary(service, case, messages)
        if level != 'county':
            other.append(summary)
        else:
            county_id = identity(case, rows)
            if county_id:
                groups[county_id].append(summary)
            else:
                unmatched.append(summary)
    result = []
    for county in rows:
        requests = sorted(groups[county['id']], key=lambda r: (PRIORITY.index(r['status']), r['id']))
        statuses = Counter(r['status'] for r in requests)
        status = next((s for s in PRIORITY if statuses[s]), 'none')
        timing = [r['deadline']['status'] for r in requests]
        result.append({**county, 'status': status, 'label': LABELS[status], 'request_count': len(requests),
                       'status_counts': dict(statuses), 'requests': requests,
                       'unread_count': sum(r['unread_count'] for r in requests),
                       'send_confirmed_count': sum(r['send_confirmed'] for r in requests),
                       'deadline_status': 'overdue' if 'overdue' in timing else 'soon' if any(x in ('due_today', 'due_soon') for x in timing) else ''})
    return {'state': state, 'workflow': workflow, 'campaign_id': campaign_id, 'counties': result,
            'status_labels': LABELS, 'counts': {'counties': len(rows), 'with_requests': sum(bool(c['requests']) for c in result),
            'without_requests': sum(not c['requests'] for c in result), 'requests': sum(len(c['requests']) for c in result),
            'unread_replies': sum(c['unread_count'] for c in result), 'by_status': dict(Counter(c['status'] for c in result))},
            'unmatched_county_requests': unmatched, 'other_jurisdiction_requests': other,
            'as_of': time.time(), 'network_accessed': False,
            'caveat': 'Saved local status only; not a fresh inbox check or statewide completeness finding. State and municipal requests never color counties. Unmatched county names need review. Map color is the highest-priority request status, not proof all requested records were received.'}
