"""Synthetic county research tests. Never reads the live mailbox or sends mail."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import runtime
import contacts
from secure_store import ConnectorError, Store, canonical
from service import Service
from storage import Database


class Protector:
    def protect(self, value): return bytes(b ^ 47 for b in canonical(value))
    def unprotect(self, value): return json.loads(bytes(b ^ 47 for b in value))


class ContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = runtime.load_catalog()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-contacts-synthetic-')
        self.db = Database(Path(self.temp.name) / 'desk', Protector())
        self.store = Store(Path(self.temp.name) / 'mail', Protector())
        self.s = Service(self.db, copy.deepcopy(self.catalog), self.store)
    def tearDown(self): self.temp.cleanup()
    def call(self, name, **args): return self.s.dispatch(name, args)
    def result(self, outcome='verified', day=None, email='records@example.test'):
        day = day or contacts.today().isoformat()
        return {'outcome': outcome, 'checked_on': day,
                'contacts': [{'department':'Synthetic FOIA office','email':email,'route_type':'designated_custodian','source_url':'https://example.gov/foia'}] if outcome in ('verified','candidate','conflict') else [],
                'sources':[{'url':'https://example.gov/foia','title':'Synthetic official contacts','publisher':'Synthetic County','checked_on':day,'official':True,'evidence':'Synthetic published email and designated filing role, not a real contact.'}],
                'note':'Synthetic evidence only. No real source or request.'}
    def save(self, **changes):
        args={'county_id':'county:26001','role':'public_records','revision':0,'operation_key':'manual-one','result':self.result()};args.update(changes)
        return self.call('desk_save_contact', **args)
    def create(self, **changes):
        args={'state':'MI','county_ids':['county:26001','county:26003'],'roles':['public_records'],'request_key':'batch-one'};args.update(changes)
        return self.call('desk_create_contact_batch', **args)['batch']
    def claim(self, b, worker='worker-a', limit=1):
        return self.call('desk_claim_contact_tasks',batch_id=b['id'],worker_id=worker,limit=limit)['tasks']
    def finish(self, b, t, result=None):
        return self.call('desk_complete_contact_task',batch_id=b['id'],task_id=t['id'],lease_token=t['lease_token'],result=result or self.result())

    def test_counties_include_all_missing_and_equivalents(self):
        national=self.call('desk_list_counties');self.assertEqual(national['inventory']['count'],3144);self.assertEqual(len(national['states']),51)
        self.assertEqual(national['counties'],[])
        mi=self.call('desk_list_counties',state='MI');self.assertEqual(len(mi['counties']),83)
        self.assertEqual(len(self.call('desk_list_counties',state='CT')['counties']),9)
        self.assertEqual(len(self.call('desk_list_counties',state='DC')['counties']),1)
        found=self.call('desk_find_contacts',state='MI',roles=['public_records'],limit=100)
        self.assertEqual(found['scope_total'],83);self.assertEqual(found['counts'],{'missing':83})
        all_roles=self.call('desk_find_contacts',state='TX',limit=100);self.assertEqual(all_roles['scope_total'],254*6);self.assertEqual(all_roles['next_offset'],100)

    def test_validation_rejects_wrong_counties_empty_duplicates_and_unknown_fields(self):
        for args in ({'state':'XX'},{'state':'MI','county_ids':[]},{'state':'MI','county_ids':['county:55001']},{'state':'MI','roles':[]},{'state':'MI','roles':['x']},{'state':'MI','roles':['it','it']},{'state':'MI','max_age_days':True},{'state':'MI','county_ids':['county:26001']*2},{'state':'MI','command':'bad'}):
            with self.assertRaises(ConnectorError):self.call('desk_find_contacts',**args)
        bad=self.result();bad['authorization']='send'
        with self.assertRaises(ConnectorError):self.save(result=bad)

    def test_history_revision_idempotency_and_dates(self):
        first=self.save();self.assertEqual(first['contact']['revision'],1)
        self.assertTrue(self.save()['already_saved'])
        with self.assertRaisesRegex(ConnectorError,'different evidence'):self.save(result=self.result(email='other@example.test'))
        with self.assertRaisesRegex(ConnectorError,'revision'):self.save(operation_key='two')
        second=self.save(operation_key='two',revision=1,result=self.result('no_email_found'))
        self.assertEqual(second['contact']['revision'],2);self.assertEqual(second['contact']['last_verified_on'],contacts.today().isoformat())
        detail=self.call('desk_get_contact',county_id='county:26001',role='public_records',history_limit=1)
        self.assertEqual(detail['contact']['history_count'],2);self.assertEqual(detail['history'][0]['outcome'],'no_email_found');self.assertEqual(detail['next_history_offset'],1)
        self.assertEqual(self.call('desk_get_contact',county_id='county:26001',role='public_records',history_offset=1)['history'][0]['contacts'][0]['email'],'records@example.test')
        raw=(self.db.root/'records.sqlite3').read_bytes();self.assertNotIn(b'records@example.test',raw)

    def test_evidence_constraints_and_public_url_safety(self):
        mutations=[lambda r:r.update(checked_on='2099-01-01'),lambda r:r.update(sources=[]),lambda r:r['sources'][0].update(official=False),lambda r:r['sources'][0].update(checked_on='2000-01-01'),lambda r:r['contacts'][0].update(route_type='records_holder'),lambda r:r['contacts'][0].update(source_url='https://example.gov/other'),lambda r:r['contacts'][0].update(email='a@example.test\nBcc: x@y.test')]
        for change in mutations:
            r=self.result();change(r)
            with self.assertRaises(ConnectorError):self.save(result=r)
        for url in ('http://example.gov/a','javascript:alert(1)','https://127.0.0.1/x','https://user:pass@example.gov/','https://site.local/x','https://example.gov:8443/x'):
            r=self.result();r['sources'][0]['url']=url;r['contacts'][0]['source_url']=url
            with self.assertRaises(ConnectorError):self.save(result=r)
        r=self.result('blocked');r['sources']=[];self.assertEqual(self.save(result=r)['contact']['current']['outcome'],'blocked')

    def test_freshness_is_source_check_not_import_timestamp(self):
        old=(contacts.today()-timedelta(days=100)).isoformat();self.save(result=self.result(day=old))
        r=self.call('desk_find_contacts',state='MI',county_ids=['county:26001'],roles=['public_records'])
        self.assertEqual(r['items'][0]['status'],'stale')
        r=self.call('desk_find_contacts',state='MI',county_ids=['county:26001'],roles=['public_records'],max_age_days=120)
        self.assertEqual(r['items'][0]['status'],'current')

    def test_batch_skips_current_and_existing_work_idempotently(self):
        self.save();b=self.create();self.assertEqual(b['task_count'],1);self.assertEqual(b['skipped'],{'current':1})
        self.assertTrue(self.call('desk_create_contact_batch',state='MI',county_ids=['county:26001','county:26003'],roles=['public_records'],request_key='batch-one')['already_created'])
        with self.assertRaisesRegex(ConnectorError,'different scope'):self.create(roles=['it'])
        other=self.create(request_key='batch-two');self.assertEqual(other['task_count'],0);self.assertEqual(other['skipped']['already_queued'],1);self.assertIn(b['id'],other['existing_batch_ids'])

    def test_workers_do_not_duplicate_and_claims_renew(self):
        b=self.create();a=self.claim(b)[0];again=self.claim(b)[0]
        self.assertEqual(a['lease_token'],again['lease_token']);self.assertGreaterEqual(again['lease_expires_at'],a['lease_expires_at'])
        z=self.claim(b,'worker-b')[0];self.assertNotEqual(a['id'],z['id']);self.assertEqual(self.claim(b,'worker-c'),[])
        detail=self.call('desk_get_contact_batch',batch_id=b['id']);self.assertNotIn('lease_token',json.dumps(detail));self.assertEqual(detail['batch']['counts'],{'claimed':2})
        self.assertIn('untrusted',a['research_brief'])

    def test_expired_lease_reclaimed_and_old_result_rejected(self):
        b=self.create();t=self.claim(b)[0]
        with patch('contacts.time.time',return_value=time.time()+contacts.LEASE_SECONDS+1):
            with self.assertRaisesRegex(ConnectorError,'expired'):self.finish(b,t)
            replacement=self.claim(b,'worker-b')[0]
        self.assertNotEqual(replacement['lease_token'],t['lease_token'])
        with self.assertRaisesRegex(ConnectorError,'identity'):self.finish(b,t)
        self.finish(b,replacement)

    def test_completion_atomic_retry_and_unresolved_not_ready(self):
        b=self.create();t=self.claim(b)[0];r=self.finish(b,t,self.result('not_found'))
        self.assertEqual(r['batch']['unresolved_tasks'],1);self.assertEqual(r['batch']['resolved_tasks'],0)
        self.assertTrue(self.finish(b,t,self.result('not_found'))['already_completed'])
        with self.assertRaisesRegex(ConnectorError,'different evidence'):self.finish(b,t)
        self.assertEqual(self.call('desk_find_contacts',state='MI',roles=['public_records'],county_ids=[t['county_id']])['items'][0]['status'],'not_found')
        t2=self.claim(b)[0];self.finish(b,t2)
        saved=self.call('desk_get_contact_batch',batch_id=b['id'])['batch'];self.assertEqual(saved['status'],'complete');self.assertEqual(saved['unresolved_tasks'],1)

    def test_transaction_rolls_back_contact_if_batch_encryption_fails(self):
        b=self.create();t=self.claim(b)[0];original=self.db.protector.protect
        def fail(value):
            if value['kind']=='contact_batch':raise ConnectorError('Synthetic encryption failure.')
            return original(value)
        with patch.object(self.db.protector,'protect',side_effect=fail):
            with self.assertRaisesRegex(ConnectorError,'Synthetic'):self.finish(b,t)
        self.assertIsNone(self.db.get('contact',t['id']));self.assertEqual(self.call('desk_get_contact_batch',batch_id=b['id'])['tasks'][0]['status'],'claimed')
        self.finish(b,t)

    def test_manual_edit_during_lease_cannot_be_overwritten(self):
        b=self.create();t=self.claim(b)[0];self.save(result=self.result('candidate'))
        with self.assertRaisesRegex(ConnectorError,'revision'):self.finish(b,t)
        self.call('desk_release_contact_task',batch_id=b['id'],task_id=t['id'],lease_token=t['lease_token'],note='Evidence changed; review again.')
        renewed=self.claim(b)[0];self.assertEqual(renewed['contact_revision'],1);self.finish(b,renewed)

    def test_paused_cancelled_revision_and_coverage_reservation(self):
        b=self.create();t=self.claim(b)[0];b=self.call('desk_get_contact_batch',batch_id=b['id'])['batch']
        paused=self.call('desk_update_contact_batch',batch_id=b['id'],revision=b['revision'],status='paused')['batch']
        with self.assertRaises(ConnectorError):self.claim(b)
        with self.assertRaises(ConnectorError):self.finish(b,t)
        with self.assertRaisesRegex(ConnectorError,'revision'):self.call('desk_update_contact_batch',batch_id=b['id'],revision=b['revision'],status='queued')
        self.assertEqual(self.create(request_key='other')['task_count'],0)
        cancelled=self.call('desk_update_contact_batch',batch_id=b['id'],revision=paused['revision'],status='cancelled')['batch']
        with self.assertRaises(ConnectorError):self.call('desk_update_contact_batch',batch_id=b['id'],revision=cancelled['revision'],status='queued')
        self.assertEqual(self.create(request_key='after-cancel')['task_count'],2)

    def test_new_current_evidence_reused_before_claim(self):
        b=self.create();self.save();t=self.claim(b)[0];self.assertEqual(t['county_id'],'county:26003')
        detail=self.call('desk_get_contact_batch',batch_id=b['id']);self.assertEqual(detail['batch']['counts']['reused'],1)

    def test_saved_case_leads_exact_county_only_never_role_verified(self):
        for label,level,email in [('Alcona County','county','county@example.test'),('Michigan','state','state@example.test'),('Alcona County','municipality','city@example.test')]:
            c=self.call('desk_create_equipment_request',state='MI',jurisdiction=label,jurisdiction_level=level)['case'];c=self.s.case(c['id']);c['recipient']=email;c['routing_evidence']='Synthetic old source';self.s.save(c)
        r=self.call('desk_find_contacts',state='MI',county_ids=['county:26001'],roles=['public_records'])
        self.assertEqual(r['items'][0]['status'],'missing');self.assertEqual(len(r['case_leads']['county:26001']),1);self.assertFalse(r['case_leads']['county:26001'][0]['role_verified'])

    def test_research_workflow_does_not_read_mail_or_mutate_cases(self):
        with patch.object(self.s,'settings',side_effect=AssertionError('No mailbox access')),patch.object(self.s,'save',side_effect=AssertionError('No case edits')):
            b=self.create();t=self.claim(b)[0];self.finish(b,t)
        self.assertEqual(self.db.all('mail'),[]);self.assertEqual(self.db.all('case'),[]);self.assertEqual(self.db.all('issue'),[])


if __name__=='__main__': unittest.main()
