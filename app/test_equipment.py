"""Synthetic campaign regression tests. Never contact a mailbox or agency."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import runtime
from secure_store import ConnectorError, Store, canonical
from storage import Database
from service import Service
import equipment


class Protector:
    def protect(self, value): return bytes(b ^ 63 for b in canonical(value))
    def unprotect(self, value): return json.loads(bytes(b ^ 63 for b in value))


class EquipmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = runtime.load_catalog()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-equipment-synthetic-')
        self.db = Database(Path(self.temp.name) / 'desk', Protector())
        self.store = Store(Path(self.temp.name) / 'mail', Protector())
        self.s = Service(self.db, copy.deepcopy(self.catalog), self.store)
    def tearDown(self): self.temp.cleanup()
    def call(self, name, **args): return self.s.dispatch(name, args)
    def create(self, **args):
        return self.call('desk_create_equipment_request', **({'state':'AZ','jurisdiction':'Synthetic state agency','jurisdiction_level':'state'} | args))['case']
    def state_args(self):
        row = self.call('desk_get_equipment_campaign', state='AZ')['states'][0]
        return {k: copy.deepcopy(row[k]) for k in ('state','revision','phase','scope_note','next_action','sources','coverage')}
    def test_read_all_51_no_store_no_network(self):
        with patch('connector.dispatch', side_effect=AssertionError('No mail calls')):
            r = self.call('desk_get_equipment_campaign')
        self.assertEqual(len(r['states']),51)
        self.assertEqual(r['counts']['states_not_started'],51)
        self.assertEqual(r['counts']['requests_with_send_confirmation'],0)
        self.assertFalse(self.db.root.exists())
        self.assertFalse(r['network_accessed'])
    def test_idempotent_creation_private_and_different_scope(self):
        with patch('connector.dispatch', side_effect=AssertionError('No mail calls')):
            first = self.create()
            again = self.create()
            local = self.create(jurisdiction='Synthetic County',jurisdiction_level='county')
        self.assertEqual(first['id'],again['id'])
        self.assertNotEqual(first['id'],local['id'])
        self.assertEqual(first['drafts'],[])
        self.assertFalse(first['routing_verified'])
        self.assertFalse(first['catalog_drift'])
        self.assertEqual(self.s.catalog,self.catalog)
        r = self.call('desk_get_equipment_campaign')
        self.assertEqual(r['counts']['states_started'],1)
        self.assertEqual(r['counts']['requests'],2)
        self.assertEqual(len(self.call('desk_list_cases')['catalog']['cases']),2)
        self.assertEqual(self.call('desk_get_workspace')['workspace']['starter_pack'],'blank')
        self.call('desk_save_workspace',revision=0,starter_pack='civicresultmaps')
        self.assertEqual(len(self.call('desk_list_cases')['catalog']['cases']),16)
        self.assertIn('No fees are authorized',first['body'])
        self.assertIn('older agreements',first['body'])
        self.assertIn('not an allegation',first['body'])
        reset=equipment.default_state(self.s,'AZ');self.db.put('campaign',reset['id'],reset)
        repaired=self.create()
        row=self.call('desk_get_equipment_campaign',state='AZ')['states'][0]
        self.assertEqual(repaired['id'],first['id'])
        self.assertEqual(row['phase'],'researching');self.assertIn('State-held',row['scope_note'])
    def test_invalid_scope_state_arguments(self):
        for args in ({'state':'XX'},{'jurisdiction_level':'nation'},{'jurisdiction':''}):
            with self.assertRaises(ConnectorError): self.create(**args)
        with self.assertRaises(ConnectorError): self.call('desk_get_equipment_campaign',state='XX')
        with self.assertRaises(ConnectorError): self.call('desk_get_equipment_campaign',send=True)
    def test_revision_control_and_source_validation(self):
        self.create();args = self.state_args()
        args['sources']=[{'title':'Synthetic official page','url':'https://example.gov/records','checked_date':'2026-09-13','summary':'Synthetic context only.'}]
        args['coverage']['equipment']={'status':'partial','note':'Synthetic dated inventory; other categories unknown.'}
        self.call('desk_save_equipment_state',**args)
        with self.assertRaisesRegex(ConnectorError,'revision'): self.call('desk_save_equipment_state',**args)
        args=self.state_args();args['sources'][0]['url']='http://127.0.0.1/secret'
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
        args=self.state_args();args['coverage']['loans']={'status':'not_applicable','note':''}
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
        args=self.state_args();args['sources'][0]['checked_date']='2999-01-01'
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
    def test_no_fake_sent_or_automatic_complete(self):
        c=self.create()
        for stage in ('sent','submitted','awaiting_response'):
            args=self.state_args();args['phase']=stage
            with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
        args=self.state_args();args['phase']='scoped_review_complete'
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
        args=self.state_args();args['phase']='not_started'
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_state',**args)
        c=self.s.case(c['id']);c['stage']='waiting';c['last_sent_at']=time.time();self.s.save(c)
        row=self.call('desk_get_equipment_campaign',state='AZ')['states'][0]
        self.assertEqual(row['requests'][0]['status'],'draft_prepared')
        self.assertEqual(row['requests'][0]['receipts'],[])
        self.assertFalse(row['statewide_completeness_verified'])
    def test_response_requires_linked_incoming_message(self):
        c=self.create()
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_progress',case_id=c['id'],revision=c['revision'],response_stage='acknowledged')
        m={'id':'INBOX:1:1','folder':'INBOX','uid_validity':1,'uid':1,'case_id':c['id'],'synced_at':time.time(),'read_in_desk':False}
        self.db.put('mail',m['id'],m)
        c=self.call('desk_save_equipment_progress',case_id=c['id'],revision=c['revision'],response_stage='acknowledged',response_message_id=m['id'])['case']
        row=self.call('desk_get_equipment_campaign',state='AZ')['states'][0]
        self.assertEqual(row['status'],'new_reply')
        self.assertEqual(row['requests'][0]['receipts'],[])
        m['read_in_desk']=True;self.db.put('mail',m['id'],m)
        self.assertEqual(self.call('desk_get_equipment_campaign',state='AZ')['states'][0]['status'],'acknowledged')
        m['case_id']='another-case';self.db.put('mail',m['id'],m)
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_progress',case_id=c['id'],revision=c['revision'],response_stage='records_received',response_message_id=m['id'])
    def test_deadlines_require_verified_basis_and_do_not_incur_fees(self):
        c=self.create()
        args={'case_id':c['id'],'revision':c['revision'],'response_stage':'none','deadline_date':'2026-10-01'}
        with self.assertRaises(ConnectorError): self.call('desk_save_equipment_progress',**args)
        args.update(deadline_kind='appeal',deadline_source='https://example.gov/records',deadline_basis='Synthetic denial date plus verified business days; no real deadline.',deadline_checked_date='2026-09-13',fee_note='Synthetic estimate only; no approval.')
        with patch('connector.dispatch',side_effect=AssertionError('No mail')):
            r=self.call('desk_save_equipment_progress',**args)
        self.assertFalse(r['fees_incurred'])
        self.assertEqual(r['messages_sent'],0)
        self.assertEqual(r['case']['tracking']['deadline_date'],'2026-10-01')
        c=r['case']
        r=self.call('desk_save_equipment_progress',case_id=c['id'],revision=c['revision'],response_stage='none',note='Later note')
        self.assertEqual(r['case']['tracking']['deadline_date'],'2026-10-01')
        self.assertEqual(r['case']['tracking']['fee_note'],'Synthetic estimate only; no approval.')
    def test_only_actual_draft_receipt_counts_submission(self):
        c=self.create();saved=self.s.case(c['id']);saved['drafts']=['synthetic-draft'];self.s.save(saved)
        draft={'state':'accepted','receipt':{'accepted_at':'2026-09-13T12:00:00+00:00','message_id':'<synthetic@example.test>'},'message_id':'<synthetic@example.test>'}
        with patch.object(self.store,'get_draft',return_value=draft):
            r=self.call('desk_get_equipment_campaign',state='AZ')
        self.assertEqual(r['counts']['requests_with_send_confirmation'],1)
        self.assertEqual(r['states'][0]['requests'][0]['status'],'awaiting_response')
        draft['state']='uncertain'
        with patch.object(self.store,'get_draft',return_value=draft):
            r=self.call('desk_get_equipment_campaign',state='AZ')
        self.assertEqual(r['counts']['requests_with_send_confirmation'],0)
        self.assertEqual(r['states'][0]['status'],'uncertain')
        draft.update(state='accepted',receipt={})
        with patch.object(self.store,'get_draft',return_value=draft):
            r=self.call('desk_get_equipment_campaign',state='AZ')
            self.s.reconcile_sends()
        self.assertEqual(r['counts']['requests_with_send_confirmation'],0)
        self.assertEqual(r['states'][0]['status'],'uncertain')
        self.assertEqual(self.s.case(c['id'])['latest_send_state'],'receipt_invalid')
        with patch.object(self.store,'get_draft',side_effect=ConnectorError('Missing')):
            self.assertEqual(self.call('desk_get_equipment_campaign',state='AZ')['states'][0]['status'],'uncertain')
    def test_template_routing_and_source_catalog_preserved(self):
        c=self.create()
        c=self.call('desk_save_case',case_id=c['id'],revision=c['revision'],recipient='records@example.gov',subject=c['subject'],body=c['body'],routing_verified=True,routing_evidence='https://example.gov/records')['case']
        self.s.verify_routing(self.s.case(c['id']))
        self.assertFalse(c['catalog_drift'])
        with self.assertRaisesRegex(ConnectorError,'explicit'):
            self.call('desk_clone_case',case_id=c['id'],label='Other office')
        stored=self.s.case(c['id']);stored['base']['body']='changed';self.s.save(stored)
        with self.assertRaises(ConnectorError):self.s.verify_routing(self.s.case(c['id']))
    def test_campaign_envelope_identity_guard(self):
        with self.assertRaises(ConnectorError):self.db.put('campaign','x',{'id':'y'})


if __name__=='__main__':unittest.main()
