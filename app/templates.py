"""Private, versioned generic request templates with a deliberately tiny renderer."""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import re
import time
import uuid

import connector
from intake import safe_url
from secure_store import ConnectorError, canonical

SCHEMA_VERSION = 1
FIELD_ID = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
TOKEN = re.compile(r'{{\s*(#if\s+)?([a-z][a-z0-9_]*)\s*}}')


def text(value, limit=4000, blank=False):
    if blank and value == '':
        return ''
    return connector.clean_text(value, limit, multiline=True)


def _date(value, label):
    value = text(value, 10)
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ConnectorError(f'{label} must be an exact YYYY-MM-DD date.') from None
    return value


def digest(definition):
    return hashlib.sha256(canonical(definition)).hexdigest()


def normalize_definition(value):
    """Reject executable/template-engine features and all private defaults."""
    if not isinstance(value, dict):
        raise ConnectorError('Template definition must be an object.')
    permitted = {'schema_version', 'title', 'category', 'fields', 'subject', 'body', 'sources', 'review_date', 'archived'}
    if set(value) - permitted or any(k not in value for k in ('schema_version', 'title', 'fields', 'subject', 'body', 'sources')):
        raise ConnectorError('Template definition has unknown or missing fields.')
    if type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION:
        raise ConnectorError('Template schema_version must be 1.')
    fields = value['fields']
    if not isinstance(fields, list) or len(fields) > 50:
        raise ConnectorError('A template needs zero to 50 declared fields.')
    normalized_fields = []
    ids = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) != {'id', 'label', 'required', 'type'}:
            raise ConnectorError('Each template field has only id, label, required and type.')
        field_id = field['id']
        if not isinstance(field_id, str) or not FIELD_ID.fullmatch(field_id) or field_id in ids:
            raise ConnectorError('Template field IDs must be unique lowercase identifiers.')
        if type(field['required']) is not bool or field['type'] not in ('text', 'multiline'):
            raise ConnectorError('Template field required/type is invalid.')
        ids.add(field_id)
        normalized_fields.append({'id': field_id, 'label': text(field['label'], 120), 'required': field['required'], 'type': field['type']})
    sources = value['sources']
    if not isinstance(sources, list) or len(sources) > 30:
        raise ConnectorError('Provide up to 30 reviewed source records.')
    normalized_sources = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'title', 'url', 'review_date'}:
            raise ConnectorError('Each source needs title, URL and review_date.')
        normalized_sources.append({'title': text(source['title'], 200), 'url': safe_url(text(source['url'], 1500)),
                                   'review_date': _date(source['review_date'], 'Source review date')})
    def rendered_text(value, label, limit, multiline=True):
        value = connector.clean_text(value, limit, multiline=multiline)
        token = re.compile(r'{{\s*(?:(#if)\s+([a-z][a-z0-9_]*)|(/if)|([a-z][a-z0-9_]*))\s*}}')
        depth = 0; cursor = 0
        for match in token.finditer(value):
            if '{{' in value[cursor:match.start()] or '}}' in value[cursor:match.start()]:
                raise ConnectorError(f'{label} has invalid placeholder syntax.')
            field_id = match.group(2) or match.group(4)
            if field_id and field_id not in ids and field_id not in {'organization', 'signature', 'requester_email', 'agency', 'jurisdiction', 'state', 'date_start', 'date_end', 'requester_name', 'requester_address', 'requester_phone'}:
                raise ConnectorError(f'{label} references undeclared field {field_id}.')
            if field_id in {'requester_name', 'requester_address', 'requester_phone'}:
                field=next((x for x in normalized_fields if x['id']==field_id),None)
                if not field or not field['required']:
                    raise ConnectorError(f'{label} may use {field_id} only through an explicitly required field.')
            if match.group(1):
                depth += 1
                if depth > 1: raise ConnectorError(f'{label} does not allow nested conditional placeholders.')
            elif match.group(3):
                depth -= 1
                if depth < 0: raise ConnectorError(f'{label} has an unmatched conditional end.')
            cursor = match.end()
        if depth or '{{' in value[cursor:] or '}}' in value[cursor:]:
            raise ConnectorError(f'{label} only supports declared {{field}} and {{#if field}} blocks.')
        return value
    definition = {'schema_version': SCHEMA_VERSION, 'title': text(value['title'], 160),
                  'fields': normalized_fields, 'subject': rendered_text(value['subject'], 'Subject', 250, False),
                  'body': rendered_text(value['body'], 'Body', 50000), 'sources': normalized_sources}
    if 'category' in value:
        definition['category'] = text(value['category'], 100, True)
    # The review date is optional.  Treat an explicitly blank control the same
    # as an omitted field, while retaining strict validation for real dates.
    if 'review_date' in value and value['review_date'] != '':
        definition['review_date'] = _date(value['review_date'], 'Template review date')
    if 'archived' in value:
        if type(value['archived']) is not bool:
            raise ConnectorError('Template archived must be true or false.')
        definition['archived'] = value['archived']
    return definition


