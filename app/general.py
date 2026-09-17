"""Generic local workspace/campaign operations. They never send, publish, or incur fees."""
from __future__ import annotations

from datetime import date
import copy
import hashlib
import time
import uuid

import connector
import equipment
from intake import safe_url
from secure_store import ConnectorError, canonical
import templates

WORKSPACE_ID = 'default'
LEVELS = ('federal', 'state', 'county', 'municipality', 'other')
RESPONSE_STAGES = ('none', 'acknowledged', 'partial_response', 'records_received', 'fee_notice', 'clarification', 'denied', 'closed')
COVERAGE = ('not_assessed', 'partial', 'received', 'unavailable', 'not_applicable')


def text(value, limit=4000, blank=False):
    if blank and value == '': return ''
    return connector.clean_text(value, limit, multiline=True)


def date_text(value, label, blank=True):
    if blank and value is None:
        value = ''
    value = text(value, 10, blank)
    if value:
        try:
            if date.fromisoformat(value).isoformat() != value: raise ValueError()
        except ValueError: raise ConnectorError(f'{label} must be an exact YYYY-MM-DD date.') from None
    return value


def legacy_storage(service):
    # A deliberately narrow compatibility signal. Never open connector settings or inspect a live mailbox.
    summary = connector.account_summary(service.mail_store)
    # Equipment cases are a separate first-party workspace and carry
    # ``campaign_id`` without ``general_campaign_id``.  Only an untyped case
    # is evidence of the pre-generic legacy starter-pack storage shape.
    legacy_case = any(not c.get('general_campaign_id') and not c.get('campaign_id')
                      for c in service.db.all('case'))
    return bool(summary.get('legacy_storage') or summary.get('legacy_settings') or legacy_case)


def default_workspace(service):
    return {'id': WORKSPACE_ID, 'revision': 0, 'name': '', 'organization': '', 'signature': '',
            'requester_name': '', 'requester_address': '', 'requester_phone': '',
            'starter_pack': 'civicresultmaps' if legacy_storage(service) else 'blank',
            'created_at': time.time()}


def workspace(service):
    return service.db.get('workspace', WORKSPACE_ID) or default_workspace(service)


def workspace_view(value):
    # Same-user local tooling can edit these encrypted values, but they are never part of templates/exports.
    return {key: value.get(key, '') for key in ('id', 'revision', 'name', 'organization', 'signature',
        'requester_name', 'requester_address', 'requester_phone', 'starter_pack')} | {
        'requester_configured': bool(value.get('requester_name') or value.get('requester_address') or value.get('requester_phone')),
        'legacy_storage': bool(value.get('legacy_storage', False))}


def get_workspace(service):
    row = workspace(service)
    row['legacy_storage'] = legacy_storage(service)
    account = connector.account_summary(service.mail_store)
    return {'workspace': workspace_view(row) | {'requester_email': account.get('email')},
            'account': {key: account.get(key) for key in ('configured','email','display_name','profile_id','legacy_storage')}}


def save_workspace(service, args):
    row = workspace(service)
    if type(args.get('revision')) is not int or args['revision'] != row['revision']:
        raise ConnectorError('Workspace changed in another window. Reload before saving.')
    # Omitted private fields preserve their encrypted values. Explicit empty strings intentionally clear them.
    for key, limit in (('name', 160), ('organization', 300), ('signature', 4000),
                       ('requester_name', 300), ('requester_address', 1500), ('requester_phone', 80)):
        if key in args: row[key] = text(args[key], limit, True)
    if 'starter_pack' in args:
        if args['starter_pack'] not in ('blank', 'civicresultmaps'): raise ConnectorError('Starter pack must be blank or civicresultmaps.')
        row['starter_pack'] = args['starter_pack']
    row['revision'] += 1; row['updated_at'] = time.time(); row['legacy_storage'] = legacy_storage(service)
    service.db.put('workspace', WORKSPACE_ID, row)
    service.db.event(WORKSPACE_ID, 'workspace_saved', {'revision': row['revision'], 'private_fields_configured': bool(row['requester_name'] or row['requester_address'] or row['requester_phone'])})
    return {'workspace': workspace_view(row)}


