"""Bounded synthetic regression probes for the generic workspace review.

These focused tests are deliberately kept separate from the product tests:
they cover concrete edge cases found in review without changing the
implementation or touching a live store/mailbox.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'connector')]

import equipment  # noqa: E402
import general  # noqa: E402
import templates  # noqa: E402
from secure_store import ConnectorError  # noqa: E402
from service import Service  # noqa: E402


class MemoryDB:
    """Small in-memory stand-in for the encrypted DB used by these probes."""

    def __init__(self, **records):
        self.records = {kind: {row['id']: copy.deepcopy(row) for row in rows}
                        for kind, rows in records.items()}
        self.root = Path('synthetic-desk')

    def get(self, kind, key, default=None):
        value = self.records.get(kind, {}).get(key)
        return copy.deepcopy(value) if value is not None else default

    def all(self, kind):
        return [copy.deepcopy(value) for value in self.records.get(kind, {}).values()]

    def put(self, kind, key, value):
        self.records.setdefault(kind, {})[key] = copy.deepcopy(value)

    def event(self, *_args, **_kwargs):
        return None

    @contextmanager
    def operation(self):
        yield


class ReceiptStore:
    def __init__(self, draft):
        self.draft = draft

    def get_draft(self, _draft_id):
        return copy.deepcopy(self.draft)


class GeneralReviewTests(TestCase):
    def test_blank_optional_template_review_date_is_accepted(self):
        definition = {
            'schema_version': 1,
            'title': 'Synthetic request',
            'fields': [],
            'subject': 'Synthetic subject',
            'body': 'Synthetic body',
            'sources': [{'title': 'Official source', 'url': 'https://example.gov/records',
                         'review_date': '2026-09-17'}],
            # The shared schema permits an explicitly empty optional field.  The
            # backend should normalize it away instead of rejecting the request.
            'review_date': '',
        }
        normalized = templates.normalize_definition(definition)
        self.assertNotIn('review_date', normalized)

    def test_source_review_date_remains_required(self):
        definition = {
            'schema_version': 1,
            'title': 'Synthetic request',
            'fields': [],
            'subject': 'Synthetic subject',
            'body': 'Synthetic body',
            'sources': [{'title': 'Official source', 'url': 'https://example.gov/records',
                         'review_date': ''}],
        }
        with self.assertRaises(ConnectorError):
            templates.normalize_definition(definition)

    def test_equipment_case_does_not_switch_new_generic_workspace_to_legacy_pack(self):
        equipment_case = {'id': 'equipment-case', 'campaign_id': equipment.ID}
        service = type('ServiceStub', (), {
            'db': MemoryDB(case=[equipment_case]),
            'mail_store': object(),
        })()
        with patch.object(general.connector, 'account_summary', return_value={
            'legacy_storage': False,
            'legacy_settings': False,
        }):
            self.assertFalse(general.legacy_storage(service))

    def test_campaign_queue_reconciles_an_accepted_receipt_before_reporting_status(self):
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        campaign = {'id': 'campaign-a', 'kind': 'generic_campaign', 'name': 'Synthetic campaign', 'targets': [target]}
        case = {
            'id': 'request-a', 'general_campaign_id': campaign['id'], 'target': target,
            'revision': 0, 'stage': 'draft', 'drafts': ['draft-a'],
            'tracking': {'response_stage': 'none'},
        }
        accepted = {
            'state': 'accepted',
            'message_id': '<draft-a@example.test>',
            'receipt': {'accepted_at': '2026-09-17T12:00:00+00:00',
                        'message_id': '<draft-a@example.test>'},
        }
        service = Service(
            MemoryDB(campaign=[campaign], case=[case]),
            catalog={},
            mail_store=ReceiptStore(accepted),
        )
        listed = service.dispatch('desk_list_campaigns', {})['campaigns'][0]
        request = listed['target_progress'][0]['requests'][0]
        self.assertEqual(request['stage'], 'waiting')

    def test_reconciled_receipt_does_not_reopen_closed_request(self):
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        campaign = {'id': 'campaign-a', 'kind': 'generic_campaign',
                    'name': 'Synthetic campaign', 'targets': [target]}
        case = {'id': 'request-a', 'general_campaign_id': campaign['id'],
                'target': target, 'revision': 2, 'stage': 'closed',
                'latest_send_state': 'accepted', 'drafts': ['draft-a'],
                'tracking': {'response_stage': 'closed'}}
        accepted = {
            'state': 'accepted', 'message_id': '<draft-a@example.test>',
            'receipt': {'accepted_at': '2026-09-17T12:00:00+00:00',
                        'message_id': '<draft-a@example.test>'},
        }
        service = Service(MemoryDB(campaign=[campaign], case=[case]),
                          catalog={}, mail_store=ReceiptStore(accepted))
        self.assertEqual(general._derived_request_stage(service, case), 'closed')

    def test_campaign_open_end_and_effective_text_changes_do_not_reuse_old_case(self):
        definition = {
            'schema_version': 1, 'title': 'Synthetic request', 'fields': [],
            'subject': 'Request {{date_start}}',
            'body': 'For {{organization}} through {{date_end}}.',
            'sources': [{'title': 'Official source', 'url': 'https://example.gov/records',
                         'review_date': '2026-09-17'}],
        }
        snapshot = {'version': 1, 'hash': templates.digest(definition),
                    'definition': definition}
        template = {'id': 'template-a', 'revision': 1, 'versions': [snapshot]}
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        campaign = {'id': 'campaign-a', 'kind': 'generic_campaign', 'revision': 1,
                    'name': 'Synthetic campaign', 'description': '',
                    'template_id': template['id'], 'date_start': '2026-09-17',
                    'date_end': '2026-10-01', 'targets': [target]}
        db = MemoryDB(template=[template], campaign=[campaign])
        db.put('workspace', 'default', {'id': 'default', 'revision': 1,
                                        'organization': 'First organization',
                                        'signature': '', 'requester_name': '',
                                        'requester_address': '', 'requester_phone': '',
                                        'starter_pack': 'blank'})
        service = Service(db, catalog={'sha256': 'catalog', 'cases': [], 'states': []},
                          mail_store=object())
        with patch.object(general.connector, 'account_summary', return_value={'email': ''}):
            first = service.dispatch('desk_create_request', {
                'campaign_id': campaign['id'], 'target_id': target['id'],
                'agency': 'Synthetic agency', 'values': {}})
            repeat = service.dispatch('desk_create_request', {
                'campaign_id': campaign['id'], 'target_id': target['id'],
                'agency': 'Synthetic agency', 'values': {}})
            self.assertTrue(first['created'])
            self.assertFalse(repeat['created'])
            current = db.get('campaign', campaign['id'])
            updated = service.dispatch('desk_save_campaign', {
                'campaign_id': campaign['id'], 'revision': current['revision'],
                'name': current['name'], 'description': current['description'],
                'template_id': current['template_id'],
                'date_start': current['date_start'],
                'targets': current['targets']})
            changed_date = service.dispatch('desk_create_request', {
                'campaign_id': campaign['id'], 'target_id': target['id'],
                'agency': 'Synthetic agency', 'values': {}})
            self.assertNotEqual(changed_date['case']['id'], first['case']['id'])
            self.assertEqual(updated['campaign']['date_end'], '')
            self.assertEqual(first['case']['campaign_scope']['date_end'], '2026-10-01')
            self.assertEqual(changed_date['case']['campaign_scope']['date_end'], '')
            workspace = db.get('workspace', 'default')
            workspace['organization'] = 'Second organization'
            db.put('workspace', 'default', workspace)
            changed_profile = service.dispatch('desk_create_request', {
                'campaign_id': campaign['id'], 'target_id': target['id'],
                'agency': 'Synthetic agency', 'values': {}})
        self.assertNotEqual(changed_profile['case']['id'], changed_date['case']['id'])

    def test_agency_recipient_is_not_a_request_creation_shortcut(self):
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        definition = {
            'schema_version': 1, 'title': 'Synthetic request', 'fields': [],
            'subject': 'Synthetic subject', 'body': 'Synthetic body',
            'sources': [{'title': 'Official source', 'url': 'https://example.gov/records',
                         'review_date': '2026-09-17'}],
        }
        snapshot = {'version': 1, 'hash': templates.digest(definition),
                    'definition': definition}
        db = MemoryDB(
            template=[{'id': 'template-a', 'revision': 1, 'versions': [snapshot]}],
            campaign=[{'id': 'campaign-a', 'kind': 'generic_campaign',
                       'revision': 1, 'template_id': 'template-a',
                       'date_start': '', 'date_end': '', 'targets': [target]}])
        service = Service(db, catalog={'sha256': 'catalog', 'cases': [], 'states': []},
                          mail_store=object())
        with patch.object(general.connector, 'account_summary', return_value={'email': ''}):
            with self.assertRaises(ConnectorError):
                service.dispatch('desk_create_request', {
                    'campaign_id': 'campaign-a', 'target_id': 'target-a',
                    'agency': {'name': 'Synthetic agency',
                               'recipient': 'records@example.gov'}, 'values': {}})

    def test_status_reports_current_backend_tooling_version(self):
        service = Service(MemoryDB(), catalog={'sha256': 'catalog', 'cases': [], 'states': []},
                          mail_store=object())
        with patch('service.connector.dispatch', return_value={}):
            self.assertEqual(service.dispatch('desk_status', {})['tooling_version'], '0.6.0')

    def test_unassigning_response_evidence_clears_progress_that_requires_linkage(self):
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        case = {
            'id': 'request-a', 'general_campaign_id': 'campaign-a', 'target': target,
            'revision': 1, 'stage': 'waiting', 'drafts': [], 'issues': [],
            'tracking': {'response_stage': 'acknowledged', 'coverage': 'partial',
                         'response_message_id': 'INBOX:1:1', 'note': 'Keep this note',
                         'fee_note': 'No fee accepted', 'procedure_note': 'Keep procedure'},
            'base': {},
        }
        message = {'id': 'INBOX:1:1', 'folder': 'INBOX', 'case_id': case['id']}
        db = MemoryDB(case=[case], mail=[message])
        service = Service(db, catalog={}, mail_store=object())
        service.dispatch('desk_link_message', {'message_id': message['id'], 'case_id': ''})
        stored = db.get('case', case['id'])
        self.assertEqual(stored['tracking']['response_stage'], 'none')
        self.assertEqual(stored['tracking']['response_message_id'], '')
        self.assertEqual(stored['tracking']['coverage'], 'partial')
        self.assertEqual(stored['tracking']['note'], 'Keep this note')
        self.assertEqual(stored['revision'], 2)

    def test_reassigning_response_evidence_resets_the_previous_case(self):
        target = {'id': 'target-a', 'label': 'Synthetic target', 'level': 'other'}
        previous = {
            'id': 'request-previous', 'general_campaign_id': 'campaign-a',
            'target': target, 'revision': 1, 'stage': 'waiting', 'drafts': [],
            'issues': [], 'tracking': {'response_stage': 'acknowledged',
                                       'coverage': 'received',
                                       'response_message_id': 'INBOX:2:1',
                                       'note': 'Preserve this note'}, 'base': {},
        }
        destination = {
            'id': 'request-destination', 'general_campaign_id': 'campaign-a',
            'target': target, 'revision': 1, 'stage': 'draft', 'drafts': [],
            'issues': [], 'tracking': {'response_stage': 'none'}, 'base': {},
        }
        message = {'id': 'INBOX:2:1', 'folder': 'INBOX',
                   'case_id': previous['id']}
        db = MemoryDB(case=[previous, destination], mail=[message])
        service = Service(db, catalog={}, mail_store=object())
        service.dispatch('desk_link_message', {'message_id': message['id'],
                                                'case_id': destination['id']})
        stored = db.get('case', previous['id'])
        self.assertEqual(stored['tracking']['response_stage'], 'none')
        self.assertEqual(stored['tracking']['response_message_id'], '')
        self.assertEqual(stored['tracking']['coverage'], 'received')
        self.assertEqual(stored['tracking']['note'], 'Preserve this note')
        self.assertEqual(stored['revision'], 2)


if __name__ == '__main__':
    import unittest
    unittest.main()
