"""Synthetic optional-destination and local export regression tests; no network."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch
import runtime
import connector
import intake
from service import Service
from storage import Database
from secure_store import ConnectorError, Store, canonical

class Protector:
    def protect(self,value): return bytes(x^27 for x in canonical(value))
    def unprotect(self,value): return json.loads(bytes(x^27 for x in value))

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog=runtime.load_catalog()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='relay-integrations-synthetic-')
        self.root=Path(self.temp.name)
        self.db=Database(self.root/'desk',Protector());self.store=Store(self.root/'mail',Protector())
        self.service=Service(self.db,copy.deepcopy(self.catalog),self.store)
        self.case_id='source-IN-2024'
    def tearDown(self):self.temp.cleanup()
    def call(self,operation,**args):return self.service.dispatch(operation,args)
    def destination(self,**overrides):
        args={'name':'Synthetic handoff','repository':'example-org/records','template':'records.yml','enabled':True,'labels':['records'],
            'fields':[{'id':'summary','label':'Reviewed summary','type':'textarea','required':True,'options':[]},
                      {'id':'response_url','label':'Public records link','type':'input','required':False,'options':[]}]}
        return self.call('desk_save_destination',**(args|overrides))['destination']
    def prepared(self,**overrides):
        dest=self.destination()
        return self.call('desk_prepare_publication',case_id=self.case_id,destination_id=dest['id'],fields={'summary':'Synthetic reviewed summary'},**overrides)['issue']
    def test_local_only_default_no_destination_no_github_dependency(self):
        with patch('intake.run',side_effect=AssertionError('No network')):
            self.assertEqual(self.call('desk_list_destinations')['destinations'],[])
            result=self.call('desk_export_case',case_id=self.case_id)
        self.assertTrue(result['exported']);self.assertFalse(result['publicly_uploaded'])
        with zipfile.ZipFile(result['path']) as archive:
            self.assertIn('PRIVATE-request.json',archive.namelist())
            self.assertEqual(json.loads(archive.read('PRIVATE-request.json'))['id'],self.case_id)
            self.assertNotIn('PUBLIC-issue-preview.md',archive.namelist())
    def test_prepared_destination_is_bound_and_fields_not_copied_from_mail(self):
        issue=self.prepared()
        self.assertEqual(issue['repository'],'example-org/records')
        self.assertEqual(issue['target_snapshot']['template'],'records.yml')
        self.assertEqual(issue['digest'],intake.digest(issue))
        self.assertEqual(set(issue['fields']),{'summary','response_url'})
        self.assertFalse('state' in issue['fields']);self.assertIn('github.com/example-org/records',issue['form_url'])
        altered=copy.deepcopy(issue);altered['target_snapshot']['repository']='attacker/elsewhere'
        self.assertNotEqual(intake.digest(altered),issue['digest'])
    def test_destination_change_invalidates_prepared_preview_without_network(self):
        issue=self.prepared();target=issue['target_snapshot']
        definition={k:target[k] for k in ('name','repository','template','labels','enabled')}
        definition['fields']=[{k:f[k] for k in ('id','label','type','required','options')} for f in target['fields']]
        self.call('desk_save_destination',destination_id=target['id'],revision=target['revision'],**(definition|{'repository':'example-org/new-records'}))
        with patch('intake.run',side_effect=AssertionError('No network')):
            with self.assertRaisesRegex(ConnectorError,'destination changed'):
                intake.publish(self.db,self.catalog,issue['id'],issue['digest'])
        self.assertEqual(self.db.get('issue',issue['id'])['state'],'prepared')
    def test_publication_targets_exact_repo_and_remote_response_must_match(self):
        issue=self.prepared();calls=[]
        def runner(command,**kwargs):
            calls.append(command)
            self.assertIn('repos/example-org/records/issues',command)
            self.assertEqual(json.loads(kwargs['payload'])['body'],issue['body'])
            return SimpleNamespace(returncode=0,stdout=json.dumps({'html_url':'https://github.com/example-org/records/issues/3'}).encode())
        result=intake.publish(self.db,self.catalog,issue['id'],issue['digest'],runner)
        self.assertEqual(result['state'],'published');self.assertEqual(len(calls),1)
        with self.assertRaises(ConnectorError):intake.publish(self.db,self.catalog,issue['id'],issue['digest'],runner)
        self.assertEqual(len(calls),1)
    def test_wrong_repo_response_is_uncertain_not_retryable(self):
        issue=self.prepared()
        runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'{"html_url":"https://github.com/elsewhere/records/issues/3"}')
        result=intake.publish(self.db,self.catalog,issue['id'],issue['digest'],runner)
        self.assertEqual(result['state'],'uncertain')
        with self.assertRaisesRegex(ConnectorError,'unresolved'):
            self.call('desk_prepare_publication',case_id=self.case_id,destination_id=issue['destination_id'],fields={'summary':'Another summary'})
    def test_reconcile_published_old_target_after_configuration_change(self):
        issue=self.prepared();issue['state']='uncertain';self.db.put('issue',issue['id'],issue)
        dest=self.db.get('destination',issue['destination_id']);dest['enabled']=False;self.db.put('destination',dest['id'],dest)
        response={'html_url':'https://github.com/example-org/records/issues/7','title':issue['title'],'body':issue['body'],'labels':[{'name':'records'}]}
        runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(response).encode())
        result=intake.reconcile(self.db,issue['id'],response['html_url'],runner)
        self.assertEqual(result['state'],'published')
    def test_repository_field_and_header_injection_rejected(self):
        for repository in ['https://github.com/owner/repo','--hostname/evil','owner/repo/../../else','owner/repo?token=x','owner\n/repo']:
            with self.assertRaises(ConnectorError):self.destination(repository=repository)
        with self.assertRaises(ConnectorError):self.destination(template='../../form.yml')
        with self.assertRaises(ConnectorError):self.destination(labels=['good\nbad'])
        dest=self.destination()
        for fields in ({'summary':'From: private@example.org'},{'summary':'Reviewed','unknown':'extra'}):
            with self.assertRaises(ConnectorError):self.call('desk_prepare_publication',case_id=self.case_id,destination_id=dest['id'],fields=fields)
    def test_snapshot_export_hash_and_selected_file_ownership(self):
        content=b'Synthetic record only.';key='a'*64
        artifact={'id':key,'case_id':self.case_id,'filename':'../../record.txt','bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'content_type':'text/plain','message_id':'INBOX:1:1'}
        self.db.put('artifact',key,artifact);self.db.put('blob',key,{'base64':base64.b64encode(content).decode()})
        result=self.call('desk_export_case',case_id=self.case_id,artifact_ids=[key])
        self.assertEqual(hashlib.sha256(Path(result['path']).read_bytes()).hexdigest(),result['sha256'])
        with zipfile.ZipFile(result['path']) as archive:
            self.assertFalse(any('/../' in name or name.startswith('../') for name in archive.namelist()))
            entry=next(x for x in archive.namelist() if x.startswith('files/'))
            self.assertEqual(archive.read(entry),content)
        artifact['case_id']='some-other-case';self.db.put('artifact',key,artifact)
        with self.assertRaises(ConnectorError):self.call('desk_export_case',case_id=self.case_id,artifact_ids=[key])
    def test_destination_revision_required_and_no_template_configuration_shortcut(self):
        dest=self.destination()
        with self.assertRaisesRegex(ConnectorError,'revision'):
            self.destination(destination_id=dest['id'],revision=0)
        with self.assertRaises(ConnectorError):self.call('desk_save_destination',password='not-a-setting')
        with self.assertRaises(ConnectorError):self.destination(destination_id=dest['id'],revision=True)
        with self.assertRaises(ConnectorError):self.destination(destination_id=0)
        with self.assertRaises(ConnectorError):self.destination(labels=[{}])

if __name__=='__main__':unittest.main()