def _target(service, value):
    if not isinstance(value, dict) or set(value) - {'id', 'label', 'level', 'state'} or any(k not in value for k in ('id', 'label', 'level')):
        raise ConnectorError('Each campaign target needs id, label, level and optional state.')
    target_id = text(value['id'], 80)
    if value['level'] not in LEVELS: raise ConnectorError('Campaign target level is invalid.')
    state = text(value.get('state', ''), 2, True).upper()
    if state and state not in {x['code'] for x in service.catalog['states']}: raise ConnectorError('Campaign target state must be a supported state or DC code.')
    return {'id': target_id, 'label': text(value['label'], 160), 'level': value['level'], **({'state': state} if state else {})}


def campaign(service, campaign_id):
    found = service.db.get('campaign', campaign_id)
    if not found or found.get('kind') != 'generic_campaign': raise ConnectorError('Campaign not found.')
    return found


def _derived_request_stage(service, case):
    """Derive send state from the latest immutable draft receipt for reads.

    Queue reads must not mutate encrypted case revisions.  The existing
    equipment receipt validator is shared so an accepted transport state is
    only trusted when its timestamp and Message-ID are valid.
    """
    stage = case.get('stage', 'draft')
    drafts = case.get('drafts') or []
    if not drafts:
        return stage
    try:
        draft = service.mail_store.get_draft(drafts[-1])
    except ConnectorError:
        return 'attention'
    if equipment.valid_receipt(draft):
        # Once reconciliation has recorded this receipt, the ordinary case
        # stage may reflect a handled/closed workflow. An accepted receipt
        # that has not been reconciled yet is still surfaced as waiting.
        return stage if case.get('latest_send_state') == draft.get('state') else 'waiting'
    if draft.get('state') != 'draft':
        return 'attention'
    return stage


def list_campaigns(service):
    rows = [x for x in service.db.all('campaign') if x.get('kind') == 'generic_campaign']
    cases = [x for x in service.db.all('case') if x.get('general_campaign_id')]
    result=[]
    for row in rows:
        item=copy.deepcopy(row); tracked=[x for x in cases if x['general_campaign_id']==row['id']]
        item['target_progress']=[{'target_id': target['id'], 'request_count': sum(x['target']['id']==target['id'] for x in tracked),
                                  'response_stages': sorted({x.get('tracking',{}).get('response_stage','none') for x in tracked if x['target']['id']==target['id']}),
                                  'requests':[{'case_id':x['id'],'revision':x['revision'],'stage':_derived_request_stage(service, x),
                                               'response_stage':x.get('tracking',{}).get('response_stage','none')} for x in tracked if x['target']['id']==target['id']]}
                                 for target in row['targets']]
        item['remaining_targets']=sum(not x['request_count'] for x in item['target_progress'])
        result.append(item)
    return {'campaigns': sorted(result, key=lambda x: (x['name'].casefold(), x['id']))}


