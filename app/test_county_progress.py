"""Synthetic county status checks; no mail/network or live-store access."""
import copy
import json
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest.mock import patch

import runtime
import contacts
import county_progress
from secure_store import ConnectorError, Store
from service import Service
from storage import Database
from test_contacts import Protector


class CountyProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = runtime.load_catalog()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-county-progress-')
        self.s = Service(Database(Path(self.temp.name)/'desk',Protector()),copy.deepcopy(self.catalog),Store(Path(self.temp.name)/'mail',Protector()))
    def tearDown(self): self.temp.cleanup()
    def case(self, name='Alcona County', state='MI', level='county', **fields):
        c=self.s.dispatch('desk_create_equipment_request',{'state':state,'jurisdiction':name,'jurisdiction_level':level})['case']
        c=self.s.case(c['id']);c.update(fields);self.s.db.put('case',c['id'],c);return c
    def mail(self, c, key='INBOX:1:1', reviewed=False, conflict=False):
        m={'id':key,'case_id':c['id'],'folder':'INBOX','uid_validity':'1','uid':key.split(':')[-1],'read_in_desk':reviewed,'synced_at':time.time(),
           'thread_conflict':conflict,'message_id':f'<{key}@example.test>','subject':'Synthetic response',
           'from':'Synthetic Office <records@example.test>','to':'staff@example.test','date':'2026-09-21',
           'body_loaded':False,'attachment_count':0,'assignment':'manual'}
        self.s.db.put('mail',key,m);return m
    def overview(self, **args):
        return self.s.dispatch('desk_list_counties',{'state':'MI','include_requests':True,**args})['request_progress']
    def row(self, data, cid='county:26001'): return next(c for c in data['counties'] if c['id']==cid)
    def receipt(self, state='accepted'):
        return {'draft_id':'synthetic-draft','state':state,'message_id':'<synthetic-send@example.test>',
                'receipt':{'message_id':'<synthetic-send@example.test>','accepted_at':'2026-09-20T14:00:00+00:00'} if state=='accepted' else None,
                'in_reply_to':None}
    def test_complete_inventory_no_store_write(self):
        with patch('connector.dispatch',side_effect=AssertionError('No connector/network operation')):
            result=self.overview()
        self.assertEqual(len(result['counties']),83);self.assertEqual(result['counts']['without_requests'],83)
        self.assertEqual(self.row(result)['status'],'none');self.assertFalse(self.s.db.root.exists())
    def test_exact_jurisdiction_match_and_unmatched_remain_visible(self):
        self.case();self.case('State Office',level='state');self.case('Alcona County',level='municipality')
        self.case('Alcona County',state='WI');self.case('Alcona')
        self.case('Wrong canonical county',target={'id':'county:55001','label':'Alcona County','level':'county'})
        self.case('Canonical county ID',target={'id':'county:26003','label':'Operator label','level':'county'})
        r=self.overview();self.assertEqual(r['counts']['with_requests'],2)
        self.assertEqual(len(r['unmatched_county_requests']),2);self.assertEqual(len(r['other_jurisdiction_requests']),2)
        self.assertEqual(self.row(r)['request_count'],1);self.assertEqual(self.row(r,'county:26003')['request_count'],1)
    def test_waiting_requires_receipt_and_unknown_remains_locked(self):
        c=self.case(stage='waiting',routing_verified=True)
        self.assertEqual(self.row(self.overview())['status'],'draft')
        c['drafts']=['synthetic-draft'];self.s.db.put('case',c['id'],c)
        with patch.object(self.s.mail_store,'get_draft',return_value=self.receipt()):
            row=self.row(self.overview());self.assertEqual(row['status'],'waiting');self.assertEqual(row['send_confirmed_count'],1)
        with patch.object(self.s.mail_store,'get_draft',return_value=self.receipt('uncertain')):
            row=self.row(self.overview());self.assertEqual(row['status'],'uncertain');self.assertEqual(row['send_confirmed_count'],0)
    def test_replies_change_only_their_county_and_ack_is_not_complete(self):
        c=self.case();m=self.mail(c);c['tracking']={'response_stage':'acknowledged','response_message_id':m['id']};self.s.db.put('case',c['id'],c)
        statewide=self.case('State Office',level='state');self.mail(statewide,'INBOX:1:2')
        r=self.overview();self.assertEqual(self.row(r)['status'],'new');self.assertEqual(r['counts']['unread_replies'],1)
        self.assertEqual(self.row(r,'county:26003')['status'],'none')
        self.s.dispatch('desk_mark_reviewed',{'message_id':m['id']})
        self.assertEqual(self.row(self.overview())['status'],'acknowledged')
        saved=self.s.case(c['id']);saved['stage']='closed';self.s.db.put('case',saved['id'],saved)
        self.assertEqual(self.row(self.overview())['status'],'closed')
    def test_conflicts_and_missing_evidence_cannot_show_records_received(self):
        c=self.case(tracking={'response_stage':'records_received','response_message_id':'INBOX:1:9'})
        self.assertEqual(self.row(self.overview())['status'],'attention')
        self.mail(c,'INBOX:1:9',reviewed=True,conflict=True)
        self.assertEqual(self.row(self.overview())['status'],'attention')
        self.mail(c,'INBOX:1:9',reviewed=True,conflict=False)
        self.assertEqual(self.row(self.overview())['status'],'received')
    def test_multiple_requests_keep_individual_status_and_filters(self):
        c=self.case(stage='closed');other=copy.deepcopy(c);other.update(id='synthetic-second-request',stage='draft',routing_verified=True)
        self.s.db.put('case',other['id'],other)
        r=self.overview(workflow='equipment');row=self.row(r)
        self.assertEqual(row['status'],'draft');self.assertEqual(row['status_counts'],{'draft':1,'closed':1})
        self.assertEqual(len(row['requests']),2)
        self.assertEqual(self.overview(workflow='records')['counts']['requests'],0)
        self.assertEqual(self.overview(campaign_id='different-campaign')['counts']['requests'],0)
        self.assertEqual(self.overview(campaign_id='equipment-communications-2024')['counts']['requests'],2)
    def test_arguments_fail_closed_and_observation_is_readonly(self):
        c=self.case();before=self.s.db.get('case',c['id'])
        self.overview();self.assertEqual(self.s.db.get('case',c['id']),before)
        for args in ({'include_requests':True},{'state':'MI','include_requests':1},{'state':'MI','workflow':'all'},
                     {'state':'MI','include_requests':True,'workflow':'invalid'}):
            with self.assertRaises(ConnectorError):self.s.dispatch('desk_list_counties',args)
    def test_general_and_equipment_cases_stay_in_separate_workflows(self):
        c=self.case();generic=copy.deepcopy(c)
        generic.update(id='synthetic-generic-county',campaign_id='synthetic-campaign',general_campaign_id='synthetic-campaign',
                       target={'id':'county:26003','state':'MI','level':'county','label':'Alger County'})
        self.s.db.put('case',generic['id'],generic)
        r=self.overview(workflow='general');self.assertEqual(r['counts']['requests'],1)
        self.assertEqual(self.row(r)['request_count'],0);self.assertEqual(self.row(r,'county:26003')['request_count'],1)
        self.assertEqual(self.overview(workflow='equipment')['counts']['requests'],1)
        self.assertEqual(self.overview()['counts']['requests'],2)
    def test_public_geometry_matches_every_inventory_id(self):
        asset=Path(__file__).parent/'static/county-map.json';raw=asset.read_bytes();self.assertLess(len(raw),2_000_000)
        data=json.loads(raw);rows=[c for group in data['states'].values() for c in group]
        expected={c['id'] for c in contacts.inventory()['counties']}
        self.assertEqual({c['id'] for c in rows},expected);self.assertEqual(len(rows),3144)
        self.assertEqual(len(data['states']['MI']),83);self.assertEqual(data['geometry_count'],3144)
        self.assertTrue(data['source_url'].startswith('https://www2.census.gov/'))
        for row in rows:
            self.assertRegex(row['path'],r'^M[MLZ0-9.,]+Z$')
            coordinates=[float(x) for x in re.findall(r'\d+(?:\.\d+)?',row['path'])]
            self.assertTrue(all(0<=x<=900 for x in coordinates))


