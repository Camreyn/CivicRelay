"""Read-only, disposable README demo. Never opens live stores or contacts a service."""
from pathlib import Path
import json
import tempfile
from unittest.mock import patch

from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_equipment import Protector
from test_county_progress import seed_browser
import server


ALLOWED = frozenset({
    'desk_list_cases', 'desk_get_case', 'desk_get_workflow', 'desk_get_deadlines',
    'desk_get_state_guide', 'desk_list_counties', 'desk_get_equipment_campaign',
    'desk_get_workspace', 'desk_list_templates', 'desk_get_template',
    'desk_preview_template', 'desk_list_campaigns', 'desk_list_destinations',
})


def seed_demo(service):
    """All scenario/identity text is invented; geography is the bundled public map."""
    service.dispatch('desk_save_workspace', {
        'revision': 0, 'name': 'Example community records desk',
        'organization': 'DEMO / FICTIONAL DATA', 'signature': 'Example Records Team',
        'starter_pack': 'blank',
    })
    # Existing test-only records illustrate six county statuses, never live mail.
    county_ids = seed_browser(service)
    drafts = {}
    scenarios = [
        ('AZ', 'waiting'), ('CA', 'records_received'), ('CO', 'partial_response'),
        ('FL', 'draft'), ('GA', 'new'), ('MA', 'acknowledged'),
        ('NC', 'waiting'), ('NV', 'draft'), ('OH', 'acknowledged'),
        ('OR', 'records_received'), ('PA', 'partial_response'),
        ('TX', 'new'), ('WA', 'waiting'), ('WI', 'draft'),
    ]
    for index, (state, status) in enumerate(scenarios, 20):
        view = service.dispatch('desk_create_equipment_request', {
            'state': state, 'jurisdiction': 'Example state records office',
            'jurisdiction_level': 'state',
        })['case']
        case = service.case(view['id'])
        case.update(recipient='records@example.test', family_label='Example equipment request',
                    routing_verified=False, note='Fictional screenshot scenario. No request was sent.')
        if status != 'draft':
            key = 'demo-receipt-' + state
            message_id = f'<demo-request-{state.lower()}@example.test>'
            case.update(stage='waiting', drafts=[key])
            drafts[key] = {
                'draft_id': key, 'state': 'accepted', 'message_id': message_id,
                'in_reply_to': None, 'receipt': {'message_id': message_id,
                    'accepted_at': '2026-09-28T14:00:00+00:00'},
            }
        if status not in ('draft', 'waiting'):
            key = f'INBOX:99:{index}'
            service.db.put('mail', key, {
                'id': key, 'case_id': case['id'], 'folder': 'INBOX',
                'uid_validity': '99', 'uid': str(index), 'synced_at': 1790683200,
                'from': 'Example Records Office <records@example.test>',
                'to': 'demo@example.test', 'subject': 'Example records response',
                'date': '2026-09-29', 'message_id': f'<demo-reply-{index}@example.test>',
                'read_in_desk': status != 'new', 'body_loaded': False,
                'assignment': 'manual', 'attachment_count': 0,
            })
            case['tracking'] = {'response_stage': 'acknowledged' if status == 'new' else status,
                                'response_message_id': key}
        service.db.put('case', case['id'], case)
    original_get = service.mail_store.get_draft
    service.mail_store.get_draft = lambda key: drafts[key] if key in drafts else original_get(key)
    # Replace default scope notes, not production UI markup or behavior.
    for row in service.db.all('campaign'):
        row.update(scope_note='Fictional example: state-held equipment and service records only.',
                   next_action='Review the example response and record any remaining gaps.')
        service.db.put('campaign', row['id'], row)
    template = service.dispatch('desk_save_template', {'definition': {
        'schema_version': 1, 'title': 'Park maintenance contracts', 'category': 'Local services',
        'fields': [{'id': 'topic', 'label': 'Records requested', 'type': 'text', 'required': True}],
        'subject': 'Public records request: {{topic}} — {{jurisdiction}}',
        'body': 'Hello {{agency}},\n\nPlease provide existing {{topic}} for {{jurisdiction}} '
                'covering {{date_start}} through {{date_end}}.\n\n'
                'Electronic copies are preferred. Please redact exempt personal information '
                'and provide the remaining records. This request does not ask you to create '
                'a report or conduct an investigation.\n\n'
                'Please provide a cost estimate before incurring any fees.\n\n'
                'Thank you,\n{{signature}}',
        'sources': [],
    }})['template']
    service.dispatch('desk_save_campaign', {
        'name': 'Example parks transparency project',
        'description': 'Fictional demonstration. No requests sent and no fees authorized.',
        'template_id': template['id'], 'date_start': '2025-01-01', 'date_end': '2025-12-31',
        'targets': [
            {'id': 'example-riverton', 'label': 'Example Riverton', 'level': 'municipality', 'state': 'WI'},
            {'id': 'example-lakeview', 'label': 'Example Lakeview', 'level': 'municipality', 'state': 'WI'},
        ],
    })
    return {'county_cases': county_ids, 'template_id': template['id']}


def invoke_demo(service, name, args):
    if name not in ALLOWED:
        return {'ok': False, 'error': 'Read-only screenshot demo: mail, saves, exports and external actions are disabled.'}
    return safe_dispatch(name, args, service)


def main():
    with tempfile.TemporaryDirectory(prefix='relay-readme-demo-') as temporary:
        root = Path(temporary)
        service = Service(Database(root / 'desk', Protector()), mail_store=Store(root / 'mail', Protector()))
        seed_demo(service)
        server.invoke = lambda name, args: invoke_demo(service, name, args)
        # Defense in depth: even a mistakenly added read operation cannot open mail,
        # fetch a directory, launch GitHub, or make an outbound socket connection.
        forbidden = AssertionError('External operations are forbidden in the screenshot demo.')
        with patch('connector.dispatch', side_effect=forbidden), \
             patch('bridge.smtp_connection', side_effect=forbidden), \
             patch('bridge.imap_connection', side_effect=forbidden), \
             patch('intake.run', side_effect=forbidden), \
             patch('socket.socket.connect', side_effect=forbidden), \
             patch('socket.socket.connect_ex', side_effect=forbidden):
            with server.Server(('127.0.0.1', 0), server.Handler) as httpd:
                server.PORT = httpd.server_address[1]
                server.ORIGIN = f'http://127.0.0.1:{server.PORT}'
                print(json.dumps({'url': server.ORIGIN, 'synthetic': True, 'read_only': True}), flush=True)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    pass


if __name__ == '__main__':
    main()
