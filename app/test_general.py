"""Synthetic regression tests for the generic private workspace and campaign layer."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

import runtime
from secure_store import ConnectorError, Store, canonical
from storage import Database
from service import Service


class Protector:
    def protect(self, value): return bytes(b ^ 63 for b in canonical(value))
    def unprotect(self, value): return json.loads(bytes(b ^ 63 for b in value))


class GeneralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = runtime.load_catalog()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-general-synthetic-')
        self.db = Database(Path(self.temp.name) / 'desk', Protector())
        self.store = Store(Path(self.temp.name) / 'mail', Protector())
        self.s = Service(self.db, copy.deepcopy(self.catalog), self.store)
    def tearDown(self): self.temp.cleanup()
    def call(self, operation, **args): return self.s.dispatch(operation, args)
    def definition(self, **changes):
        value = {'schema_version': 1, 'title': 'Synthetic records request', 'category': 'synthetic',
                 'fields': [{'id':'topic','label':'Topic','required':True,'type':'text'}, {'id':'details','label':'Details','required':False,'type':'multiline'}],
                 'subject':'Request: {{topic}}', 'body':'Hello {{organization}}. {{#if details}}Details: {{details}}{{/if}} {{signature}}',
                 'sources':[{'title':'Synthetic official source','url':'https://example.gov/records','review_date':'2026-09-17'}]}
        return value | changes
    def template(self): return self.call('desk_save_template', definition=self.definition())['template']
    def test_documented_template_example_imports_and_renders(self):
        import re
        documentation=(Path(__file__).resolve().parents[1]/'docs'/'TEMPLATES.md').read_text(encoding='utf-8')
        example=json.loads(re.search(r'```json\s*\n(.*?)\n```',documentation,re.S).group(1))
        template=self.call('desk_import_template',definition=example)['template']
        rendered=self.call('desk_preview_template',template_id=template['id'],values={'topic':'Synthetic existing records','jurisdiction':'Synthetic jurisdiction','agency':'Synthetic records office'})['rendered']
        self.assertIn('Synthetic existing records',rendered['body'])
        self.assertIn('Synthetic jurisdiction',rendered['subject'])
    def test_workspace_private_values_not_exported_and_preserved_when_omitted(self):
        w=self.call('desk_get_workspace')['workspace']; self.assertEqual(w['starter_pack'],'blank')
        self.assertEqual(self.call('desk_list_cases')['catalog']['cases'],[])
        w=self.call('desk_save_workspace',revision=w['revision'],organization='Synthetic org',signature='Synthetic signature',requester_name='Private Person',requester_address='Private address',requester_phone='555-0100',starter_pack='blank')['workspace']
        self.assertTrue(w['requester_configured']); self.assertEqual(w['requester_name'],'Private Person')
        w=self.call('desk_save_workspace',revision=w['revision'],name='Only name changes')['workspace']
        self.assertEqual(w['requester_address'],'Private address')
        t=self.template(); exported=self.call('desk_export_template',template_id=t['id'])['definition']
        self.assertNotIn('Private Person', json.dumps(exported)); self.assertNotIn('default', json.dumps(exported))
    def test_template_versions_safe_render_archive_and_duplicate(self):
        t=self.template(); preview=self.call('desk_preview_template',template_id=t['id'],values={'topic':'Synthetic topic'})
        self.assertIn('Hello',preview['rendered']['body'])
        with self.assertRaisesRegex(ConnectorError,'missing|required'): self.call('desk_preview_template',template_id=t['id'],values={})
        with self.assertRaisesRegex(ConnectorError,'unknown'): self.call('desk_preview_template',template_id=t['id'],values={'topic':'x','evil':'y'})
        with self.assertRaises(ConnectorError): self.call('desk_save_template',template_id=t['id'],revision=t['revision'],definition=self.definition(body='{{__import__}}'))
        changed=self.definition(archived=True); updated=self.call('desk_save_template',template_id=t['id'],revision=t['revision'],definition=changed)['template']
        self.assertEqual(updated['versions'][-1]['version'],2); self.assertFalse(updated['versions'][0]['definition'].get('archived',False))
        duplicate=self.call('desk_save_template',definition=self.definition())['template']; self.assertNotEqual(duplicate['id'],t['id'])
    def test_campaign_case_snapshot_survives_template_change(self):
        t=self.template(); campaign=self.call('desk_save_campaign',name='Synthetic campaign',description='',template_id=t['id'],date_start='2026-09-17',date_end='2026-10-01',targets=[{'id':'county-x','label':'Synthetic County','level':'county','state':'AZ'}])['campaign']
        c=self.call('desk_create_request',campaign_id=campaign['id'],target_id='county-x',agency={'name':'Synthetic records office'},values={'topic':'Synthetic topic'})['case']
        self.assertEqual(c['template_snapshot']['version'],1); original=c['body']
        self.call('desk_save_template',template_id=t['id'],revision=t['revision'],definition=self.definition(body='Changed {{topic}}'))
        saved=self.s.case(c['id']); self.assertEqual(saved['body'],original); self.assertFalse(self.s.view_case(saved)['catalog_drift'])
        message={'id':'INBOX:1:1','folder':'INBOX','uid_validity':1,'uid':1,'case_id':c['id'],'synced_at':time.time(),'read_in_desk':False}
        self.db.put('mail',message['id'],message)
        progress=self.call('desk_save_request_progress',case_id=c['id'],revision=c['revision'],response_stage='fee_notice',response_message_id=message['id'],coverage='partial',fee_note='Synthetic only; not accepted.')['case']
        self.assertFalse(progress['tracking']['fee_authorization'] != 'No fee acceptance is performed by this tool.')
        with self.assertRaisesRegex(ConnectorError,'revision'): self.call('desk_save_request_progress',case_id=c['id'],revision=c['revision'],response_stage='none',coverage='not_assessed')
    def test_legacy_case_signals_optional_pack_without_connector_read(self):
        base=copy.deepcopy(self.catalog['cases'][0]); legacy={**base,'base':base,'catalog_sha256':self.catalog['sha256'],'revision':1,'routing_verified':False,'routing_evidence':'','stage':'draft','note':'','drafts':[],'issues':[]}
        self.db.put('case',legacy['id'],legacy)
        self.assertTrue(self.call('desk_get_workspace')['workspace']['legacy_storage'])
        self.assertEqual(self.call('desk_get_workspace')['workspace']['starter_pack'],'civicresultmaps')
        self.assertEqual(len(self.call('desk_list_cases')['catalog']['cases']),len(self.catalog['cases']))
    def test_renderer_rejects_unsafe_forms_and_allows_sequential_conditionals(self):
        for body in ('{{#if topic}}x', '{{/if}}', '{{#if topic}}{{#if details}}x{{/if}}{{/if}}', '{{unknown}}', '{{ topic '):
            with self.assertRaises(ConnectorError): self.call('desk_save_template',definition=self.definition(body=body))
        body='{{#if topic}}A{{/if}}{{#if details}}B{{/if}}'
        t=self.call('desk_save_template',definition=self.definition(body=body))['template']
        self.assertEqual(self.call('desk_preview_template',template_id=t['id'],values={'topic':'x'})['rendered']['body'],'A')
        self.assertEqual(self.call('desk_preview_template',template_id=t['id'],values={'topic':'x','details':'y'})['rendered']['body'],'AB')
        with self.assertRaises(ConnectorError): self.call('desk_save_template',definition=self.definition(subject='bad\nheader'))
        with self.assertRaises(ConnectorError): self.call('desk_preview_template',template_id=t['id'],values={'topic':'a\nb'})
    def test_private_profile_requires_required_declared_field_and_exports_no_case_values(self):
        w=self.call('desk_get_workspace')['workspace']
        self.call('desk_save_workspace',revision=w['revision'],requester_name='Synthetic Private Name',requester_address='Synthetic Private Address')
        with self.assertRaises(ConnectorError): self.call('desk_save_template',definition=self.definition(body='{{requester_name}}'))
        fields=self.definition()['fields']+[{'id':'requester_name','label':'Requester','required':True,'type':'text'}]
        t=self.call('desk_save_template',definition=self.definition(fields=fields,body='{{requester_name}} {{topic}}'))['template']
        self.assertIn('Synthetic Private Name',self.call('desk_preview_template',template_id=t['id'],values={'topic':'Synthetic'})['rendered']['body'])
        exported=self.call('desk_export_template',template_id=t['id'])['definition']
        self.assertNotIn('Synthetic Private Name',json.dumps(exported))
    def test_campaign_counts_idempotency_and_target_preservation(self):
        t=self.template(); campaign=self.call('desk_save_campaign',name='Campaign',description='',template_id=t['id'],date_start='2026-09-17',date_end='2026-09-20',targets=[{'id':'a','label':'A','level':'state','state':'AZ'},{'id':'b','label':'B','level':'other'}])['campaign']
        first=self.call('desk_create_request',campaign_id=campaign['id'],target_id='a',agency='Agency',values={'topic':'x'})
        again=self.call('desk_create_request',campaign_id=campaign['id'],target_id='a',agency='Agency',values={'topic':'x'})
        self.assertTrue(first['created']); self.assertFalse(again['created']); self.assertEqual(first['case']['id'],again['case']['id'])
        listed=self.call('desk_list_campaigns')['campaigns'][0]; self.assertEqual(listed['remaining_targets'],1); self.assertEqual(listed['target_progress'][0]['request_count'],1)
        with self.assertRaises(ConnectorError): self.call('desk_save_campaign',campaign_id=campaign['id'],revision=campaign['revision'],name='Campaign',description='',template_id=t['id'],date_start='2026-09-17',date_end='2026-09-20',targets=[{'id':'b','label':'B','level':'other'}])
        with self.assertRaises(ConnectorError): self.call('desk_save_campaign',campaign_id=campaign['id'],revision=campaign['revision'],name='Campaign',description='',template_id=t['id'],date_start='2026-09-17',date_end='2026-09-20',targets=[{'id':'a','label':'A retargeted','level':'county','state':'AZ'},{'id':'b','label':'B','level':'other'}])
    def test_response_evidence_receipts_and_publication_are_independent(self):
        t=self.template(); campaign=self.call('desk_save_campaign',name='Campaign',description='',template_id=t['id'],date_start='2026-09-17',date_end='2026-09-20',targets=[{'id':'a','label':'A','level':'state','state':'AZ'}])['campaign']
        c=self.call('desk_create_request',campaign_id=campaign['id'],target_id='a',agency='Agency',values={'topic':'x'})['case']
        with self.assertRaises(ConnectorError): self.call('desk_save_request_progress',case_id=c['id'],revision=c['revision'],response_stage='acknowledged',coverage='partial')
        m={'id':'INBOX:4:8','folder':'INBOX','uid_validity':4,'uid':8,'case_id':c['id'],'synced_at':time.time(),'read_in_desk':False}; self.db.put('mail',m['id'],m)
        c=self.call('desk_save_request_progress',case_id=c['id'],revision=c['revision'],response_stage='acknowledged',response_message_id=m['id'],coverage='partial')['case']
        m['case_id']='elsewhere'; self.db.put('mail',m['id'],m)
        with self.assertRaises(ConnectorError): self.call('desk_save_request_progress',case_id=c['id'],revision=c['revision'],response_stage='records_received',response_message_id=m['id'],coverage='received')
        stored=self.s.case(c['id']); stored['drafts']=['synthetic']; self.s.save(stored)
        from unittest.mock import patch
        malformed={'state':'accepted','receipt':{},'message_id':'<synthetic@example.test>'}
        with patch.object(self.store,'get_draft',return_value=malformed): self.s.reconcile_sends()
        self.assertEqual(self.s.case(c['id'])['stage'],'attention')
        stored=self.s.case(c['id']); issue={'id':'issue-synthetic','case_id':c['id'],'state':'published'}; self.db.put('issue',issue['id'],issue); stored['issues'].append(issue['id']); self.s.save(stored)
        view=self.s.view_case(self.s.case(c['id'])); self.assertEqual(view['publication_status'],'published'); self.assertEqual(view['stage'],'attention')


if __name__ == '__main__': unittest.main()
