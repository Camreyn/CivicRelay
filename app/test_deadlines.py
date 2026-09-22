"""Source-linked planning-clock tests. Synthetic records only, no network or real store."""
import copy
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime
import deadlines as d
from service import Service
from secure_store import ConnectorError, Store
from storage import Database
from test_equipment import Protector

NOW = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)


class CalendarTests(unittest.TestCase):
    def test_weekends_holidays_and_year_boundary(self):
        self.assertEqual(d.add_business_days(date(2026, 9, 4), 1), date(2026, 9, 8))
        self.assertEqual(d.add_business_days(date(2021, 12, 30), 1), date(2022, 1, 3))
        self.assertEqual(d.add_business_days(date(2026, 6, 18), 1), date(2026, 6, 22))
        self.assertEqual(d.add_business_days(date(2026, 9, 18), 1, ['2026-09-21']), date(2026, 9, 22))

    def test_recipient_local_day_not_utc_day(self):
        self.assertEqual(d.local_date('2026-09-14T00:33:00+00:00','Eastern'), date(2026,9,13))
        self.assertEqual(d.local_date('2026-09-20T04:30:00+00:00','Central'), date(2026,9,19))
        self.assertEqual(d.local_date('2026-01-20T04:30:00+00:00','Eastern'), date(2026,1,19))
        self.assertEqual(d.local_date('2026-07-20T04:30:00+00:00','Eastern'), date(2026,7,20))
        self.assertEqual(d.local_date('2026-07-20T06:30:00+00:00','Arizona'), date(2026,7,19))
        with self.assertRaises(ValueError): d.local_date('2026-09-20T12:00:00','Eastern')

    def test_rule_registry_is_sourced_and_bounded(self):
        r=d.registry();self.assertEqual(len(r['rules']),14)
        for code,rule in r['rules'].items():
            self.assertTrue(rule['citation']);self.assertTrue(rule['summary'])
            self.assertEqual(d.public_url(rule['url']),rule['url'])
            self.assertIn(rule['receipt_rule'],('same','next_open','email_next'))
            self.assertIn(rule['zone'],d.ZONES)
        self.assertEqual(r['rules']['IN']['unit'],'calendar')
        for code in ('WI','NC','AZ'): self.assertIsNone(r['rules'][code]['days'])


class DeadlineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='relay-deadline-synthetic-')
        root=Path(self.temp.name)
        self.db=Database(root/'desk',Protector())
        self.store=Store(root/'mail',Protector())
        self.s=Service(self.db,copy.deepcopy(runtime.load_catalog()),self.store)
        self.drafts={}
        def get_draft(key):
            if key not in self.drafts: raise ConnectorError('Synthetic draft missing.')
            return self.drafts[key]
        self.store.get_draft=get_draft
        self.clock=patch('deadlines.utcnow',return_value=NOW);self.clock.start()

    def tearDown(self):
        self.clock.stop();self.temp.cleanup()

    def case(self,state='MI',sent='2026-09-09T21:52:00+00:00',level='state'):
        c=self.s.dispatch('desk_create_equipment_request',{'state':state,'jurisdiction':'Synthetic records office','jurisdiction_level':level})['case']
        c=self.s.case(c['id']);c.update(routing_verified=True,routing_evidence='https://example.gov/records',recipient='records@example.test')
        if sent:
            key='initial-'+c['id'];mid='<'+state+'@example.test>'
            self.drafts[key]={'state':'accepted','message_id':mid,'receipt':{'message_id':mid,'accepted_at':sent},'in_reply_to':None}
            c['drafts']=[key];c['stage']='waiting'
        self.s.save(c);return c

    def row(self,c): return self.s.dispatch('desk_get_deadlines',{'case_id':c['id']})['cases'][0]
    def save(self,c,**args):
        return self.s.dispatch('desk_save_deadline_tracking',{'case_id':c['id'],'revision':self.s.case(c['id'])['revision'],**args})['case']
    def mail(self,c,key='INBOX:1:1'):
        folder,epoch,uid=key.split(':')
        m={'id':key,'folder':folder,'uid_validity':int(epoch),'uid':int(uid),'case_id':c['id'],'synced_at':NOW.timestamp(),'read_in_desk':False,'subject':'Synthetic notice'}
        self.db.put('mail',key,m);return m

    def test_empty_overview_is_read_only(self):
        with patch('connector.dispatch',side_effect=AssertionError('No mail')):
            r=self.s.dispatch('desk_get_deadlines',{})
        self.assertEqual(r['cases'],[]);self.assertFalse(self.db.root.exists())
        self.assertFalse(r['automatic_mail_polling']);self.assertFalse(r['automatic_sends']);self.assertTrue(r['mail_stale'])

    def test_michigan_email_clock(self):
        c=self.case();before=self.db.get('case',c['id'])
        r=self.row(c)
        self.assertEqual(r['receipt_date'],'2026-09-10');self.assertEqual(r['due_date'],'2026-09-17')
        self.assertEqual(r['status'],'overdue');self.assertEqual(r['label'],'Potentially overdue')
        self.assertFalse(r['legal_violation_determined']);self.assertEqual(r['checks'][0]['confidence'],'estimate')
        self.assertEqual(self.db.get('case',c['id']),before)

    def test_sunday_evening_utc_rollover(self):
        for state,expected in [('MI','2026-09-21'),('PA','2026-09-21'),('MA','2026-09-28'),('TX','2026-09-28')]:
            with self.subTest(state=state):
                r=self.row(self.case(state,'2026-09-14T00:33:00+00:00'))
                self.assertEqual(r['receipt_date'],'2026-09-14');self.assertEqual(r['due_date'],expected)
        self.assertIn('checkpoint',self.row(self.case('TX','2026-09-14T00:33:00+00:00'))['rule']['label'].lower())

    def test_followup_never_restarts_clock(self):
        c=self.case();original=self.row(c)['due_date']
        self.drafts['followup']={'state':'accepted','message_id':'<followup@example.test>','receipt':{'message_id':'<followup@example.test>','accepted_at':'2026-09-19T12:00:00+00:00'},'in_reply_to':'<original@example.test>'}
        c['drafts'].append('followup');c['last_sent_at']='2026-09-19T12:00:00+00:00';self.s.save(c)
        self.assertEqual(self.row(c)['due_date'],original)

    def test_unsent_and_uncertain_never_get_initial_clock(self):
        c=self.case(sent=None);c['last_sent_at']='2026-09-01T12:00:00+00:00';self.s.save(c)
        self.assertEqual(self.row(c)['status'],'not_sent')
        for draft in ({'state':'uncertain'},{'state':'accepted','receipt':None}):
            self.drafts['unknown']=draft;c['drafts']=['unknown'];self.s.save(c)
            r=self.row(c);self.assertEqual(r['status'],'send_uncertain');self.assertEqual(r['checks'],[])
        c['drafts']=['missing'];self.s.save(c);self.assertEqual(self.row(c)['status'],'send_uncertain')

    def test_no_fixed_and_unsupported_jurisdictions(self):
        for state in ('NC','WI','AZ'):
            r=self.row(self.case(state));self.assertEqual(r['status'],'no_fixed_clock');self.assertEqual(r['due_date'],'')
        for state,level in [('AK','county'),('CA','state')]:
            r=self.row(self.case(state,level=level));self.assertEqual(r['status'],'needs_basis');self.assertIsNone(r['rule'])

    def test_south_dakota_requires_explicit_formal_status(self):
        c=self.case('SD');self.assertEqual(self.row(c)['checks'],[])
        self.save(c,filing_status='formal');self.assertEqual(self.row(c)['due_date'],'2026-09-23')
        self.save(c,filing_status='inquiry');self.assertEqual(self.row(c)['checks'],[])

    def test_indiana_calendar_not_business_days(self):
        self.assertEqual(self.row(self.case('IN'))['due_date'],'2026-09-16')

    def test_recorded_receipt_is_start_date_not_adjusted_twice(self):
        c=self.case();self.save(c,received_date='2026-09-14',receipt_basis='Synthetic statutory receipt reviewed.')
        self.assertEqual(self.row(c)['due_date'],'2026-09-21')
        self.save(c,excluded_dates=['2026-09-15']);self.assertEqual(self.row(c)['due_date'],'2026-09-22')

    def test_reply_requires_review_not_automatic_sufficiency(self):
        c=self.case();m=self.mail(c)
        r=self.row(c);self.assertEqual(r['status'],'reply_review');self.assertEqual(r['checks'][0]['date'],'2026-09-17')
        self.save(c,initial_response='satisfied',response_message_id=m['id'],response_basis='Synthetic qualifying notice reviewed.')
        r=self.row(c);self.assertEqual(r['status'],'response_recorded');self.assertEqual(r['checks'][0]['status'],'resolved')
        self.mail(c,'INBOX:1:2');self.assertEqual(self.row(c)['status'],'reply_review')
        self.save(c,next_kind='follow_up',next_date='2026-09-30',next_basis='Internal reminder only.')
        self.assertEqual(self.row(c)['status'],'reply_review','an unrelated edit must not review new mail')

    def test_evidence_unassignment_reopens_review(self):
        c=self.case();m=self.mail(c)
        self.save(c,initial_response='satisfied',response_message_id=m['id'],response_basis='Synthetic reviewed reply.')
        m['case_id']=None;self.db.put('mail',m['id'],m)
        self.assertEqual(self.row(c)['status'],'reply_review')
        self.assertFalse(self.row(c)['checks'][0]['resolved'])

    def test_extension_separate_from_original_and_no_send(self):
        c=self.case();m=self.mail(c)
        with patch('connector.dispatch',side_effect=AssertionError('No external operation')):
            self.save(c,initial_response='satisfied',response_message_id=m['id'],response_basis='Reviewed extension notice.',next_kind='extension',next_date='2026-10-01',next_source='https://example.gov/foia',next_checked_date='2026-09-20',next_message_id=m['id'],next_basis='Synthetic case-specific extension calculation.')
        r=self.row(c);self.assertEqual(r['due_date'],'2026-10-01');self.assertEqual(len(r['checks']),2)
        self.assertEqual(r['checks'][0]['date'],'2026-09-17');self.assertEqual(r['checks'][1]['confidence'],'operator_recorded')
        self.save(c,next_completed=True);self.assertEqual(self.row(c)['status'],'response_recorded')

    def test_old_recorded_deadline_is_retained(self):
        c=self.case('WI');c['tracking'].update(deadline_date='2026-10-02',deadline_kind='appeal',deadline_source='https://example.gov/appeal',deadline_basis='Synthetic old reviewed deadline.',deadline_checked_date='2026-09-19');self.s.save(c)
        self.save(c,filing_status='formal');self.assertEqual(self.row(c)['due_date'],'2026-10-02')
        self.assertEqual(self.s.case(c['id'])['tracking']['deadline_date'],'2026-10-02')

    def test_reminders_are_not_labeled_legal_overdue(self):
        c=self.case('WI');self.save(c,next_date='2026-09-18',next_kind='follow_up',next_basis='Internal follow-up cadence.')
        r=self.row(c);self.assertEqual(r['label'],'Follow-up reminder due');self.assertEqual(r['checks'][0]['confidence'],'reminder')

    def test_revision_and_validation_guards(self):
        c=self.case()
        invalid=[{'revision':True},{'revision':999},{'received_date':'2026-09-21','receipt_basis':'Future'},
                 {'received_date':'2026-09-14'},{'received_date':'2026-02-30','receipt_basis':'Invalid'},
                 {'initial_response':'satisfied'},{'response_message_id':'missing'},
                 {'next_date':'2026-09-21'},{'next_date':'2026-09-21','next_kind':'extension','next_basis':'No notice'},
                 {'next_date':'2026-09-21','next_kind':'appeal','next_basis':'Missing source'},
                 {'next_source':'http://example.gov/law'},{'next_source':'https://secret@example.gov/'},
                 {'next_checked_date':'2027-01-01'},{'time_zone':[]},{'excluded_dates':[{}]},
                 {'next_completed':'true'},{'next_kind':'follow_up'}]
        for args in invalid:
            with self.subTest(args=args),self.assertRaises(ConnectorError):self.save(c,**args)
        c['routing_verified']=False;self.s.save(c)
        with self.assertRaises(ConnectorError):self.save(c,filing_status='formal')
        for key in ('',123):
            with self.assertRaises(ConnectorError):self.s.dispatch('desk_get_deadlines',{'case_id':key})

    def test_portal_does_not_inherit_email_receipt_adjustment(self):
        c=self.case(sent=None);c['portal_receipt']={'date':'2026-09-10','reference':'synthetic'};self.s.save(c)
        self.assertEqual(self.row(c)['status'],'needs_basis')
        self.save(c,received_date='2026-09-10',receipt_basis='Synthetic portal receipt as statutory start date.')
        self.assertEqual(self.row(c)['due_date'],'2026-09-17')

    def test_stale_sources_and_mail_are_visible(self):
        c=self.case();self.db.put('sync','INBOX',{'folder':'INBOX','at':NOW.timestamp()})
        self.assertFalse(self.s.dispatch('desk_get_deadlines',{})['mail_stale'])
        with patch('deadlines.utcnow',return_value=datetime(2027,5,1,18,tzinfo=timezone.utc)):
            r=self.s.dispatch('desk_get_deadlines',{})
        self.assertTrue(r['mail_stale']);self.assertTrue(any('180 days' in x for x in r['cases'][0]['warnings']))

    def test_federal_rule_selected_by_target_not_state(self):
        c=self.case('TX');c['target']={'level':'federal','label':'Synthetic federal agency'};self.s.save(c)
        self.assertEqual(self.row(c)['rule_code'],'US');self.assertEqual(self.row(c)['rule']['days'],20)

    def test_partial_sync_unassigned_and_saved_audit(self):
        c=self.case('WI');m=self.mail(c);m['case_id']=None;self.db.put('mail',m['id'],m)
        self.db.put('sync','INBOX',{'folder':'INBOX','at':NOW.timestamp(),'more':True})
        r=self.s.dispatch('desk_get_deadlines',{})
        self.assertTrue(r['mail_sync_incomplete']);self.assertEqual(r['unassigned_incoming'],1)
        self.save(c,next_kind='follow_up',next_date='2026-09-22',next_basis='First synthetic reminder.')
        self.save(c,next_date='2026-09-25',next_basis='Rescheduled synthetic reminder.')
        history=[e for e in self.db.all('event') if e['action']=='deadline_evidence_saved']
        self.assertEqual(len(history),2)
        self.assertEqual({e['details']['tracking']['next_date'] for e in history},{'2026-09-22','2026-09-25'})


if __name__=='__main__': unittest.main()
