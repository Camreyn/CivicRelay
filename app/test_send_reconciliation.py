"""Synthetic send-status regression tests; no mailbox, transport or live storage."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runtime
import equipment
import general
from service import Service
from test_general_review import MemoryDB


FIRST = '2026-09-01T12:00:00+00:00'
FOLLOWUP = '2026-09-02T12:00:00+00:00'


def accepted(key, when):
    message_id = f'<{key}@example.test>'
    return {'draft_id': key, 'state': 'accepted', 'message_id': message_id,
            'receipt': {'message_id': message_id, 'accepted_at': when}}


class SendReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = runtime.load_catalog()

    def setUp(self):
        self.db = MemoryDB()
        self.drafts = {'initial': accepted('initial', FIRST),
                       'reply': accepted('reply', FOLLOWUP)}
        store = SimpleNamespace(get_draft=lambda key: copy.deepcopy(self.drafts[key]))
        self.service = Service(self.db, copy.deepcopy(self.catalog), store)
        self.case = self.service.case('source-IN-2024')
        self.case.update(stage='ready', drafts=['initial', 'reply'],
                         latest_send_state='accepted', last_sent_at=FIRST,
                         recipient='records@example.test', routing_verified=True,
                         subject='Synthetic request', body='Synthetic follow-up',
                         routing_evidence='https://example.test/records', note='Preserve this note')
        self.save()

    def save(self):
        self.db.put('case', self.case['id'], self.case)

    def reconcile(self):
        with patch('connector.dispatch', side_effect=AssertionError('No transport')):
            self.service.reconcile_sends()
        return self.service.case(self.case['id'])

    def test_followup_with_same_accepted_state_updates_status_and_identity(self):
        self.case['latest_send_draft_id'] = 'initial'
        self.save()
        case = self.reconcile()
        self.assertEqual(case['stage'], 'waiting')
        self.assertEqual(case['latest_send_draft_id'], 'reply')
        self.assertEqual(case['last_sent_at'], FOLLOWUP)
        self.assertEqual(case['note'], 'Preserve this note')
        self.assertEqual(self.service.view_case(case)['status'], 'waiting')

    def test_legacy_stale_status_is_repaired_from_latest_receipt(self):
        case = self.reconcile()
        self.assertEqual(case['stage'], 'waiting')
        self.assertEqual(case['last_sent_at'], FOLLOWUP)
        self.assertEqual(case['latest_send_draft_id'], 'reply')
        self.assertEqual(self.reconcile(), case)

    def test_reconciled_operator_stage_is_not_overwritten(self):
        for stage in ('ready', 'attention', 'submitted', 'closed'):
            with self.subTest(stage=stage):
                self.case.update(stage=stage, latest_send_draft_id='reply', last_sent_at=FOLLOWUP)
                self.save()
                self.assertEqual(self.reconcile(), self.case)

    def test_legacy_current_receipt_backfills_identity_without_reopening(self):
        for stage in ('ready', 'attention', 'submitted', 'closed'):
            with self.subTest(stage=stage):
                self.case.update(stage=stage, last_sent_at=FOLLOWUP)
                self.save()
                case = self.reconcile()
                self.assertEqual(case['stage'], stage)
                self.assertEqual(case['latest_send_draft_id'], 'reply')
                self.assertEqual(self.reconcile(), case)

    def test_draft_identity_not_timestamp_distinguishes_new_send(self):
        self.drafts['reply']['receipt']['accepted_at'] = FIRST
        self.case['latest_send_draft_id'] = 'initial'
        self.save()
        self.assertEqual(self.reconcile()['stage'], 'waiting')

    def test_draft_and_uncertain_outcomes_do_not_become_waiting(self):
        for state in ('draft', 'sending', 'uncertain', 'failed_before_data'):
            with self.subTest(state=state):
                self.drafts['reply'].update(state=state, receipt=None)
                self.case.update(latest_send_draft_id='initial', stage='ready')
                self.save()
                case = self.reconcile()
                self.assertEqual(case['stage'], 'ready' if state == 'draft' else 'attention')
                self.assertEqual(case['latest_send_state'], state)
                self.assertEqual(case['latest_send_draft_id'], 'reply')
                self.assertEqual(case['last_sent_at'], FIRST)

    def test_invalid_receipt_is_not_trusted_in_any_case_family(self):
        for family in ('legacy', 'equipment', 'generic'):
            with self.subTest(family=family):
                self.case.pop('campaign_id', None)
                self.case.pop('general_campaign_id', None)
                if family == 'equipment': self.case['campaign_id'] = equipment.ID
                if family == 'generic': self.case['general_campaign_id'] = 'synthetic-campaign'
                self.drafts['reply']['receipt']['message_id'] = '<wrong@example.test>'
                self.save()
                case = self.reconcile()
                self.assertEqual(case['stage'], 'attention')
                self.assertEqual(case['latest_send_state'], 'receipt_invalid')
                self.assertEqual(case['last_sent_at'], FIRST)

    def test_generic_queue_uses_same_draft_identity_without_writes(self):
        target = {'id': 'synthetic-target', 'label': 'Synthetic target', 'level': 'other'}
        campaign = {'id': 'synthetic-campaign', 'kind': 'generic_campaign',
                    'name': 'Synthetic campaign', 'targets': [target]}
        self.db.put('campaign', campaign['id'], campaign)
        self.case.update(general_campaign_id=campaign['id'], target=target,
                         latest_send_draft_id='initial')
        self.save()
        before = copy.deepcopy(self.db.records)
        listed = general.list_campaigns(self.service)['campaigns'][0]
        self.assertEqual(listed['target_progress'][0]['requests'][0]['stage'], 'waiting')
        self.assertEqual(self.db.records, before)

    def test_recovered_waiting_case_can_save_notes_without_resending(self):
        case = self.reconcile()
        with patch('connector.dispatch', side_effect=AssertionError('No transport')):
            saved = self.service.dispatch('desk_save_case', {
                'case_id': case['id'], 'revision': case['revision'], 'stage': 'waiting',
                'recipient': case['recipient'], 'subject': case['subject'], 'body': case['body'],
                'routing_verified': True, 'routing_evidence': case['routing_evidence'],
                'note': 'Synthetic follow-up already accepted; awaiting response',
            })
        self.assertEqual(saved['case']['stage'], 'waiting')
        self.assertEqual(saved['messages_sent'], 0)


if __name__ == '__main__':
    unittest.main()