def save_campaign(service, args):
    template_id = args.get('template_id')
    template = templates.get(service, template_id)
    if template['versions'][-1]['definition'].get('archived'): raise ConnectorError('Choose an active template for a campaign.')
    key = args.get('campaign_id')
    current = campaign(service, key) if key else None
    if current and (type(args.get('revision')) is not int or args['revision'] != current['revision']):
        raise ConnectorError('Campaign changed in another window. Reload before saving.')
    raw_targets = args.get('targets')
    if not isinstance(raw_targets, list) or not 1 <= len(raw_targets) <= 500: raise ConnectorError('A campaign needs one to 500 targets.')
    targets = [_target(service, x) for x in raw_targets]
    if len({x['id'] for x in targets}) != len(targets): raise ConnectorError('Campaign target IDs must be unique.')
    start = date_text(args.get('date_start'), 'Campaign start date')
    end = date_text(args.get('date_end'), 'Campaign end date')
    if start and end and end < start: raise ConnectorError('Campaign end date cannot precede its start date.')
    if current:
        active_targets={x['target']['id']:x['target'] for x in service.db.all('case') if x.get('general_campaign_id')==current['id']}
        removed=set(active_targets)-{x['id'] for x in targets}
        if removed: raise ConnectorError('Campaign targets with saved requests cannot be removed.')
        changed={x['id'] for x in targets if x['id'] in active_targets and x != active_targets[x['id']]}
        if changed: raise ConnectorError('Campaign targets with saved requests cannot be retargeted.')
        row = copy.deepcopy(current); created = False
    else:
        row = {'id': 'campaign-' + uuid.uuid4().hex, 'kind': 'generic_campaign', 'revision': 0, 'created_at': time.time()}; created = True
    row.update(name=text(args.get('name'), 160), description=text(args.get('description'), 4000, True), template_id=template_id,
               date_start=start, date_end=end, targets=targets, template_version=template['versions'][-1]['version'],
               template_hash=template['versions'][-1]['hash'])
    row['revision'] += 1; row['updated_at'] = time.time(); service.db.put('campaign', row['id'], row)
    service.db.event(row['id'], 'campaign_saved', {'revision': row['revision'], 'targets': len(targets)})
    return {'campaign': row, 'created': created}


def _profile_values(service):
    row = workspace(service)
    account=connector.account_summary(service.mail_store)
    return {'organization':row.get('organization',''),'signature':row.get('signature',''),'requester_email':account.get('email') or ''}


def render_values(service, definition, values, builtins=None):
    if not isinstance(values, dict): raise ConnectorError('Request values must be an object.')
    profile=_profile_values(service); declared={x['id']:x for x in definition['fields']}; private=workspace(service)
    for key in ('requester_name','requester_address','requester_phone'):
        if declared.get(key,{}).get('required') is True: profile[key]=private.get(key,'')
    return {**profile, **(builtins or {}), **values}


def create_request(service, args):
    row = campaign(service, args.get('campaign_id'))
    target = next((x for x in row['targets'] if x['id'] == args.get('target_id')), None)
    if not target: raise ConnectorError('Campaign target not found.')
    template_id = args.get('template_id') or row['template_id']
    record = templates.get(service, template_id)
    snapshot = copy.deepcopy(record['versions'][-1])
    # A caller may choose a different active template without changing the campaign itself.
    if snapshot['definition'].get('archived'): raise ConnectorError('Cannot create a request from an archived template.')
    values = args.get('values')
    if not isinstance(values, dict): raise ConnectorError('Request values must be an object.')
    builtins={'agency':'','jurisdiction':target['label'],'state':target.get('state',''),'date_start':row['date_start'],'date_end':row['date_end']}
    agency = args.get('agency')
    # The shared/native contract accepts an agency name only.  Keep accepting
    # the historical ``{'name': ...}`` shape used by older local callers, but
    # reject recipient/routing fields so request creation cannot shortcut the
    # separate verified-routing step.
    if isinstance(agency, dict):
        if set(agency) != {'name'}: raise ConnectorError('Agency must be a name; recipient and routing evidence are saved only during routing review.')
        agency = agency['name']
    agency = {'name': text(agency, 200), 'recipient': '', 'routing_evidence': ''}
    rendered = templates.render(snapshot['definition'], render_values(service, snapshot['definition'], values, {**builtins, 'agency': agency['name']}))
    fingerprint=hashlib.sha256(canonical({'campaign_id':row['id'],'target':target,
        'template_id':template_id,'template_hash':snapshot['hash'],
        'date_start':row['date_start'],'date_end':row['date_end'],
        'agency':agency,'values':values,'rendered':rendered})).hexdigest()
    existing=next((x for x in service.db.all('case') if x.get('general_fingerprint')==fingerprint),None)
    if existing: return {'case':service.view_case(existing),'created':False,'already_created':True,'messages_sent':0,'fees_incurred':False}
    key = 'request-' + uuid.uuid4().hex
    base = {'id': 'generic:' + template_id + ':' + snapshot['hash'][:16], 'state': target.get('state', ''),
            'state_name': target.get('state', ''), 'family': 'generic', 'family_label': snapshot['definition']['title'] + ' / ' + target['label'],
            'subject': rendered['subject'], 'body': rendered['body'], 'recipient': agency['recipient'], 'requests': [], 'request_ids': []}
    case = {**base, 'base': copy.deepcopy(base), 'catalog_sha256': service.catalog['sha256'], 'id': key, 'revision': 0,
            'created_at': time.time(), 'updated_at': time.time(), 'general_campaign_id': row['id'],
            'campaign_id': row['id'], 'target': target, 'agency': agency, 'template_id': template_id, 'general_fingerprint':fingerprint,
            'template_snapshot': snapshot, 'rendered': rendered, 'entered_values': copy.deepcopy(values), 'stage': 'draft',
            'campaign_scope': {'campaign_id': row['id'], 'target': copy.deepcopy(target),
                               'date_start': row['date_start'], 'date_end': row['date_end']},
            'tracking': {'response_stage': 'none', 'coverage': 'not_assessed'}, 'drafts': [], 'issues': [],
            'routing_verified': False, 'routing_evidence': '', 'note': ''}
    service.db.put('case', key, case); service.db.event(key, 'generic_request_created', {'campaign_id': row['id'], 'target_id': target['id'], 'template_hash': snapshot['hash']})
    return {'case': service.view_case(case), 'created': True, 'messages_sent': 0, 'fees_incurred': False}


