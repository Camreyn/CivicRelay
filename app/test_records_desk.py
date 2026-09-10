"""Synthetic-only regression tests: never use real mail, account secrets, or GitHub writes."""
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
import base64
import copy
import hashlib
import http.client
import json
import tempfile
import threading
import time
import unittest
import zipfile
from unittest.mock import patch
import runtime
from secure_store import ConnectorError,Store,canonical
from storage import Database
from service import Service,safe_dispatch
import connector
import intake
import mailbox

class TestProtector:
    def protect(self,value):return bytes(x^127 for x in canonical(value))
    def unprotect(self,value):return json.loads(bytes(x^127 for x in value))

def mail(key='INBOX:1:1',mid='<received@example.gov>',reply='',case=None,assignment=None):
    folder,epoch,uid=key.split(':')
    return {'id':key,'folder':folder,'uid_validity':int(epoch),'uid':int(uid),'message_id':mid,
            'in_reply_to':reply,'references':'','from':'Records <records@example.gov>','to':connector.PROJECT_EMAIL,
            'date':'Wed, 09 Sep 2026 12:00:00 +0000','subject':'Synthetic records response','case_id':case,
            'assignment':assignment,'synced_at':time.time(),'body_loaded':False,'read_in_desk':False}

class DeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=runtime.load_catalog()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='records-desk-synthetic-')
        self.root=Path(self.temp.name);self.db=Database(self.root/'desk',TestProtector())
        self.store=Store(self.root/'mail',TestProtector())
        self.settings={'version':1,'email':connector.PROJECT_EMAIL,'password':'synthetic-never-a-real-credential',
            'imap_port':1143,'smtp_port':1025,'imap_pin':'1'*64,'smtp_pin':'2'*64,'sending_enabled':True,'project_mailbox_confirmed':True}
        self.store.save_settings(self.settings)
        self.service=Service(self.db,copy.deepcopy(self.catalog),self.store)
        self.case_id='source-IN-2024'
    def tearDown(self):self.temp.cleanup()
    def call(self,name,**args):return self.service.dispatch(name,args)
    def ready_case(self):
        c=self.service.case(self.case_id)
        return self.call('desk_save_case',case_id=c['id'],revision=c['revision'],recipient='records@example.gov',subject='Synthetic request',
            body='Synthetic request from Example Requester. Please provide a fee estimate before processing.',
            routing_verified=True,routing_evidence='https://example.gov/records',note='')['case']
    def fields(self):return {'state':'Indiana (IN)','request_id':'SR-2024-IN-PRECINCT-SUBCOUNTY-ROWS','custodian':'Synthetic Records Office',
            'response_date':'2026-09-09','response_status':'Records received','response_url':'','files_received':'',
            'response_summary':'Synthetic response for testing only.','follow_up_needed':''}
    def prepare_issue(self,artifacts=None):return self.call('desk_prepare_intake',case_id=self.case_id,fields=self.fields(),artifact_ids=artifacts or [])['issue']
    def test_catalog_uses_reviewed_snapshot_and_exact_public_form(self):
        self.assertEqual(len(self.catalog['states']),51);self.assertEqual(len(self.catalog['cases']),14)
        self.assertEqual(len({c['state'] for c in self.catalog['cases']}),13)
        self.assertEqual({f['id'] for f in self.catalog['issue']['fields']},{'state','request_id','custodian','response_date','response_status','response_url','files_received','response_summary','follow_up_needed','responsible_review'})
        self.assertEqual(self.catalog['issue']['template'],'records-response.yml')
        self.assertIn('[requester name]',self.catalog['cases'][0]['body'])
    def test_read_only_listing_creates_no_database(self):
        self.assertEqual(len(self.call('desk_list_cases')['catalog']['cases']),14)
        self.assertFalse(self.db.root.exists())
    def test_standalone_storage_rejects_another_git_checkout(self):
        other=self.root/'other-checkout';other.mkdir();(other/'.git').mkdir()
        database=Database(other/'CivicResultMaps'/'RecordsDesk',TestProtector())
        with self.assertRaisesRegex(ConnectorError,'Git working tree'):database.guard()
        self.assertFalse(database.root.exists())
    def test_workflow_returns_exact_form_and_no_private_database_write(self):
        r=self.call('desk_get_workflow')
        self.assertEqual(r['intake'],self.catalog['issue']);self.assertEqual(len(r['states']),51)
        self.assertFalse(r['network_accessed']);self.assertFalse(r['production_import'])
        self.assertFalse(self.db.root.exists())
    def test_saved_header_pagination_filters_and_excludes_bodies(self):
        # Synthetic in-memory headers avoid a large on-disk fixture.
        rows=[mail(f'INBOX:1:{i+1}',case=self.case_id if i==0 else None) for i in range(205)]
        for i,m in enumerate(rows):m.update(synced_at=i,body='Private body must not be returned',attachments=['not a header'])
        rows[-1]['read_in_desk']=True
        with patch.object(self.db,'all',side_effect=lambda kind:rows if kind=='mail' else []):
            first=self.call('desk_list_messages',case_id='',limit=100,unreviewed_only=True)
            second=self.call('desk_list_messages',case_id='',limit=100,unreviewed_only=True,before_message_id=first['next_before_message_id'])
            last=self.call('desk_list_messages',case_id='',limit=100,unreviewed_only=True,before_message_id=second['next_before_message_id'])
            all_ids=[m['id'] for page in [first,second,last] for m in page['messages']]
            self.assertEqual(len(all_ids),203);self.assertEqual(len(set(all_ids)),203);self.assertIsNone(last['next_before_message_id'])
            self.assertNotIn('body',first['messages'][0]);self.assertNotIn('attachments',first['messages'][0]);self.assertFalse(first['network_accessed'])
            assigned=self.call('desk_list_messages',case_id=self.case_id)
            self.assertEqual([m['id'] for m in assigned['messages']],['INBOX:1:1'])
            with self.assertRaises(ConnectorError):self.call('desk_list_messages',case_id='',before_message_id='INBOX:1:1')
        for args in [{'limit':True},{'limit':101},{'unreviewed_only':'yes'},{'folder':'Drafts'},{'case_id':None}]:
            with self.assertRaises(ConnectorError):self.call('desk_list_messages',**args)
    def test_read_saved_intake_by_id_without_publication(self):
        issue=self.prepare_issue()
        with patch('intake.run',side_effect=AssertionError('Network forbidden')):
            r=self.call('desk_get_intake',issue_id=issue['id'])
        self.assertEqual(r['issue']['digest'],issue['digest']);self.assertFalse(r['network_accessed'])
        with self.assertRaises(ConnectorError):self.call('desk_get_intake',issue_id='missing')
    def test_encrypted_restart_and_no_plaintext(self):
        c=self.ready_case();restarted=Database(self.db.root,TestProtector())
        self.assertEqual(restarted.get('case',self.case_id)['body'],c['body'])
        raw=(self.db.root/'records.sqlite3').read_bytes()
        self.assertNotIn(b'records@example.gov',raw);self.assertNotIn(b'Example Requester',raw)
    def test_inner_identity_mismatch_rejected(self):
        with self.assertRaises(ConnectorError):self.db.put('case','one',{'id':'two'})
    def test_mutation_lease_serializes_processes(self):
        with self.db.operation():
            with self.assertRaises(ConnectorError):
                with Database(self.db.root,TestProtector()).operation():pass
        with self.db.operation():pass
    def test_stale_case_revision_rejected(self):
        self.ready_case()
        with self.assertRaises(ConnectorError):self.call('desk_save_case',case_id=self.case_id,revision=0)
    def test_no_routing_no_draft(self):
        with self.assertRaises(ConnectorError):self.call('desk_prepare_email',case_id=self.case_id)
    def test_expired_routing_and_catalog_drift_block(self):
        self.ready_case();c=self.service.case(self.case_id);c['routing_verified_at']=0;self.db.put('case',c['id'],c)
        with self.assertRaises(ConnectorError):self.call('desk_prepare_email',case_id=self.case_id)
        self.ready_case();self.service.catalog['sha256']='changed'
        with self.assertRaises(ConnectorError):self.call('desk_prepare_email',case_id=self.case_id)
    def test_clone_clears_mail_and_verification(self):
        self.ready_case();c=self.service.case(self.case_id);c.update(latest_send_state='accepted',drafts=['fake'],issues=['fake']);self.db.put('case',c['id'],c)
        clone=self.call('desk_clone_case',case_id=self.case_id,label='Example County')['case']
        self.assertEqual(clone['drafts'],[]);self.assertFalse(clone['routing_verified']);self.assertNotIn('latest_send_state',clone)
    def test_draft_is_immutable_and_deduplicated(self):
        self.ready_case();one=self.call('desk_prepare_email',case_id=self.case_id)['draft'];two=self.call('desk_prepare_email',case_id=self.case_id)['draft']
        self.assertEqual(one['draft_id'],two['draft_id']);self.assertEqual(one['state'],'draft')
    def test_cancelled_send_never_authenticates_or_sends(self):
        self.ready_case();d=self.call('desk_prepare_email',case_id=self.case_id)['draft']
        with patch('desktop.confirm_send',return_value=False),patch('bridge.smtp_connection',side_effect=AssertionError('Network forbidden')):
            r=self.call('desk_send_email',case_id=self.case_id,draft_id=d['draft_id'],expected_digest=d['digest'],confirmation='SEND_REVIEWED_EMAIL')
        self.assertEqual(r['messages_sent'],0);self.assertEqual(self.store.get_draft(d['draft_id'])['state'],'draft')
    def test_send_preflight_marker_for_stale_content_and_connector_checks(self):
        self.ready_case();d=self.call('desk_prepare_email',case_id=self.case_id)['draft']
        args=dict(case_id=self.case_id,draft_id=d['draft_id'],expected_digest=d['digest'],confirmation='SEND_REVIEWED_EMAIL')
        with patch('desktop.confirm_send',side_effect=AssertionError('Approval forbidden')),patch('bridge.smtp_connection',side_effect=AssertionError('Network forbidden')):
            bad_digest=safe_dispatch('desk_send_email',{**args,'expected_digest':'0'*64},self.service)
            self.assertFalse(bad_digest['ok']);self.assertTrue(bad_digest['send_not_started'])
            with patch.object(self.store,'send_window',return_value={'ready':False,'retry_after_seconds':60}):
                cooldown=safe_dispatch('desk_send_email',args,self.service)
            self.assertFalse(cooldown['ok']);self.assertTrue(cooldown['send_not_started'])
            c=self.service.case(self.case_id);c['body']='Changed synthetic content';self.db.put('case',c['id'],c)
            stale=safe_dispatch('desk_send_email',args,self.service)
            self.assertFalse(stale['ok']);self.assertTrue(stale['send_not_started'])
        self.assertEqual(self.store.get_draft(d['draft_id'])['state'],'draft')
    def test_post_approval_and_receipt_failures_are_not_marked_preflight(self):
        self.ready_case();d=self.call('desk_prepare_email',case_id=self.case_id)['draft']
        args=dict(case_id=self.case_id,draft_id=d['draft_id'],expected_digest=d['digest'],confirmation='SEND_REVIEWED_EMAIL')
        with patch('desktop.confirm_send',return_value=True),patch.object(self.store,'claim_send',side_effect=ConnectorError('Synthetic concurrent attempt')),patch('bridge.smtp_connection',side_effect=AssertionError('Network forbidden')):
            race=safe_dispatch('desk_send_email',args,self.service)
        self.assertFalse(race['ok']);self.assertNotIn('send_not_started',race)
        with patch('connector.dispatch',return_value={'state':'accepted'}),patch.object(self.service,'reconcile_sends',side_effect=ConnectorError('Synthetic receipt refresh failure')):
            receipt=safe_dispatch('desk_send_email',args,self.service)
        self.assertFalse(receipt['ok']);self.assertNotIn('send_not_started',receipt)
    def test_success_and_duplicate_send_blocked(self):
        self.ready_case();d=self.call('desk_prepare_email',case_id=self.case_id)['draft'];wire=[]
        smtp=SimpleNamespace(mail=lambda _: (250,b''),rcpt=lambda _:(250,b''),data=lambda b:(wire.append(b) or (250,b'')))
        @contextmanager
        def connection(_):yield smtp
        args=dict(case_id=self.case_id,draft_id=d['draft_id'],expected_digest=d['digest'],confirmation='SEND_REVIEWED_EMAIL')
        with patch('desktop.confirm_send',return_value=True),patch('bridge.smtp_connection',connection):
            self.assertEqual(self.call('desk_send_email',**args)['state'],'accepted')
            with self.assertRaises(ConnectorError):self.call('desk_send_email',**args)
        self.assertEqual(len(wire),1);self.assertEqual(self.service.case(self.case_id)['stage'],'waiting')
        with self.assertRaises(ConnectorError):self.call('desk_prepare_email',case_id=self.case_id)
    def test_reply_headers_preserve_chain(self):
        self.ready_case();m=mail(case=self.case_id,assignment='manual');m['references']='<ancestor@example.gov>';self.db.put('mail',m['id'],m)
        d=self.call('desk_prepare_email',case_id=self.case_id,reply_message_id=m['id'])['draft']
        self.assertEqual(d['in_reply_to'],m['message_id']);self.assertEqual(d['references'],['<ancestor@example.gov>',m['message_id']])
    def test_thread_does_not_guess_by_subject(self):
        m=mail();mailbox.reconcile_threads([m],[('<sent@proton.me>',self.case_id)])
        self.assertIsNone(m['case_id'])
    def test_sent_message_can_anchor_followup(self):
        self.ready_case();m=mail('Sent:1:1',mid='<sent@proton.me>',case=self.case_id,assignment='manual');self.db.put('mail',m['id'],m)
        draft=self.call('desk_prepare_email',case_id=self.case_id,reply_message_id=m['id'])['draft']
        self.assertEqual(draft['in_reply_to'],m['message_id'])
    def test_exact_thread_and_late_conflict_clear_old_assignment(self):
        m=mail(reply='<a@proton.me>');messages=[m]
        mailbox.reconcile_threads(messages,[('<a@proton.me>','one')]);self.assertEqual(m['case_id'],'one')
        late=mail('INBOX:1:2',mid='<other@example.gov>',reply='<a@proton.me>',case='two',assignment='manual');messages.append(late)
        mailbox.reconcile_threads(messages,[('<a@proton.me>','one')]);self.assertIsNone(m['case_id']);self.assertTrue(m['thread_conflict']);self.assertEqual(late['case_id'],'two')
    def test_epoch_ids_are_distinct(self):
        self.assertNotEqual(mailbox.message_key('INBOX',1,1),mailbox.message_key('INBOX',2,1))
    def test_new_mail_status_and_review_flag(self):
        m=mail(case=self.case_id,assignment='manual');self.db.put('mail',m['id'],m)
        self.assertEqual(self.call('desk_get_case',case_id=self.case_id)['case']['status'],'new')
        r=self.call('desk_mark_reviewed',message_id=m['id']);self.assertFalse(r['proton_read_flag_changed'])
        self.assertEqual(self.call('desk_get_case',case_id=self.case_id)['case']['status'],'attention')
    def test_case_messages_are_paginated(self):
        for i in range(35):
            m=mail(f'INBOX:1:{i+1}',mid=f'<m{i}@example.gov>',case=self.case_id,assignment='manual');m['synced_at']=i;self.db.put('mail',m['id'],m)
        first=self.call('desk_get_case',case_id=self.case_id);self.assertEqual(len(first['messages']),30)
        second=self.call('desk_get_case',case_id=self.case_id,before_message_id=first['next_before_message_id']);self.assertEqual(len(second['messages']),5)
    def test_capture_retains_original_bytes_and_safe_provenance(self):
        m=mail(case=self.case_id,assignment='manual');message=EmailMessage();message['Message-ID']=m['message_id'];message.set_content('Synthetic response');message.add_attachment(b'a,b\n1,2\n',maintype='text',subtype='csv',filename='../../sample.csv');raw=message.as_bytes()
        artifacts=mailbox.capture(self.db,m,raw);a=artifacts[0]
        self.assertEqual(a['sha256'],hashlib.sha256(b'a,b\n1,2\n').hexdigest());self.assertFalse(a['executed']);self.assertTrue(a['quarantined'])
        self.assertEqual(base64.b64decode(self.db.get('blob',a['id'])['base64']),b'a,b\n1,2\n')
        self.assertFalse((self.root/'sample.csv').exists())
    def test_intake_missing_required_field_blocked(self):
        fields=self.fields();fields['custodian']=''
        with self.assertRaises(ConnectorError):self.call('desk_prepare_intake',case_id=self.case_id,fields=fields)
    def test_public_https_url_is_not_mistaken_for_windows_path(self):
        fields=self.fields();fields['response_url']='https://example.gov/records.csv'
        issue=self.call('desk_prepare_intake',case_id=self.case_id,fields=fields)['issue']
        self.assertIn(fields['response_url'],issue['body'])
    def captured_issue(self):
        m=mail(case=self.case_id,assignment='manual');eml=EmailMessage();eml['Message-ID']=m['message_id'];eml.set_content('Synthetic response');eml.add_attachment(b'one,two\n1,2\n',maintype='text',subtype='csv',filename='../../fixture.csv')
        artifact=mailbox.capture(self.db,m,eml.as_bytes())[0]
        return artifact,self.prepare_issue([artifact['id']])
    def test_reassigned_artifact_blocks_publication(self):
        artifact,issue=self.captured_issue();artifact['case_id']='different-case';self.db.put('artifact',artifact['id'],artifact)
        with self.assertRaises(ConnectorError):intake.require_prepared(self.db,issue['id'],issue['digest'],self.catalog)
    def test_export_requires_approval_and_uses_safe_zip_entries(self):
        artifact,issue=self.captured_issue()
        self.assertFalse(intake.export_package(self.db,issue,confirm=lambda *_:False)['exported'])
        self.assertFalse((self.db.root/'Exports').exists())
        result=intake.export_package(self.db,issue,confirm=lambda *_:True);target=Path(result['path'])
        self.assertTrue(target.is_relative_to(self.db.root/'Exports'));self.assertFalse(result['publicly_uploaded'])
        with zipfile.ZipFile(target) as archive:
            for name in archive.namelist():self.assertNotIn('..',Path(name).parts)
            entries=[n for n in archive.namelist() if n.startswith('files/')];self.assertEqual(len(entries),1)
            self.assertEqual(archive.read(entries[0]),b'one,two\n1,2\n')
        self.assertFalse(list(target.parent.glob('*.partial')))
    def test_intake_rejects_private_paths_credentials_bidi(self):
        for value in ['C:\\Users\\someone\\private.csv','password=private-marker','text\u202etest']:
            fields=self.fields();fields['response_summary']=value
            with self.assertRaises(ConnectorError):self.call('desk_prepare_intake',case_id=self.case_id,fields=fields)
    def test_private_and_signed_urls_rejected(self):
        for url in ['http://example.gov','https://127.0.0.1/a','https://10.0.0.1/a','https://agency.internal/a','https://example.gov/?%74oken=secret','https://user:pass@example.gov/a']:
            with self.assertRaises(ConnectorError):intake.safe_url(url)
        self.assertEqual(intake.safe_url('https://example.gov/records.csv'),'https://example.gov/records.csv')
    def test_issue_template_headings_and_deduplication(self):
        issue=self.prepare_issue();again=self.prepare_issue();self.assertEqual(issue['id'],again['id'])
        for label in ['State or jurisdiction','Responding office or custodian','Response status','Responsible records checklist']:self.assertIn('### '+label,issue['body'])
        self.assertIn('template=records-response.yml',issue['form_url']);self.assertEqual(issue['labels'],['records-request','data-review'])
    def test_issue_cancelled_no_publication(self):
        issue=self.prepare_issue()
        r=intake.publish(self.db,self.catalog,issue['id'],issue['digest'],confirm=lambda *_:False,runner=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Network forbidden')))
        self.assertFalse(r['published']);self.assertEqual(r['state'],'prepared')
    def test_uncertain_issue_cannot_be_reissued(self):
        issue=self.prepare_issue();calls=[]
        def fail(*a,**k):calls.append(1);raise TimeoutError()
        r=intake.publish(self.db,self.catalog,issue['id'],issue['digest'],confirm=lambda *_:True,runner=fail)
        self.assertEqual(r['state'],'uncertain')
        with self.assertRaises(ConnectorError):self.prepare_issue()
        with self.assertRaises(ConnectorError):intake.publish(self.db,self.catalog,issue['id'],issue['digest'],confirm=lambda *_:True,runner=fail)
        self.assertEqual(len(calls),1)
    def test_issue_success_receipt_and_no_duplicate_publication(self):
        issue=self.prepare_issue();commands=[]
        def runner(args,**kwargs):commands.append((args,kwargs));return SimpleNamespace(returncode=0,stdout=json.dumps({'html_url':'https://github.com/Camreyn/civicresultmaps/issues/123'}).encode())
        r=intake.publish(self.db,self.catalog,issue['id'],issue['digest'],confirm=lambda *_:True,runner=runner)
        self.assertTrue(r['published']);self.assertEqual(len(commands),1);self.assertIn('--input',commands[0][0]);self.assertNotIn(issue['body'],commands[0][0])
        with self.assertRaises(ConnectorError):intake.publish(self.db,self.catalog,issue['id'],issue['digest'],confirm=lambda *_:True,runner=runner)
    def test_weak_issue_match_rejected(self):
        issue=self.prepare_issue()
        def runner(*a,**k):return SimpleNamespace(returncode=0,stdout=json.dumps({'title':issue['title'],'body':'Somewhere Indiana (IN) '+issue['fields']['request_id'],'labels':[{'name':n} for n in issue['labels']]}).encode())
        with self.assertRaises(ConnectorError):intake.reconcile(self.db,issue['id'],'https://github.com/Camreyn/civicresultmaps/issues/123',runner)
    def test_unexpected_operation_arguments_blocked(self):
        with self.assertRaises(ConnectorError):self.call('desk_status',password='not allowed')
        with self.assertRaises(ConnectorError):self.call('delete_everything')
    def test_portal_receipt_is_user_attested_not_automatic(self):
        r=self.call('desk_record_portal',case_id=self.case_id,tracking_reference='SYNTHETIC-1',submitted_date='2026-09-09')
        self.assertFalse(r['portal_submitted_by_tool']);self.assertEqual(r['case']['stage'],'waiting')

class HttpTests(unittest.TestCase):
    def test_host_origin_cookie_and_mutation_guards(self):
        import server
        original=(server.PORT,server.ORIGIN)
        httpd=server.Server(('127.0.0.1',0),server.Handler);port=httpd.server_address[1]
        server.PORT=port;server.ORIGIN=f'http://127.0.0.1:{port}'
        thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
        def request(path='/',headers=None,method='GET',body=None):
            con=http.client.HTTPConnection('127.0.0.1',port,timeout=5);con.request(method,path,body=body,headers=headers or {});r=con.getresponse();raw=r.read();result=(r.status,dict(r.getheaders()),raw);con.close();return result
        try:
            code,_,body=request('/health');health=json.loads(body)
            self.assertEqual(code,200);self.assertEqual(health['distribution'],'civic-records-desk')
            self.assertEqual(health['installation_id'],hashlib.sha256(str(server.ROOT.parent).lower().encode()).hexdigest())
            self.assertEqual(request(headers={'Host':'attacker.example'})[0],403)
            self.assertEqual(request('/api/bootstrap')[0],403)
            self.assertEqual(request(headers={'Origin':'https://evil.example'})[0],403)
            code,headers,_=request();self.assertEqual(code,200);cookie=headers['Set-Cookie'].split(';')[0]
            self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            with patch('server.invoke',return_value={'ok':True,'result':{'synthetic':True}}) as mocked:
                self.assertEqual(request('/api/bootstrap',{'Cookie':cookie})[0],200)
                payload=json.dumps({'tool':'desk_status','arguments':{}})
                self.assertEqual(request('/api/operation',{'Cookie':cookie,'Content-Type':'application/json'},'POST',payload)[0],403)
                self.assertEqual(request('/api/operation',{'Cookie':cookie,'Content-Type':'application/json','X-Records-Desk':'1','Origin':server.ORIGIN},'POST',payload)[0],200)
                self.assertEqual(mocked.call_count,2)
        finally:httpd.shutdown();httpd.server_close();thread.join();server.PORT,server.ORIGIN=original

if __name__=='__main__':unittest.main(verbosity=2)
