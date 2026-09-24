"""Bounded public-directory collection. Never touches mail, routing or credentials.

Only registered HTTPS sources can be refreshed. Snapshots and attempts remain in
the encrypted store, and a failed/partial parse never replaces the last good set.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import http.client
import json
import re
import socket
import ssl
import time
import uuid
from urllib.parse import urlsplit

from secure_store import ConnectorError

SOURCE_ID = 'ma-local-election-offices'
SOURCE = dict(id=SOURCE_ID, state='MA', label='Massachusetts city/town election offices',
    url='https://www.sec.state.ma.us/divisions/elections/voter-resources/find-my-local-election-office.htm',
    description='Official statewide directory. Election-office records-holder contacts, not verified designated filing RAOs.',
    expected_count=351, review_after_days=90)
ARGUMENTS = {'desk_get_sources': set(), 'desk_refresh_source': {'source_id'},
             'desk_import_source': {'source_id', 'checked_on', 'text'},
             'desk_get_municipal_contacts': {'state', 'query', 'offset', 'limit'}}
READ_ONLY = {'desk_get_sources', 'desk_get_municipal_contacts'}
MAX_BYTES = 2_000_000
MAX_HISTORY = 100
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}")
POLICY = 'Municipalities are not counties. Directory contacts identify elections records holders only. Verify each designated RAO, scope and email procedure before filing. No case is rerouted or created; no email, fees or publication.'


def now():
    return datetime.now(timezone.utc)


def roster():
    return json.loads(Path(__file__).with_name('ma-municipalities.json').read_text(encoding='utf-8'))['municipalities']


def identity(name):
    return 'municipality:MA:' + re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


class SourceError(Exception):
    def __init__(self, code, message, debug=()):
        self.code, self.message, self.debug = code, message, list(debug)


class DirectoryText(HTMLParser):
    """Extract text only; do not execute scripts or follow links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.ignored=0

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'):
            self.ignored += 1
        if self.ignored:
            return
        if tag == 'h2':
            self.parts.append('\n## ')
        elif tag in ('p','br','div','li','tr','h1','h3','hr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'):
            self.ignored=max(0,self.ignored-1)
        if not self.ignored and tag in ('h2','h1','h3','p','div','li','tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def parse_directory(text, html=False):
    if re.search(r'Incapsula|Request unsuccessful|captcha|Access Denied', text, re.I):
        raise SourceError('source_blocked', 'The official website returned a blocking page. Previous contacts were preserved.', ['Use the source link and import reviewed directory text, or try again later.'])
    if html:
        parser=DirectoryText();parser.feed(text);text=''.join(parser.parts)
    text=text.replace('\xa0',' ')
    sections=re.split(r'(?m)^\s*##[ \t]+([^\r\n]+)\r?\n',text)
    expected=set(roster());found={}
    for name, block in zip(sections[1::2],sections[2::2]):
        name=' '.join(name.split())
        if name not in expected:
            continue
        if name in found:
            raise SourceError('duplicate_municipality','The directory contains duplicate municipality sections. Previous contacts were preserved.')
        # Bound extraction to this heading; never assign the next town's contact.
        email=re.search(r'\bEmail\s*:\s*(.*?)(?=\b(?:Phone|Fax|Drop Box(?:es)?)\s*:|$)',block,re.I|re.S)
        email_text=' '.join(email.group(1).split()) if email else ''
        emails=list(dict.fromkeys(e.lower() for e in EMAIL.findall(email_text)))
        phone=re.search(r'\bPhone\s*:\s*([^\n]+)',block,re.I)
        office=re.search(r'\bAddress\s*:\s*([^\n]+)',block,re.I)
        # Missing/ambiguous emails remain explicit gaps, never guessed addresses.
        found[name]={'id':identity(name),'state':'MA','jurisdiction_level':'municipality','municipality':name,
            'role':'elections','office':(office.group(1).strip() if office else 'Local election office')[:160],
            'emails':emails[:10], 'email_context':email_text[:1200],
            'phone':phone.group(1).strip()[:120] if phone else '',
            'evidence_status':'official_directory_entry', 'routing_verified':False,
            'designated_rao_status':'not_verified', 'source_url':SOURCE['url']}
    if set(found) != expected:
        raise SourceError('incomplete_directory','The directory is incomplete or its layout changed. Previous contacts were preserved.',
                          [f'Expected {len(expected)} municipalities; recognized {len(found)}.', f'Missing {len(expected-set(found))} municipality sections.'])
    count=sum(bool(r['emails']) for r in found.values())
    if count < 300:
        raise SourceError('email_layout_changed','Too few email fields were recognized. Previous contacts were preserved.',[f'Recognized emails for {count} of {len(expected)} municipalities.'])
    return [found[name] for name in sorted(found)]


def fetch_directory():
    """Fixed host/path, no proxies, redirects, cookies, credentials or URL arguments."""
    url=urlsplit(SOURCE['url'])
    connection=http.client.HTTPSConnection(url.hostname,443,timeout=12,context=ssl.create_default_context())
    started=time.monotonic()
    try:
        connection.request('GET',url.path,headers={'Accept':'text/html','User-Agent':'CivicRelay-public-directory/1.0','Accept-Encoding':'identity'})
        response=connection.getresponse()
        if response.status != 200:
            code='source_redirect' if 300<=response.status<400 else 'source_http_error'
            raise SourceError(code,'The source did not return the approved directory. Previous contacts were preserved.',[f'HTTP {response.status}; redirects are not followed.'])
        if response.getheader('Content-Type','').split(';')[0].strip().lower() not in ('text/html','application/xhtml+xml'):
            raise SourceError('content_type','The source returned an unexpected content type. Previous contacts were preserved.')
        if response.getheader('Content-Encoding','identity').lower() not in ('identity',''):
            raise SourceError('content_encoding','The source returned an unsupported encoding. Previous contacts were preserved.')
        chunks=[];size=0
        while True:
            if time.monotonic()-started > 35:
                raise SourceError('source_timeout','The source took too long. Previous contacts were preserved.')
            block=response.read1(min(65536,MAX_BYTES+1-size))
            if not block:
                break
            chunks.append(block);size+=len(block)
            if size>MAX_BYTES:
                raise SourceError('source_too_large','The source exceeded the 2 MB limit. Previous contacts were preserved.')
        raw=b''.join(chunks)
        return raw.decode('utf-8-sig'),len(raw)
    except SourceError:
        raise
    except (TimeoutError,socket.timeout):
        raise SourceError('source_timeout','The source timed out. Previous contacts were preserved.') from None
    except (OSError,http.client.HTTPException,UnicodeError):
        raise SourceError('source_unavailable','The source could not be read securely. Previous contacts were preserved.', ['Check internet access or use reviewed directory-text import. TLS verification remains enabled.']) from None
    finally:
        connection.close()


def require_source(value):
    if value != SOURCE_ID:
        raise ConnectorError('Choose a registered source ID from desk_get_sources. Arbitrary URLs are not accepted.')


def get_sources(service):
    state=service.db.get('source',SOURCE_ID,{})
    snapshot=service.db.get('source_snapshot',state.get('snapshot_id',''),{})
    age=(now().date()-date.fromisoformat(snapshot['checked_on'])).days if snapshot else None
    return {'sources':[{**SOURCE,'last_attempt_at':state.get('last_attempt_at'),
        'last_success_at':state.get('last_success_at'), 'checked_on':snapshot.get('checked_on'),
        'collection_mode':snapshot.get('collection_mode'), 'record_count':len(snapshot.get('records',[])),
        'stale':age is not None and age>SOURCE['review_after_days'],
        'last_result':state.get('last_result'), 'history':state.get('history',[])}],
        'network_accessed':False,'policy':POLICY}


def collect(service,args,imported=False):
    require_source(args.get('source_id'))
    current=service.db.get('source',SOURCE_ID,{'id':SOURCE_ID,'history':[]})
    if len(current['history']) >= MAX_HISTORY:
        raise ConnectorError('Source history capacity reached. No observations were discarded; use reviewed maintenance.')
    checked=now().date().isoformat()
    if imported:
        checked=args.get('checked_on')
        try:
            parsed=date.fromisoformat(checked)
            if parsed.isoformat()!=checked or parsed>now().date():raise ValueError()
        except (ValueError,TypeError):
            raise ConnectorError('Supply the actual source-check date as YYYY-MM-DD, not a future date.') from None
        value=args.get('text')
        if not isinstance(value,str) or not 1<=len(value)<=200000 or any(ord(c)<32 and c not in '\n\r\t' for c in value):
            raise ConnectorError('Import bounded plain directory text (1–200000 characters), without control characters.')
        old=service.db.get('source_snapshot',current.get('snapshot_id',''),{})
        if old and checked<old['checked_on']:
            raise ConnectorError('This import predates the saved source check. Older research cannot replace newer contacts.')
    attempted=now().isoformat()
    result={'source_id':SOURCE_ID,'attempted_at':attempted,'ok':False,'debug':[]}
    writes=[]
    try:
        if not imported:
            value,size=fetch_directory()
        else:
            size=len(value.encode('utf-8'))
        records=parse_directory(value,html=not imported)
        snapshot_id=str(uuid.uuid4())
        snapshot={'id':snapshot_id,'source_id':SOURCE_ID,'checked_on':checked,'collected_at':attempted,
            'collection_mode':'reviewed_text_import' if imported else 'direct_fetch',
            'sha256':hashlib.sha256(value.encode('utf-8')).hexdigest(),'bytes':size,'records':records,
            'source_url':SOURCE['url'],'source_text':value}
        writes.append(('source_snapshot',snapshot_id,snapshot))
        current.update(snapshot_id=snapshot_id,last_success_at=attempted)
        result.update(ok=True,code='imported' if imported else 'refreshed',
            message=f'Saved {len(records)} municipal election-office entries. Designated RAOs still require verification.',
            debug=[f'Validated {len(records)} unique municipalities against the official names roster.',
                   f'{sum(bool(r["emails"]) for r in records)} entries have email addresses.',
                   'No requests were created, rerouted or sent; no fees or publication.'])
    except SourceError as error:
        result.update(code=error.code,message=error.message,debug=error.debug)
    snapshot=next((v for k,_,v in writes if k=='source_snapshot'),None)
    if snapshot is None:
        snapshot=service.db.get('source_snapshot',current.get('snapshot_id',''),{})
    result.update(record_count=len(snapshot.get('records',[])),last_success_at=current.get('last_success_at'),
                  checked_on=snapshot.get('checked_on'),collection_mode=snapshot.get('collection_mode'))
    attempt_id=str(uuid.uuid4())
    current['history'].append({'id':attempt_id,**result,'snapshot_id':current.get('snapshot_id')})
    current.update(last_attempt_at=attempted,last_result=result)
    writes.append(('source',SOURCE_ID,current))
    service.db.put_many(writes)
    return result


def municipal_contacts(service,args):
    if args.get('state')!='MA':
        raise ConnectorError('Municipal directory coverage currently supports MA only. County contacts are separate.')
    query=args.get('query','')
    offset,limit=args.get('offset',0),args.get('limit',50)
    if not isinstance(query,str) or len(query)>100 or any(ord(c)<32 for c in query):
        raise ConnectorError('Use a municipality-name filter of up to 100 characters.')
    if type(offset) is not int or not 0<=offset<=351 or type(limit) is not int or not 1<=limit<=100:
        raise ConnectorError('Use a valid offset and a page size from 1 to 100.')
    source=get_sources(service)['sources'][0]
    current=service.db.get('source',SOURCE_ID,{})
    snap=service.db.get('source_snapshot',current.get('snapshot_id',''),{})
    by_name={r['municipality']:r for r in snap.get('records',[])}
    rows=[]
    for name in roster():
        if query.strip().lower() not in name.lower():continue
        item=by_name.get(name,{'id':identity(name),'municipality':name,'state':'MA','jurisdiction_level':'municipality',
                            'emails':[],'role':'elections','evidence_status':'not_collected','routing_verified':False,
                            'designated_rao_status':'not_verified','source_url':SOURCE['url']})
        rows.append({**item,'checked_on':snap.get('checked_on'),'collected_at':snap.get('collected_at'),
                     'collection_mode':snap.get('collection_mode'),'stale':source['stale']})
    return {'state':'MA','contacts':rows[offset:offset+limit],'total':len(rows),
        'next_offset':offset+limit if offset+limit<len(rows) else None,'source':source,
        'coverage':{'municipalities':351,'collected':len(by_name),'with_email':sum(bool(r['emails']) for r in by_name.values()),
                    'designated_raos_verified':0}, 'policy':POLICY,'network_accessed':False}


def dispatch(service,name,args):
    if name=='desk_get_sources':return get_sources(service)
    if name=='desk_refresh_source':return collect(service,args)
    if name=='desk_import_source':return collect(service,args,imported=True)
    if name=='desk_get_municipal_contacts':return municipal_contacts(service,args)
    raise ConnectorError('Unknown source operation.')