def save_request_progress(service, args):
    case = service.case(args.get('case_id'))
    if not case.get('general_campaign_id'): raise ConnectorError('Select a generic campaign request.')
    if type(args.get('revision')) is not int or args['revision'] != case['revision']: raise ConnectorError('Request revision changed in another window. Reload before saving progress.')
    stage = args.get('response_stage')
    coverage = args.get('coverage')
    if stage not in RESPONSE_STAGES or coverage not in COVERAGE: raise ConnectorError('Request response stage or coverage is invalid.')
    prior = case.get('tracking', {})
    message_id=text(args.get('response_message_id', prior.get('response_message_id','')),150,True)
    if stage not in ('none','closed'):
        message=service.message(message_id)
        if message.get('case_id') != case['id'] or message.get('folder') != 'INBOX':
            raise ConnectorError('Response progress requires an incoming message linked to this request.')
    date_value = date_text(args.get('deadline_date', prior.get('deadline_date', '')), 'Deadline date')
    kind = args.get('deadline_kind', prior.get('deadline_kind', ''))
    if kind not in ('', 'response', 'appeal'): raise ConnectorError('Deadline kind must be response or appeal.')
    source = text(args.get('deadline_source', prior.get('deadline_source', '')), 1500, True)
    source = safe_url(source) if source else ''
    basis = text(args.get('deadline_basis', prior.get('deadline_basis', '')), 2500, True)
    checked = date_text(args.get('deadline_checked_date', prior.get('deadline_checked_date', '')), 'Deadline checked date')
    if date_value and (not kind or not source or not basis or not checked): raise ConnectorError('A deadline requires kind, official source, basis and checked date.')
    if checked and date.fromisoformat(checked) > date.today(): raise ConnectorError('Deadline verification cannot be future dated.')
    case['tracking'] = {'response_stage': stage, 'coverage': coverage, 'response_message_id': message_id,
        'note': text(args.get('note', prior.get('note', '')), 4000, True),
        'fee_note': text(args.get('fee_note', prior.get('fee_note', '')), 2500, True),
        'procedure_note': text(args.get('procedure_note', prior.get('procedure_note', '')), 4000, True),
        'deadline_date': date_value, 'deadline_kind': kind, 'deadline_source': source,
        'deadline_basis': basis, 'deadline_checked_date': checked,
        'fee_authorization': 'No fee acceptance is performed by this tool.'}
    service.save(case); service.db.event(case['id'], 'generic_request_progress_saved', {'revision': case['revision'], 'response_stage': stage, 'coverage': coverage})
    return {'case': service.view_case(case), 'messages_sent': 0, 'fees_incurred': False}
