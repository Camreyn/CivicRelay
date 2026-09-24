"""MA response reviews and draft-only follow-ups. No mail parsing or network actions.

Reviews are explicit operator assessments, scoped to one linked response. A referral
does not establish receipt by its destination, records completeness, or local coverage.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import uuid

import connector
import deadlines
import equipment
from secure_store import ConnectorError

FIELDS = {'response_message_id', 'response_kind', 'summary', 'categories',
          'referral_level', 'referral_target', 'referral_status', 'referral_note',
          'response_date', 'date_basis', 'follow_up_on'}
ARGUMENTS = {
    'desk_get_ma_follow_up': {'case_id'},
    'desk_save_ma_review': {'case_id', 'revision'} | FIELDS,
    'desk_preview_ma_follow_up': {'case_id', 'revision', 'response_message_id', 'purpose'},
}
READ_ONLY = {'desk_get_ma_follow_up', 'desk_preview_ma_follow_up'}
KINDS = ['internal_referral', 'local_referral', 'no_records', 'partial_response',
         'records_received', 'withheld', 'clarification']
DISPOSITIONS = ['not_addressed', 'pending', 'partial', 'received',
                'agency_reports_not_held', 'withheld', 'not_requested']
BASE = 'https://www.sec.state.ma.us/divisions/'
LAW = 'https://malegislature.gov/Laws/GeneralLaws/PartI/TitleX/Chapter66/Section10'
APPEAL = BASE + 'public-records/public-records-law/appealing-a-denial.htm'
PROFILE = {
    'version': '2026-09-23.1', 'checked_date': '2026-09-23',
    'contacts': [
        {'role': 'designated_filing_custodian', 'office': 'Secretary of the Commonwealth Records Access Officer',
         'email': 'Sec.RAO@sec.state.ma.us', 'scope': 'Records held by the Secretary\u2019s office; not every MA agency or municipality.',
         'source': BASE + 'public-records/prepra/records-access-officer-contact.htm'},
        {'role': 'division_contact_not_separate_rao', 'office': 'Elections Division',
         'email': 'elections@sec.state.ma.us', 'scope': 'Verified division contact; does not replace the designated filing custodian.',
         'source': BASE + 'about-us/contact-us.htm'},
    ],
    'sources': [
        {'label': 'Response contents, custody, production and fees: M.G.L. c. 66, section 10', 'url': LAW},
        {'label': 'Supervisor appeal procedure: 90 days after a response', 'url': APPEAL},
        {'label': 'Official city/town election-office directory (records-holder leads, not verified RAOs)',
         'url': BASE + 'elections/voter-resources/find-my-local-election-office.htm'},
        {'label': 'Official city/town websites and department directories', 'url': BASE + 'cis/contact/town-contact.htm'},
    ],
    'suggested_holders': [
        {'role': 'Elections', 'records': 'Equipment, recorded versions, testing, audits, custody and logs'},
        {'role': 'Procurement / Purchasing', 'records': 'Contracts and purchase orders'},
        {'role': 'Finance / Accounts Payable', 'records': 'Invoices and payments'},
        {'role': 'IT / Information Services', 'records': 'Communications deployment records'},
        {'role': 'Emergency Management', 'records': 'Loan/donation records only if involved'},
    ],
    'municipal_routing': 'Select specific cities/towns and verify each designated RAO and email procedure before creating separate requests. A county is not a substitute for a municipality. Suggested records holders are not verified filing contacts.',
    'limits': 'No automatic classification, mailbox checks, sends, fee acceptance, appeals, local request creation or publication. Reviews do not close cases, mark mail reviewed, satisfy statutory response requirements or change original submission clocks.',
}


def checklist(c):
    if c.get('campaign_id') == equipment.ID:
        return [{'key': k, 'label': label} for k, label in (
            ('equipment', 'Voting equipment inventories and recorded software/firmware versions'),
            ('communications', 'Internet, cellular or satellite contracts, purchase orders and invoices'),
            ('loans', 'Equipment loan, donation and transfer records'),
            ('deployment', 'Existing communications deployment and purpose records'))]
    if c.get('family') == 'electronic' and not c.get('general_campaign_id'):
        rows = [{'key': r['artifactType'], 'label': r['artifactLabel']} for r in c.get('requests', [])]
        if rows and len(rows) <= 12 and len({r['key'] for r in rows}) == len(rows):
            return rows
    return []


def ma_case(service, key, supported=False):
    c = service.case(key)
    if c.get('state') != 'MA':
        raise ConnectorError('Choose a Massachusetts request. Other states do not use this profile.')
    if supported and not checklist(c):
        raise ConnectorError('This helper supports MA electronic starter-pack and equipment requests. Use general workflow tools for other templates.')
    return c


def checked_revision(c, value):
    if type(value) is not int or value != c['revision']:
        raise ConnectorError('Request changed. Reload before reviewing or previewing this response.')


def text(value, limit, blank=False):
    if blank and value == '':
        return ''
    return connector.clean_text(value, limit, multiline=True)


def evidence(service, c, key):
    if not isinstance(key, str) or not key or len(key) > 150:
        return None
    m = service.db.get('mail', key)
    if not m or m.get('folder') != 'INBOX' or m.get('case_id') != c['id'] or m.get('thread_conflict'):
        return None
    return m


def review_valid(service, c, review):
    m = evidence(service, c, review['response_message_id'])
    return bool(m and m.get('body_loaded') and not m.get('body_truncated') and
                m.get('message_id') == review.get('message_identity'))


def profile():
    p = deepcopy(PROFILE)
    p['source_stale'] = (deadlines.utcnow().date() - date.fromisoformat(p['checked_date'])).days > 180
    return p


def case_view(service, c):
    rows = checklist(c)
    reviews = deepcopy(c.get('ma_response_reviews', []))
    valid_ids = set()
    watches = []
    today = deadlines.utcnow().date()
    for r in reviews:
        r['evidence_valid'] = review_valid(service, c, r)
        if r['evidence_valid']:
            valid_ids.add(r['response_message_id'])
        if r.get('response_date'):
            day = date.fromisoformat(r['response_date']) + timedelta(days=90)
            watches.append({'message_id': r['response_message_id'], 'response_date': r['response_date'],
                            'candidate_date': day.isoformat(), 'days_remaining': (day-today).days,
                            'confidence': 'estimate_requires_review', 'evidence_valid': r['evidence_valid'],
                            'basis': '90 calendar days after the operator-recorded response date; no weekend/holiday extension assumed. Verify applicability and filing rules. Follow-ups do not reset this watch.',
                            'source': APPEAL, 'source_checked_date': PROFILE['checked_date']})
    mail = service.mails(c['id'])
    incoming = [m for m in mail if m.get('folder') == 'INBOX']
    pending = [m['id'] for m in incoming if m['id'] not in valid_ids]
    return {'case_id': c['id'], 'revision': c['revision'], 'subject': c['subject'],
            'workflow': 'equipment' if c.get('campaign_id') == equipment.ID else c.get('family', ''),
            'supported': bool(rows), 'checklist': rows, 'reviews': reviews,
            'incoming': [{k: m.get(k) for k in ('id', 'date', 'subject', 'body_loaded', 'body_truncated', 'thread_conflict')} for m in incoming],
            'unreviewed_message_ids': pending, 'appeal_watches': watches,
            'original_submission': deadlines.first_submission(service, c),
            'internal_reminders': [{'message_id': r['response_message_id'], 'date': r['follow_up_on'],
                                    'evidence_valid': r['evidence_valid'], 'legal_deadline': False}
                                   for r in reviews if r.get('follow_up_on')],
            'case_stage_unchanged': c['stage'], 'municipal_coverage_inferred': False}


def overview(service, key=None):
    cases = [ma_case(service, key)] if key is not None else [c for c in service.all_cases() if c.get('state') == 'MA']
    return {'profile': profile(), 'cases': [case_view(service, c) for c in cases],
            'network_accessed': False, 'messages_sent': 0, 'fees_incurred': False}


def save_review(service, args):
    c = ma_case(service, args.get('case_id'), supported=True)
    checked_revision(c, args.get('revision'))
    if not FIELDS <= set(args):
        raise ConnectorError('Provide the complete response review. Read the saved review first; omitted fields are not silently cleared.')
    key = args['response_message_id']
    m = evidence(service, c, key)
    if not m or not m.get('body_loaded') or m.get('body_truncated') or not m.get('message_id'):
        raise ConnectorError('Read a complete incoming message linked to this case without a thread conflict before saving a review.')
    r = {k: args[k] for k in FIELDS}
    if r['response_kind'] not in KINDS:
        raise ConnectorError('Choose a supported response kind.')
    for name, maximum, blank in [('summary', 2500, False), ('referral_target', 250, True),
                                 ('referral_note', 2500, True), ('date_basis', 1500, True)]:
        r[name] = text(r[name], maximum, blank)
    if r['referral_level'] not in ('', 'state', 'municipality', 'unknown') or r['referral_status'] not in ('', 'reported_forwarded', 'suggested_routing', 'receipt_confirmed'):
        raise ConnectorError('Choose a valid referral level and status; municipalities are not counties.')
    is_referral = r['response_kind'] in ('internal_referral', 'local_referral')
    if is_referral or any(r[k] for k in ('referral_level', 'referral_target', 'referral_status', 'referral_note')):
        if not all(r[k] for k in ('referral_level', 'referral_target', 'referral_status', 'referral_note')):
            raise ConnectorError('A referral requires its level, target, status and evidence note. Forwarding is not confirmed receipt.')
    if r['response_kind'] == 'local_referral' and r['referral_level'] != 'municipality':
        raise ConnectorError('Record MA local referrals as cities/towns, not statewide or county coverage.')
    if r['response_kind'] == 'internal_referral' and r['referral_level'] != 'state':
        raise ConnectorError('An internal state referral requires the state level.')
    for name in ('response_date', 'follow_up_on'):
        r[name] = deadlines.date_text(r[name])
    if r['response_date']:
        if not r['date_basis'] or date.fromisoformat(r['response_date']) > deadlines.utcnow().date():
            raise ConnectorError('The response date needs a reviewed basis and cannot be in the future.')
    elif r['date_basis']:
        raise ConnectorError('Supply a response date with its basis, or clear both.')
    expected = {row['key'] for row in checklist(c)}
    categories = r['categories']
    if not isinstance(categories, list) or len(categories) != len(expected):
        raise ConnectorError('Review every checklist category; use not_addressed or not_requested where appropriate.')
    seen = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != {'key', 'status', 'note'} or not isinstance(item['key'], str) or item['key'] not in expected or item['key'] in seen:
            raise ConnectorError('Use each exact category key once; unknown or duplicate categories are not allowed.')
        seen.add(item['key'])
        if item['status'] not in DISPOSITIONS:
            raise ConnectorError('Choose a valid category disposition.')
        item['note'] = text(item['note'], 1500, blank=item['status'] in ('not_addressed', 'pending'))
    old = c.get('ma_response_reviews', [])
    if len(old) >= 100 and not any(x['response_message_id'] == key for x in old):
        raise ConnectorError('This case reached 100 response reviews. Existing evidence was preserved.')
    r.update(message_identity=m['message_id'], reviewed_at=deadlines.utcnow().isoformat(),
             profile_version=PROFILE['version'])
    c['ma_response_reviews'] = [x for x in old if x['response_message_id'] != key] + [r]
    # Save the review and its event together. Do not alter routing, drafts, clocks or stages.
    c['revision'] += 1
    c['updated_at'] = deadlines.utcnow().timestamp()
    event_id = str(uuid.uuid4())
    event = {'id': event_id, 'case_id': c['id'], 'action': 'ma_response_review_saved', 'at': c['updated_at'],
             'details': {'revision': c['revision'], 'review': r}}
    service.db.put_many([('case', c['id'], c), ('event', event_id, event)])
    return {'case': service.view_case(c), 'ma_follow_up': overview(service, c['id']),
            'messages_sent': 0, 'fees_incurred': False, 'network_accessed': False}


def preview(service, args):
    c = ma_case(service, args.get('case_id'), supported=True)
    checked_revision(c, args.get('revision'))
    key = args.get('response_message_id')
    r = next((r for r in c.get('ma_response_reviews', []) if r['response_message_id'] == key), None)
    if not r or not review_valid(service, c, r):
        raise ConnectorError('Save a review backed by the linked incoming message before previewing a follow-up.')
    # A newer response may make an old follow-up inappropriate. Require a fresh review.
    if any(m.get('synced_at', 0) > date_time(r['reviewed_at']) for m in service.mails(c['id']) if m.get('folder') == 'INBOX'):
        raise ConnectorError('New mail arrived after this review. Read it and review this follow-up again.')
    purpose = args.get('purpose')
    if purpose not in ('confirm_referral', 'clarify_categories'):
        raise ConnectorError('Choose confirm_referral or clarify_categories.')
    if purpose == 'confirm_referral' and r['response_kind'] != 'internal_referral':
        raise ConnectorError('Confirm a handoff only for an internal referral. Local routing suggestions are not forwarded requests.')
    reference = ', '.join(c.get('request_ids', [])) or c['id']
    paragraphs = ['To the Records Access Officer:',
                  f'I am following up on our existing records request, reference(s): {reference}. This is a clarification of that request, not a replacement or an expanded request.']
    if purpose == 'confirm_referral':
        paragraphs.append('Thank you for the referral. Please confirm whether the receiving division has received the complete original request, the office or contact handling it, any tracking reference, and the expected date for a substantive response. Please clarify whether the statement about no responsive records applies only to the responding office or also to the receiving division.')
    else:
        paragraphs.append('Please clarify whether your response addresses each category of the original request, including responsive records already retained by your agency. We are not asking your office to obtain records held only by other agencies or municipalities or to conduct a new collection.')
    labels = {row['key']: row['label'] for row in checklist(c)}
    unresolved = [labels[x['key']] for x in r['categories'] if x['status'] not in ('received', 'not_requested')]
    if unresolved:
        paragraphs.append('For these categories, within the scope and dates of the original request:\n' + '\n'.join('- ' + x for x in unresolved))
        paragraphs.append('Please identify records you will provide, records withheld and the applicable legal basis, and categories not held by your agency. If another custodian is known, please identify that agency or municipality and its designated records contact. Please provide reasonably segregable/redacted copies where appropriate, without creating a new report or analysis.')
    paragraphs.extend(['The original exclusions remain: no credentials, sensitive network details or personal voter information. No fees are authorized at any amount. Please provide an itemized estimate and wait for express written approval before any chargeable work.',
                       'This is neutral evidence gathering, not an allegation of election interference. Please retain the original request date and reference in your response.', 'Thank you.'])
    subject = c['subject'] if c['subject'].lower().startswith('re:') else 'Re: ' + c['subject']
    return {'case_id': c['id'], 'revision': c['revision'], 'reply_message_id': key,
            'recipient': c.get('recipient', ''), 'routing_verified': False,
            'routing_note': 'Saved recipient is a lead. Reverify the designated custodian for this case before preparing a send. State-office contacts do not apply to a municipal case.',
            'subject': subject, 'body': '\n\n'.join(paragraphs), 'unresolved_categories': unresolved,
            'original_submission': deadlines.first_submission(service, c),
            'draft_created': False, 'messages_sent': 0, 'network_accessed': False,
            'next_steps': ['Review the exact text and current official recipient.',
                           'Save correspondence with desk_save_case at the current revision, preserving other fields.',
                           'Use desk_prepare_email with this reply_message_id for an immutable threaded draft.',
                           'Sending requires separate user authority and the existing exact-digest send action.']}


def date_time(value):
    from datetime import datetime
    return datetime.fromisoformat(value).timestamp()


def dispatch(service, name, args):
    if name == 'desk_get_ma_follow_up':
        return overview(service, args.get('case_id'))
    if name == 'desk_save_ma_review':
        return save_review(service, args)
    if name == 'desk_preview_ma_follow_up':
        return preview(service, args)
    raise ConnectorError('Unknown MA operation.')