def seed_browser(service):
    """Persist synthetic county requests for the actual HTTP/browser story."""
    drafts={}
    rows=[('Alcona County','routing'),('Alger County','waiting'),('Allegan County','new'),
          ('Alpena County','partial_response'),('Antrim County','acknowledged'),('Arenac County','records_received')]
    created={}
    for index,(name,status) in enumerate(rows,1):
        view=service.dispatch('desk_create_equipment_request',{'state':'MI','jurisdiction':name,'jurisdiction_level':'county'})['case']
        c=service.case(view['id']);c['family_label']='Synthetic request / '+name;c['recipient']='records@example.test'
        c['routing_verified']=status!='routing';c['stage']='draft'
        if status=='waiting':
            key='synthetic-'+c['id'];c['drafts']=[key];c['stage']='waiting'
            drafts[key]={'draft_id':key,'state':'accepted','message_id':'<county-waiting@example.test>',
                         'receipt':{'message_id':'<county-waiting@example.test>','accepted_at':'2026-09-20T12:00:00+00:00'},'in_reply_to':None}
        if status in ('new','partial_response','acknowledged','records_received'):
            mid=f'INBOX:1:{index}';service.db.put('mail',mid,{'id':mid,'case_id':c['id'],'folder':'INBOX','uid_validity':'1','uid':str(index),'read_in_desk':status!='new',
                'synced_at':time.time(),'message_id':'<'+mid+'@example.test>','from':'records@example.test','to':'staff@example.test',
                'subject':'Synthetic reply','date':'2026-09-21','body_loaded':False,'assignment':'manual','attachment_count':0})
            c['tracking']={'response_stage':'acknowledged' if status=='new' else status,'response_message_id':mid}
        service.db.put('case',c['id'],c);created[name]=c['id']
    for name,level in [('Synthetic state office','state'),('Unmatched synthetic county','county')]:
        c=service.dispatch('desk_create_equipment_request',{'state':'MI','jurisdiction':name,'jurisdiction_level':level})['case'];created[name]=c['id']
    original=service.mail_store.get_draft
    service.mail_store.get_draft=lambda key:drafts[key] if key in drafts else original(key)
    return created


if __name__=='__main__':unittest.main()