def _replace_conditionals(template, values):
    conditional = re.compile(r'{{\s*#if\s+([a-z][a-z0-9_]*)\s*}}(.*?){{\s*/if\s*}}', re.S)
    return conditional.sub(lambda m: m.group(2) if values.get(m.group(1), '') else '', template)


def render(definition, values):
    if not isinstance(values, dict) or any(not isinstance(k, str) for k in values):
        raise ConnectorError('Template values must be an object.')
    declared = {f['id']: f for f in definition['fields']}
    permitted = set(declared) | {'organization', 'signature', 'requester_email', 'agency', 'jurisdiction', 'state', 'date_start', 'date_end', 'requester_name', 'requester_address', 'requester_phone'}
    unknown = set(values) - permitted
    if unknown:
        raise ConnectorError('Template values include unknown fields: ' + ', '.join(sorted(unknown)))
    clean = {}
    for key, value in values.items():
        clean[key] = text(value, 4000, True)
        if key in declared and declared[key]['type'] == 'text' and '\n' in clean[key]:
            raise ConnectorError(f'Template field {key} must be a single line.')
    missing = [key for key, field in declared.items() if field['required'] and not clean.get(key)]
    if missing:
        raise ConnectorError('Template values are missing required fields: ' + ', '.join(missing))
    def fill(value):
        value = _replace_conditionals(value, clean)
        return TOKEN.sub(lambda m: clean.get(m.group(2), ''), value)
    return {'subject': connector.clean_text(fill(definition['subject']), 250, multiline=False),
            'body': connector.clean_text(fill(definition['body']), 50000, multiline=True)}


def summary(record):
    latest = record['versions'][-1]
    return {'id': record['id'], 'revision': record['revision'], 'version': latest['version'], 'title': latest['definition']['title'],
            'archived': bool(latest['definition'].get('archived')), 'updated_at': record['updated_at'], 'hash': latest['hash'],
            'field_count': len(latest['definition']['fields'])}


def get(service, template_id):
    record = service.db.get('template', template_id)
    if not record:
        raise ConnectorError('Template not found.')
    return record


def list_templates(service):
    return {'templates': sorted((summary(x) for x in service.db.all('template')), key=lambda x: (x['archived'], x['title'].casefold(), x['id']))}


def save(service, args, imported=False):
    definition = normalize_definition(args.get('definition'))
    key = args.get('template_id')
    if key is not None and (not isinstance(key, str) or not key):
        raise ConnectorError('Template ID is invalid.')
    existing = service.db.get('template', key) if key else None
    if key and not existing:
        raise ConnectorError('Template not found; omit template_id to create one.')
    if existing:
        if type(args.get('revision')) is not int or args['revision'] != existing['revision']:
            raise ConnectorError('Template changed in another window. Reload before saving.')
        # Avoid a meaningless new immutable version when an operator simply re-saves it.
        if definition == existing['versions'][-1]['definition']:
            return {'template': existing, 'created': False, 'unchanged': True}
        record = copy.deepcopy(existing)
        version = record['versions'][-1]['version'] + 1
        created = False
    else:
        key = 'template-' + uuid.uuid4().hex
        record = {'id': key, 'revision': 0, 'versions': [], 'created_at': time.time()}
        version = 1
        created = True
    snapshot = {'version': version, 'hash': digest(definition), 'created_at': time.time(), 'definition': definition}
    record['versions'].append(snapshot)
    record['revision'] += 1
    record['updated_at'] = time.time()
    service.db.put('template', key, record)
    service.db.event(key, 'template_' + ('imported' if imported else 'saved'), {'revision': record['revision'], 'version': version, 'hash': snapshot['hash']})
    return {'template': record, 'created': created}


def export(service, template_id):
    # Definitions exclude workspace/profile/case values, but their literal author text still needs review before sharing.
    return {'definition': copy.deepcopy(get(service, template_id)['versions'][-1]['definition'])}
