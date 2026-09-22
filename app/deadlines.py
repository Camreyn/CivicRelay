"""Read-only, source-linked planning clocks; never infer receipt or send mail.

Rules are reviewed public data. Mail bodies/subjects are never parsed as rules.
Derived clocks are estimates. Case-specific dates require explicit evidence.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import json
import re
from urllib.parse import urlsplit

from secure_store import ConnectorError
import connector

ZONES = {'Eastern': -5, 'Central': -6, 'Mountain': -7, 'Pacific': -8,
         'Alaska': -9, 'Hawaii': -10, 'Arizona': -7, 'UTC': 0}
FIELDS = {'filing_status', 'received_date', 'receipt_basis', 'receipt_message_id',
          'initial_response', 'response_message_id', 'response_basis', 'time_zone',
          'excluded_dates', 'next_date', 'next_kind', 'next_source', 'next_basis',
          'next_checked_date', 'next_message_id', 'next_completed'}
ARGUMENTS = {'desk_get_deadlines': {'case_id'},
             'desk_save_deadline_tracking': {'case_id', 'revision'} | FIELDS}
READ_ONLY = {'desk_get_deadlines'}
DEFAULTS = dict(filing_status='unverified', received_date='', receipt_basis='', receipt_message_id='',
                initial_response='unreviewed', response_message_id='', response_basis='', time_zone='',
                excluded_dates=[], next_date='', next_kind='', next_source='', next_basis='',
                next_checked_date='', next_message_id='', next_completed=False, reviewed_message_ids=[])


@lru_cache(maxsize=1)
def registry():
    return json.loads(Path(__file__).with_name('deadline-rules.json').read_text(encoding='utf-8'))


def utcnow():
    return datetime.now(timezone.utc)


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday-first.weekday()) % 7 + 7*(n-1))


def local_date(instant, zone):
    """Post-2007 US civil-time planning offsets, without an OS tzdata dependency."""
    if isinstance(instant, str):
        instant = datetime.fromisoformat(instant.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('A send timestamp must include its UTC offset.')
    instant = instant.astimezone(timezone.utc)
    offset = ZONES[zone]
    if zone not in ('UTC', 'Hawaii', 'Arizona') and instant.year >= 2007:
        start = datetime.combine(nth_weekday(instant.year, 3, 6, 2), datetime.min.time(), timezone.utc) + timedelta(hours=2-offset)
        end = datetime.combine(nth_weekday(instant.year, 11, 6, 1), datetime.min.time(), timezone.utc) + timedelta(hours=1-offset)
        if start <= instant < end:
            offset += 1
    return (instant + timedelta(hours=offset)).date()


@lru_cache(maxsize=32)
def federal_holidays(year):
    result = set()
    # Adjacent year's observed New Year's Day can fall on December 31.
    for y in (year-1, year, year+1):
        fixed = [(1, 1), (7, 4), (11, 11), (12, 25)] + ([(6, 19)] if y >= 2021 else [])
        for month, day in fixed:
            d = date(y, month, day)
            result.add(d + timedelta(days=-1 if d.weekday() == 5 else 1 if d.weekday() == 6 else 0))
        result.update([nth_weekday(y, 1, 0, 3), nth_weekday(y, 2, 0, 3),
                       date(y, 5, 31)-timedelta(days=date(y, 5, 31).weekday()),
                       nth_weekday(y, 9, 0, 1), nth_weekday(y, 10, 0, 2), nth_weekday(y, 11, 3, 4)])
    return frozenset(d for d in result if d.year == year)


def business_day(day, exclusions=()):
    return day.weekday() < 5 and day not in federal_holidays(day.year) and day.isoformat() not in exclusions


def add_business_days(day, count, exclusions=()):
    while count:
        day += timedelta(days=1)
        if business_day(day, exclusions):
            count -= 1
    return day


def open_day(day, exclusions=()):
    while not business_day(day, exclusions):
        day += timedelta(days=1)
    return day


def date_text(value):
    if value == '':
        return ''
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ConnectorError('Use a real YYYY-MM-DD deadline date.')
    try:
        parsed = date.fromisoformat(value)
        if not 2007 <= parsed.year <= 2100:
            raise ValueError()
    except ValueError:
        raise ConnectorError('Use a real date between 2007 and 2100.') from None
    return value


def public_url(value):
    if not value:
        return ''
    value = connector.clean_text(value, 1500)
    try:
        p = urlsplit(value)
        valid = p.scheme == 'https' and p.hostname and not p.username and not p.password and not any(c.isspace() or ord(c) < 32 for c in value)
    except ValueError:
        valid = False
    if not valid:
        raise ConnectorError('Use an HTTPS official-source URL without credentials.')
    return value


def linked_incoming(service, case, key):
    if not key:
        return False
    m = service.db.get('mail', key)
    return bool(m and m.get('folder') == 'INBOX' and m.get('case_id') == case['id'] and not m.get('thread_conflict'))


def save_tracking(service, args):
    c = service.case(args.get('case_id'))
    if type(args.get('revision')) is not int or args['revision'] != c['revision']:
        raise ConnectorError('Request changed. Reload before saving deadline evidence.')
    t = {**DEFAULTS, **c.get('deadline_tracking', {}), **{k: v for k, v in args.items() if k in FIELDS}}
    for key in ('receipt_basis', 'response_basis', 'next_basis'):
        t[key] = connector.clean_text(t[key], 2500, multiline=True) if t[key] else ''
    for key in ('receipt_message_id', 'response_message_id', 'next_message_id'):
        t[key] = connector.clean_text(t[key], 150) if t[key] else ''
        if t[key] and not linked_incoming(service, c, t[key]):
            raise ConnectorError('Deadline evidence must be an incoming message linked to this request without a thread conflict.')
    if t['filing_status'] not in ('unverified', 'formal', 'inquiry'):
        raise ConnectorError('Choose unverified, formal, or inquiry filing status.')
    if t['filing_status'] == 'formal' and not c.get('routing_verified'):
        raise ConnectorError('Verify official custodian routing before recording a formal filing.')
    if t['initial_response'] not in ('unreviewed', 'satisfied'):
        raise ConnectorError('Choose unreviewed or satisfied for the initial response.')
    if not isinstance(t['time_zone'], str) or t['time_zone'] and t['time_zone'] not in ZONES:
        raise ConnectorError('Choose a supported planning time zone.')
    for key in ('received_date', 'next_date', 'next_checked_date'):
        t[key] = date_text(t[key])
    today = utcnow().date()
    if any(t[k] and date.fromisoformat(t[k]) > today for k in ('received_date', 'next_checked_date')):
        raise ConnectorError('Receipt and source-review dates cannot be in the future.')
    if t['received_date'] and not t['receipt_basis']:
        raise ConnectorError('A statutory receipt/start date requires evidence and a calculation basis.')
    if t['initial_response'] == 'satisfied' and (not t['response_message_id'] or not t['response_basis']):
        raise ConnectorError('Satisfying the initial-response checkpoint requires linked mail and a review basis. An acknowledgment alone may not suffice.')
    if not isinstance(t['excluded_dates'], list) or len(t['excluded_dates']) > 80 or any(not d for d in t['excluded_dates']):
        raise ConnectorError('Provide at most 80 nonworking dates.')
    t['excluded_dates'] = sorted(set(date_text(d) for d in t['excluded_dates']))
    if t['next_kind'] not in ('', 'agency_commitment', 'extension', 'appeal', 'follow_up') or type(t['next_completed']) is not bool:
        raise ConnectorError('Invalid checkpoint kind or completion state.')
    t['next_source'] = public_url(t['next_source'])
    if t['next_date']:
        if not t['next_kind'] or not t['next_basis']:
            raise ConnectorError('A checkpoint requires its kind and basis.')
        if t['next_kind'] != 'follow_up' and (not t['next_source'] or not t['next_checked_date']):
            raise ConnectorError('An agency, extension or appeal date requires its official source and checked date.')
        if t['next_kind'] in ('agency_commitment', 'extension') and not t['next_message_id']:
            raise ConnectorError('An agency commitment or extension requires the actual linked notice.')
        if t['next_kind'] == 'extension' and t['initial_response'] != 'satisfied':
            raise ConnectorError('Review whether the extension satisfies the initial-response requirement before recording it.')
    elif t['next_kind'] or t['next_completed']:
        raise ConnectorError('A checkpoint date is required, or clear its kind and completion state.')
    if t['initial_response'] == 'satisfied' and any(k in args for k in ('initial_response', 'response_message_id', 'response_basis')):
        t['reviewed_message_ids'] = [m['id'] for m in service.mails(c['id']) if m.get('folder') == 'INBOX' and not m.get('thread_conflict')]
    c['deadline_tracking'] = t
    service.save(c)
    service.db.event(c['id'], 'deadline_evidence_saved', {'revision': c['revision'], 'filing_status': t['filing_status'], 'tracking': t, 'rule_version': registry()['version']})
    return {'case': service.view_case(c), 'messages_sent': 0, 'fees_incurred': False, 'network_accessed': False}


def first_submission(service, case):
    """Use the original accepted request, never last_sent_at or a follow-up draft."""
    from equipment import valid_receipt
    candidates, uncertain = [], False
    for key in case.get('drafts', []):
        try:
            d = service.mail_store.get_draft(key)
        except ConnectorError:
            uncertain = True
            continue
        if valid_receipt(d) and not d.get('in_reply_to'):
            candidates.append((datetime.fromisoformat(d['receipt']['accepted_at']), key))
        elif d.get('state') not in ('draft', 'accepted') or d.get('state') == 'accepted' and not valid_receipt(d):
            uncertain = True
    if candidates:
        when, key = min(candidates)
        return {'at': when.isoformat(), 'draft_id': key, 'kind': 'accepted', 'uncertain': uncertain}
    if case.get('portal_receipt'):
        return {'date': case['portal_receipt']['date'], 'kind': 'portal', 'uncertain': uncertain}
    return {'kind': 'uncertain' if uncertain else 'not_sent', 'uncertain': uncertain}


def state_rule(case):
    level = case.get('target', {}).get('level', case.get('jurisdiction_level', 'state'))
    code = 'US' if level == 'federal' else case.get('state', '')
    rule = registry()['rules'].get(code)
    if rule and level not in rule.get('levels', ['state', 'county', 'municipality', 'federal']):
        return code, None
    return code, rule


def evaluate(service, case, messages=None, now=None):
    reg = registry()
    t = {**DEFAULTS, **case.get('deadline_tracking', {})}
    code, rule = state_rule(case)
    zone = t['time_zone'] or (rule or {}).get('zone', 'UTC')
    today = local_date(now or utcnow(), zone)
    mails = [m for m in (messages if messages is not None else service.mails(case['id'])) if m.get('case_id') == case['id']]
    inbox = [m for m in mails if m.get('folder') == 'INBOX' and not m.get('thread_conflict')]
    submission = first_submission(service, case)
    warnings = []
    result = {'case_id': case['id'], 'state': case.get('state', ''), 'jurisdiction': case.get('target', {}).get('label') or case.get('state_name', code),
              'request': case.get('family_label', case.get('subject', 'Request')), 'revision': case['revision'],
              'as_of': today.isoformat(), 'time_zone': zone, 'rule_code': code, 'rule': rule,
              'rule_version': reg['version'], 'source_checked_date': reg['checked_date'],
              'source_review_due': (date.fromisoformat(reg['checked_date'])+timedelta(days=reg['review_after_days'])).isoformat(),
              'calendar_note': reg['calendar_note'], 'calendar_source': reg['calendar_source'],
              'submission': submission, 'filing_status': t['filing_status'], 'checks': [], 'warnings': warnings,
              'status': 'not_sent', 'label': 'Not sent', 'due_date': '', 'days_remaining': None, 'attention': False,
              'legal_violation_determined': False, 'network_accessed': False}
    stale = today > date.fromisoformat(result['source_review_due'])
    if stale:
        warnings.append('The bundled legal source review is older than 180 days. Recheck current law before relying on a date.')
    if submission['uncertain']:
        warnings.append('A send outcome or draft record needs reconciliation. No new send or retry is implied.')
    if t['filing_status'] != 'formal':
        warnings.append('Formal filing/custodian compliance has not been established.' if t['filing_status'] == 'unverified' else 'Information inquiry: no statutory response clock is asserted.')
    if rule:
        warnings.append(reg['calendar_note'])
        warnings.append('Planning time zone uses current post-2007 US DST rules. Verify the custodian’s location and after-hours receipt policy.')
    else:
        warnings.append('No reviewed automatic rule for this jurisdiction/scope. Record a sourced date or an internal reminder; no default legal clock is invented.')

    evidence_invalid = any(t[k] and not linked_incoming(service, case, t[k]) for k in ('receipt_message_id', 'response_message_id', 'next_message_id'))
    if evidence_invalid:
        warnings.append('Saved timing evidence was unassigned or has a thread conflict. Re-review the deadline evidence.')
    received = None
    if t['received_date'] and not (t['receipt_message_id'] and not linked_incoming(service, case, t['receipt_message_id'])):
        received = date.fromisoformat(t['received_date'])
        result['receipt_basis'] = t['receipt_basis']
    elif submission.get('at'):
        received = local_date(submission['at'], zone)
        if rule and rule['receipt_rule'] == 'email_next':
            received = add_business_days(received, 1, t['excluded_dates'])
        elif rule and rule['receipt_rule'] == 'next_open':
            received = open_day(received, t['excluded_dates'])
        result['receipt_basis'] = 'Estimated from original Bridge acceptance, not proof of delivery or agency receipt.'
    elif submission.get('date'):
        warnings.append('Portal submission is recorded. Enter its reviewed statutory receipt/start date; emailed-request timing is not assumed.')
    result['receipt_date'] = received.isoformat() if received else ''
    response_satisfied = t['initial_response'] == 'satisfied' and not evidence_invalid
    new_reply = response_satisfied and any(m['id'] not in t['reviewed_message_ids'] for m in inbox)
    if new_reply:
        warnings.append('New linked mail arrived after timing evidence was reviewed. Check whether it changes the next checkpoint.')
    closed = case.get('stage') == 'closed' or case.get('tracking', {}).get('response_stage') == 'closed'

    def add_check(kind, due, label, confidence, basis, source='', resolved=False, review=False):
        diff = (due-today).days
        status = 'resolved' if resolved else 'overdue' if diff < 0 else 'due_today' if diff == 0 else 'due_soon' if due <= add_business_days(today, 2, t['excluded_dates']) else 'upcoming'
        result['checks'].append({'kind': kind, 'date': due.isoformat(), 'label': label, 'confidence': confidence,
                                 'basis': basis, 'source': source, 'status': status, 'days_remaining': diff,
                                 'review_required': review, 'resolved': resolved})

    sent = submission['kind'] in ('accepted', 'portal')
    if sent and received and rule and rule['days'] is not None and t['filing_status'] != 'inquiry' and not (rule.get('requires_formal') and t['filing_status'] != 'formal'):
        due = add_business_days(received, rule['days'], t['excluded_dates']) if rule['unit'] == 'business' else received+timedelta(days=rule['days'])
        add_check('initial_response', due, rule['label'], 'estimate',
                  f"{rule['days']} {rule['unit']} days after {received.isoformat()}; receipt day excluded. {result['receipt_basis']}",
                  rule['url'], resolved=response_satisfied or closed, review=bool(inbox) and not response_satisfied)
    elif sent and not closed and not response_satisfied:
        result.update(status='no_fixed_clock' if rule and rule['days'] is None else 'needs_basis',
                      label='No fixed statutory day count' if rule and rule['days'] is None else 'Timing basis needs review')

    # A separately reviewed next event never silently rewrites the original clock.
    if t['next_date']:
        manual_kind = t['next_kind']
        add_check(manual_kind, date.fromisoformat(t['next_date']),
                  {'agency_commitment': 'Agency-promised response', 'extension': 'Reviewed extension', 'appeal': 'Recorded appeal deadline', 'follow_up': 'Internal follow-up reminder'}[manual_kind],
                  'reminder' if manual_kind == 'follow_up' else 'operator_recorded', t['next_basis'], t['next_source'],
                  resolved=t['next_completed'], review=evidence_invalid)
    old = case.get('tracking', {})
    if old.get('deadline_date') and old.get('deadline_source') and old.get('deadline_basis') and old.get('deadline_checked_date'):
        try:
            add_check('legacy_'+old.get('deadline_kind', 'response'), date.fromisoformat(old['deadline_date']),
                      'Previously recorded '+old.get('deadline_kind', 'response')+' deadline', 'operator_recorded',
                      old['deadline_basis'], old['deadline_source'], resolved=closed)
        except ValueError:
            warnings.append('A previously recorded deadline is invalid; review the saved progress fields.')
    active = [x for x in result['checks'] if not x['resolved']]
    if active:
        # Review-needed replies are not silently declared legally sufficient.
        priority = {'overdue': 0, 'due_today': 1, 'due_soon': 2, 'upcoming': 3}
        chosen = min(active, key=lambda x: (x['review_required'], priority[x['status']], x['date']))
        state = 'reply_review' if chosen['review_required'] else chosen['status']
        label = {'reply_review': 'Reply / timing evidence needs review', 'overdue': 'Past recorded date',
                 'due_today': 'Due today', 'due_soon': 'Due soon', 'upcoming': 'Upcoming'}[state]
        if chosen['confidence'] == 'estimate' and state != 'reply_review':
            label = {'overdue': 'Potentially overdue', 'due_today': 'Estimated due today', 'due_soon': 'Estimated due soon', 'upcoming': 'Estimated upcoming'}[state]
        if chosen['confidence'] == 'reminder':
            label = 'Follow-up reminder'+(' due' if chosen['status'] in ('overdue', 'due_today') else '')
        result.update(status=state, label=label, due_date=chosen['date'], days_remaining=chosen['days_remaining'],
                      attention=state in ('overdue', 'due_today', 'due_soon', 'reply_review'))
    elif closed or response_satisfied:
        result.update(status='closed' if closed else 'response_recorded', label='Closed locally' if closed else 'Initial response reviewed')
    elif inbox:
        result.update(status='reply_review', label='Reply needs timing review', attention=True)
    elif not sent:
        result.update(status='send_uncertain' if submission['uncertain'] else 'not_sent', label='Send needs reconciliation' if submission['uncertain'] else 'Not sent', attention=submission['uncertain'])
    if (new_reply or evidence_invalid) and not closed:
        result.update(status='reply_review', label='Reply / timing evidence needs review', attention=True)
    return result


def overview(service, case_id=None):
    if case_id is not None:
        if not isinstance(case_id, str) or not case_id:
            raise ConnectorError('Choose a known request ID or omit case_id for all requests.')
        cases = [service.case(case_id)]
    else:
        cases = service.all_cases()
    mails = service.mails()
    now = utcnow()
    rows = [evaluate(service, c, mails, now) for c in cases]
    sync = next((s for s in service.db.all('sync') if s.get('folder') == 'INBOX'), None)
    last = sync.get('at') if sync else None
    return {'cases': rows, 'rules': registry(), 'checked_at': now.isoformat(),
            'mail_last_synced_at': last, 'mail_stale': last is None or now.timestamp()-last > 86400,
            'mail_sync_incomplete': bool(sync and sync.get('more')),
            'unassigned_incoming': sum(1 for m in mails if m.get('folder') == 'INBOX' and (not m.get('case_id') or m.get('thread_conflict'))),
            'counts': {k: sum(r['status'] == k for r in rows) for k in ('overdue', 'due_today', 'due_soon', 'reply_review', 'needs_basis', 'not_sent')},
            'automatic_mail_polling': False, 'automatic_sends': False, 'network_accessed': False,
            'notice': 'Clocks refresh locally from saved receipts and reviewed evidence. Refresh the mailbox separately. Estimates and reminders are not findings of a legal violation; appeal dates require case-specific review.'}
