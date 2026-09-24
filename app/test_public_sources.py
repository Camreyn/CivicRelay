"""Synthetic contacts and mocked public HTTPS only. Never uses live mail/stores."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime
import public_sources as sources
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store, ConnectorError
from test_equipment import Protector

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)


def sample(html=False):
    rows=[]
    for i,name in enumerate(sources.roster()):
        if html:
            rows.append(f'<h2>{name}</h2><p>Address:<br>Town Clerk<br>Synthetic office</p><p>Email: <a href="mailto:office{i}@example.test">office{i}@example.test</a><br>Phone: 555-0100</p>')
        else:
            rows.append(f'## {name}\nAddress:\nTown Clerk\nSynthetic office\nEmail: office{i}@example.test\nPhone: 555-0100\n')
    return '\n'.join(rows)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='relay-sources-test-')
        root=Path(self.tmp.name)
        self.s=Service(Database(root/'desk',Protector()),mail_store=Store(root/'mail',Protector()))
        self.clock=patch('public_sources.now',return_value=NOW);self.clock.start()

    def tearDown(self):
        self.clock.stop();self.tmp.cleanup()

    def collect(self,text=None,day='2026-09-23'):
        return self.s.dispatch('desk_import_source',{'source_id':sources.SOURCE_ID,'checked_on':day,'text':sample() if text is None else text})

    def test_read_only_empty_inventory_and_all_gaps(self):
        with patch('public_sources.fetch_directory',side_effect=AssertionError('No network')):
            r=self.s.dispatch('desk_get_municipal_contacts',{'state':'MA'})
            self.assertEqual(r['coverage'],{'municipalities':351,'collected':0,'with_email':0,'designated_raos_verified':0})
            self.assertEqual(len(r['contacts']),50);self.assertEqual(r['next_offset'],50)
            self.assertEqual(r['contacts'][0]['evidence_status'],'not_collected')
            self.assertFalse(self.s.db.root.exists())

    def test_import_persists_evidence_and_never_reroutes(self):
        r=self.collect();self.assertTrue(r['ok']);self.assertEqual(r['collection_mode'],'reviewed_text_import')
        rows=self.s.dispatch('desk_get_municipal_contacts',{'state':'MA','query':'Abington'})['contacts']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['emails'],['office0@example.test'])
        self.assertEqual(rows[0]['source_url'],sources.SOURCE['url']);self.assertEqual(rows[0]['checked_on'],'2026-09-23')
        self.assertEqual(rows[0]['jurisdiction_level'],'municipality');self.assertFalse(rows[0]['routing_verified'])
        self.assertEqual(self.s.db.all('case'),[]);self.assertEqual(self.s.db.all('mail'),[])
        snap=self.s.db.all('source_snapshot')[0];self.assertEqual(snap['source_text'],sample());self.assertEqual(len(snap['sha256']),64)

    def test_html_and_plain_equivalent_and_ignores_scripts(self):
        self.assertEqual(sources.parse_directory(sample()),sources.parse_directory('<script>Email: fake@example.test</script>'+sample(True),html=True))

    def test_multiple_labeled_emails_not_selected_as_custodian(self):
        text=sample().replace('Email: office0@example.test','Email:\nGeneral inquiries: general@example.test\nVoting by mail: ballots@example.test')
        row=sources.parse_directory(text)[0]
        self.assertEqual(row['emails'],['general@example.test','ballots@example.test']);self.assertIn('Voting by mail',row['email_context'])
        self.assertFalse(row['routing_verified'])

    def test_missing_email_remains_explicit_gap(self):
        r=sources.parse_directory(sample().replace('Email: office0@example.test','Email:'))
        self.assertEqual(r[0]['emails'],[]);self.assertEqual(r[1]['emails'],['office1@example.test'])

    def test_partial_and_block_page_preserve_snapshot(self):
        self.collect();old=self.s.db.get('source',sources.SOURCE_ID)['snapshot_id']
        for text in ['Request unsuccessful. Incapsula',sample().split('## Acton')[0]]:
            r=self.collect(text);self.assertFalse(r['ok']);self.assertEqual(r['record_count'],351)
            self.assertEqual(self.s.db.get('source',sources.SOURCE_ID)['snapshot_id'],old)
        self.assertEqual(len(self.s.db.all('source_snapshot')),1)
        self.assertEqual(len(self.s.db.get('source',sources.SOURCE_ID)['history']),3)

    def test_duplicate_headings_rejected(self):
        r=self.collect(sample()+'\n## Abington\nEmail: another@example.test\n')
        self.assertEqual(r['code'],'duplicate_municipality');self.assertEqual(r['record_count'],0)

    def test_date_and_argument_validation(self):
        for day in ['2026-09-24','09-23-2026','20260923','',None]:
            with self.assertRaises(ConnectorError):self.collect(day=day)
        for operation,args in [('desk_refresh_source',{'source_id':'https://localhost'}),('desk_refresh_source',{'source_id':sources.SOURCE_ID,'url':'https://example.test'}),('desk_get_municipal_contacts',{'state':'MI'}),('desk_get_municipal_contacts',{'state':'MA','limit':True}),('desk_import_source',{'source_id':sources.SOURCE_ID,'checked_on':'2026-09-23','text':'bad\x00text'})]:
            self.assertFalse(safe_dispatch(operation,args,self.s)['ok'])

    def test_old_import_cannot_replace_newer_data(self):
        self.collect()
        with self.assertRaises(ConnectorError):self.collect(day='2026-09-22')
        self.assertEqual(len(self.s.db.all('source_snapshot')),1)

    def test_direct_refresh_and_private_history(self):
        with patch('public_sources.fetch_directory',return_value=(sample(True),1234)):
            r=self.s.dispatch('desk_refresh_source',{'source_id':sources.SOURCE_ID})
        self.assertTrue(r['ok']);self.assertEqual(r['collection_mode'],'direct_fetch')
        self.collect();self.assertEqual(len(self.s.db.all('source_snapshot')),2)
        self.assertNotIn('records',self.s.dispatch('desk_get_sources',{})['sources'][0])

    def test_failed_refresh_does_not_fake_success_timestamp(self):
        self.collect();previous=self.s.dispatch('desk_get_sources',{})['sources'][0]
        with patch('public_sources.fetch_directory',side_effect=sources.SourceError('source_timeout','Timed out')):
            r=self.s.dispatch('desk_refresh_source',{'source_id':sources.SOURCE_ID})
        self.assertFalse(r['ok']);self.assertEqual(r['last_success_at'],previous['last_success_at'])

    def test_stale_source_and_pagination(self):
        self.collect(day='2026-01-01')
        r=self.s.dispatch('desk_get_municipal_contacts',{'state':'MA','offset':350,'limit':25})
        self.assertEqual(len(r['contacts']),1);self.assertIsNone(r['next_offset']);self.assertTrue(r['source']['stale'])

    def test_history_limit_preserves_data(self):
        with patch('public_sources.MAX_HISTORY',1):
            self.collect()
            with self.assertRaises(ConnectorError):self.collect()
        self.assertEqual(len(self.s.db.all('source_snapshot')),1)

    def test_guides_explicit_availability_and_default_collapsed(self):
        ma=self.s.dispatch('desk_get_state_guide',{'state':'MA'})
        self.assertEqual(len(ma['guides']),2);self.assertTrue(ma['display']['default_collapsed'])
        self.assertTrue(ma['display']['automatic_on_state_selection']);self.assertFalse(ma['network_accessed'])
        self.assertTrue(self.s.dispatch('desk_get_state_guide',{'state':'MI'})['available'])
        self.assertFalse(self.s.dispatch('desk_get_state_guide',{'state':'AL'})['available'])
        self.assertIn('default_collapsed',self.s.dispatch('desk_get_workflow',{})['state_guides'])

    def test_fetch_does_not_follow_redirect_or_send_credentials(self):
        with patch('public_sources.http.client.HTTPSConnection') as connection:
            response=connection.return_value.getresponse.return_value;response.status=302
            with self.assertRaises(sources.SourceError) as caught:sources.fetch_directory()
            self.assertEqual(caught.exception.code,'source_redirect')
            args=connection.return_value.request.call_args
            self.assertEqual(args.args[0],'GET');self.assertEqual(args.args[1],'/divisions/elections/voter-resources/find-my-local-election-office.htm')
            self.assertNotIn('Authorization',args.kwargs['headers']);self.assertNotIn('Cookie',args.kwargs['headers'])
            connection.return_value.close.assert_called_once()

    def test_fetch_limits_type_size_and_private_diagnostics(self):
        for kind in ['type','size','network']:
            with patch('public_sources.http.client.HTTPSConnection') as connection:
                response=connection.return_value.getresponse.return_value;response.status=200
                response.getheader.side_effect=lambda k,d='':('application/json' if kind=='type' else 'text/html') if k=='Content-Type' else d
                response.read1.side_effect=[b'x'*(sources.MAX_BYTES+1)]
                if kind=='network':connection.return_value.request.side_effect=OSError('PRIVATE sentinel')
                with self.assertRaises(sources.SourceError) as caught:sources.fetch_directory()
                self.assertNotIn('PRIVATE',caught.exception.message)
                self.assertEqual(caught.exception.code,{'type':'content_type','size':'source_too_large','network':'source_unavailable'}[kind])


if __name__=='__main__':unittest.main()
