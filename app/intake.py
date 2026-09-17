"""Same records-response issue form as the public site; publication is an explicit action."""
import base64
import hashlib
import hmac
import io
import ipaddress
import os
import json
import re
import time
import urllib.parse
import uuid
import zipfile
from runtime import GH, run
from secure_store import ConnectorError, canonical
import connector

REPOSITORY='Camreyn/civicresultmaps'
ISSUE_URL=re.compile(r'https://github\.com/Camreyn/civicresultmaps/issues/[1-9][0-9]*\Z',re.I)

def validate_repository(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',value):
        raise ConnectorError('Use a GitHub owner/repository, without a URL, path or command options.')
    return value

def issue_url_matches(url,repository):
    validate_repository(repository)
    return bool(isinstance(url,str) and re.fullmatch(r'https://github\.com/'+re.escape(repository)+r'/issues/[1-9][0-9]*',url,re.I))

def snapshot_repository(issue):
    repository=validate_repository(issue.get('repository'))
    if issue.get('destination_id'):
        target=issue.get('target_snapshot')
        if not isinstance(target,dict) or target.get('id')!=issue['destination_id'] or target.get('repository')!=repository or target.get('template_sha256')!=issue.get('template_sha256'):
            raise ConnectorError('Publication destination snapshot changed.')
    elif repository!=REPOSITORY:
        raise ConnectorError('Legacy publication destination changed.')
    return repository

def safe_url(value):
    if not value:return ''
    try:p=urllib.parse.urlsplit(value)
    except ValueError:raise ConnectorError('Use a public HTTPS link.') from None
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ConnectorError('Only public HTTPS links without embedded credentials are allowed.')
    host=p.hostname.lower()
    try:local_ip=not ipaddress.ip_address(host).is_global
    except ValueError:local_ip=False
    if local_ip or host in {'localhost','127.0.0.1','::1'} or host.endswith(('.local','.localhost','.internal','.lan','.home')) or not '.' in host or '%' in host:
        raise ConnectorError('A local address is not a public source location.')
    decoded=(p.path+'?'+p.query+'#'+p.fragment).lower()
    for _ in range(3):decoded=urllib.parse.unquote(decoded)
    if any(word in decoded for word in ('token=','password=','secret=','signature=','x-amz-','access_key=')):
        raise ConnectorError('This looks like a signed/private URL. Use a stable public location instead.')
    return value

def check_public_text(text):
    # This is a tripwire, not a redaction guarantee. The operator must review the exact preview.
    if re.search(r'(?i)((?<![a-z])[a-z]:[\\/]|file://|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|\b(?:ghp_|github_pat_|sk-proj-)[a-zA-Z0-9_]+|(?:password|api[_ -]?key|access[_ -]?token)\s*[:=]\s*\S+)',text):
        raise ConnectorError('The submission contains a private path or possible credential. Remove it before preparing a public issue.')
    if re.search(r'(?im)^\s*(from|to|cc|bcc):',text):
        raise ConnectorError('Do not paste raw mail headers into the public submission. Summarize and redact first.')

def prepare(db,catalog,case,fields,artifact_ids,*,definition=None):
    custom=definition is not None
    definition=definition if custom else catalog['issue']
    allowed={f['id'] for f in definition['fields'] if f['type']!='checkboxes'}
    if not isinstance(fields,dict) or set(fields)-allowed:raise ConnectorError('Use the current records-response form fields only.')
    values={}
    for f in definition['fields']:
        if f['type']=='checkboxes':continue
        value=fields.get(f['id'],'')
        if not isinstance(value,str) or len(value)>12000:raise ConnectorError('An intake field is missing or too long.')
        value=value.strip()
        if value:connector.clean_text(value,12000,multiline=True)
        if f['required'] and not value:raise ConnectorError(f"Complete the required field: {f['label']}.")
        if f['options'] and value not in f['options']:raise ConnectorError('Choose a valid response status from the public form.')
        values[f['id']]=value
    if not custom:
        values['state']=f"{case['state_name']} ({case['state']})"
        if not values.get('request_id'):values['request_id']='; '.join(case['request_ids'])
    if values.get('response_date'):
        from datetime import date
        try:date.fromisoformat(values['response_date'])
        except ValueError:raise ConnectorError('Use YYYY-MM-DD for the response date.') from None
    safe_url(values.get('response_url',''))
    if not isinstance(artifact_ids,list) or len(artifact_ids)>30 or len(set(artifact_ids))!=len(artifact_ids):
        raise ConnectorError('Select up to 30 unique captured artifacts.')
    artifact_ids=sorted(artifact_ids)
    artifacts=[]
    for key in artifact_ids:
        a=db.get('artifact',key)
        if not a or a['case_id']!=case['id']:raise ConnectorError('An artifact does not belong to this request.')
        artifacts.append(a)
    # Explicit form input is authoritative; never copy raw mail, signatures, or attachments into a ticket.
    parts=[]
    for f in definition['fields']:
        value='\n'.join('- [x] '+v for v in f['checklist']) if f['type']=='checkboxes' else values.get(f['id'],'') or '_No response_'
        parts.append(f"### {f['label']}\n\n{value}")
    if artifacts:
        parts.append('### Captured file manifest\n\n'+ '\n'.join(f"- {a['filename']} | {a['content_type']} | {a['bytes']} bytes | SHA-256 `{a['sha256']}`" for a in artifacts))
        parts.append('Original files are NOT attached by this tool. The public link/upload must be supplied separately; local quarantine paths are never published.')
    title=f"[Records response] {case['state']} {case['request_ids'][0]}" if not custom else '[Records response] '+case['family_label'][:150]
    key=str(uuid.uuid4())
    parts.append(f'<!-- records-desk-submission:{key} -->')
    body='\n\n'.join(parts); check_public_text(title+'\n'+body)
    if len(body)>50000:raise ConnectorError('Public issue text is too long. Shorten the response summary.')
    issue={'id':key,'case_id':case['id'],'title':title,'body':body,'fields':values,
           'artifact_ids':artifact_ids,'artifacts':[{'id':a['id'],'filename':a['filename'],'sha256':a['sha256'],'bytes':a['bytes']} for a in artifacts],
           'template_sha256':definition['template_sha256'],'repository':definition['repository'] if custom else REPOSITORY,
           'labels':definition['labels'],'state':'prepared','prepared_at':time.time(),'url':None}
    if custom:
        issue.update(destination_id=definition['id'],target_snapshot=definition)
    issue['digest']=digest(issue)
    params={'template':definition['template'],'labels':','.join(definition['labels']),'title':title,**values}
    url=definition['url']+'?'+urllib.parse.urlencode(params)
    issue['form_url']=url if len(url)<7500 else definition['url']+'?'+urllib.parse.urlencode({'template':definition['template'],'title':title})
    issue['form_prefill_complete']=len(url)<7500
    # One open intake per case: an uncertain or published attempt must be reconciled,
    # never evaded by generating a new ID for the same response.
    for previous in db.all('issue'):
        if previous['case_id']==case['id'] and previous['state'] in ('publishing','uncertain'):
            raise ConnectorError('A previous public submission is unresolved. Verify and link that issue before preparing another.')
        if previous['case_id']==case['id'] and previous['fields']==values and sorted(previous['artifact_ids'])==artifact_ids and previous['repository']==issue['repository'] and previous.get('destination_id')==issue.get('destination_id') and (previous['state']=='published' or (previous['state']=='prepared' and previous['template_sha256']==definition['template_sha256'])):
            return previous
    for previous in db.all('issue'):
        if previous['case_id']==case['id'] and previous['state']=='prepared':
            previous['state']='superseded';db.put('issue',previous['id'],previous)
    db.put('issue',key,issue)
    return issue

def digest(issue):
    keys=('id','case_id','title','body','fields','artifacts','template_sha256','repository','labels')
    value={k:issue[k] for k in keys}
    if issue.get('destination_id'):
        value.update(destination_id=issue['destination_id'],target_snapshot=issue['target_snapshot'])
    return hashlib.sha256(canonical(value)).hexdigest()

def require_prepared(db,key,expected,catalog):
    issue=db.get('issue',key)
    if not issue or issue['state']!='prepared':raise ConnectorError('Submission already attempted or missing. Reconcile the receipt before any retry.')
    for other in db.all('issue'):
        if other['id']!=key and other['case_id']==issue['case_id'] and other['state'] in ('publishing','uncertain'):
            raise ConnectorError('Another public submission for this request is unresolved. Reconcile it before publishing anything else.')
    if not isinstance(expected,str) or not hmac.compare_digest(digest(issue),expected) or issue['digest']!=expected:
        raise ConnectorError('Submission content changed. Review the exact current preview.')
    if issue.get('destination_id'):
        target=db.get('destination',issue['destination_id'])
        if not target or not target.get('enabled') or target!=issue['target_snapshot']:
            raise ConnectorError('Publication destination changed or was disabled. Prepare a new exact preview.')
    elif issue['template_sha256']!=catalog['issue']['template_sha256'] or issue['repository']!=REPOSITORY:
        raise ConnectorError('The public issue form changed. Prepare a new preview using its current fields.')
    verify_snapshot(db,issue)
    return issue

def verify_snapshot(db,issue):
    if issue['digest']!=digest(issue):raise ConnectorError('Issue snapshot identity changed.')
    snapshot_repository(issue)
    check_public_text(issue['title']+'\n'+issue['body'])
    for saved in issue['artifacts']:
        artifact=db.get('artifact',saved['id']);blob=db.get('blob',saved['id'])
        if not artifact or artifact['case_id']!=issue['case_id'] or any(artifact[k]!=saved[k] for k in ('id','sha256','filename','bytes')):
            raise ConnectorError('A selected artifact was reassigned or changed. Prepare a current intake preview.')
        if not blob or hashlib.sha256(base64.b64decode(blob['base64'],validate=True)).hexdigest()!=saved['sha256']:
            raise ConnectorError('Captured artifact bytes do not match the reviewed manifest.')

def publish(db,catalog,key,expected,runner=None):
    issue=require_prepared(db,key,expected,catalog)
    if issue['artifacts'] and not issue['fields'].get('response_url'):
        raise ConnectorError('Captured files are private, not uploaded. Add a reviewed public file link or use the GitHub form to upload the exported package first.')
    if not GH or (runner is None and not __import__('pathlib').Path(GH).is_file()):raise ConnectorError('GitHub CLI is unavailable. Use the same public GitHub form link instead.')
    issue=require_prepared(db,key,expected,catalog)
    issue.update(state='publishing',attempted_at=time.time());db.put('issue',key,issue)
    try:
        # JSON stdin avoids command-line content exposure and prevents option injection.
        payload=json.dumps({'title':issue['title'],'body':issue['body'],'labels':issue['labels']}).encode()
        repository=snapshot_repository(issue)
        result=(runner or run)([GH,'api','--hostname','github.com','--method','POST',f'repos/{repository}/issues','--input','-'],payload=payload,timeout=45)
        if result.returncode or len(result.stdout)>1_000_000:raise RuntimeError()
        response=json.loads(result.stdout)
        if not issue_url_matches(response.get('html_url',''),repository):raise RuntimeError()
        issue.update(state='published',url=response['html_url'],published_at=time.time());db.put('issue',key,issue)
        return {'published':True,'state':'published','issue':issue}
    except Exception:
        issue['state']='uncertain';db.put('issue',key,issue)
        return {'published':False,'state':'uncertain','issue':issue,'warning':'An issue may have been created. Check GitHub for this title and submission ID; no automatic retry is allowed.'}

def reconcile(db,key,url,runner=None):
    issue=db.get('issue',key)
    if not issue:raise ConnectorError('Submission was not found.')
    repository=snapshot_repository(issue)
    if not issue_url_matches(url,repository):raise ConnectorError('Use an issue URL in the exact reviewed GitHub repository.')
    if issue['state']=='superseded':raise ConnectorError('Use the latest reviewed preview for this submission.')
    verify_snapshot(db,issue)
    number=url.rsplit('/',1)[1]
    result=(runner or run)([GH,'api','--hostname','github.com',f'repos/{repository}/issues/{number}'],timeout=30)
    if result.returncode or len(result.stdout)>1_000_000:raise ConnectorError('Could not verify that GitHub issue using the current desktop authentication.')
    remote=json.loads(result.stdout)
    if not issue_url_matches(remote.get('html_url'),repository) or remote['html_url'].lower()!=url.lower():
        raise ConnectorError('The GitHub response does not match the exact reviewed repository and issue URL.')
    labels={x['name'] for x in remote.get('labels',[])}
    if 'pull_request' in remote or not set(issue['labels']).issubset(labels):raise ConnectorError('This is not the expected records-response issue.')
    body=remote.get('body') or ''
    if remote.get('title')!=issue['title']:raise ConnectorError('The public issue title differs from the reviewed submission.')
    if issue['state'] in ('publishing','uncertain','published'):
        if body.strip()!=issue['body'].strip():raise ConnectorError('The remote issue does not match this attempted submission. Review its exact content before reconciliation.')
    else:
        sections={m[0].strip():m[1].strip() for m in re.findall(r'(?ms)^### ([^\n]+)\n+(.*?)(?=^### |\Z)',body)}
        expected={m[0].strip():m[1].strip() for m in re.findall(r'(?ms)^### ([^\n]+)\n+(.*?)(?=^### |\Z)',issue['body'])}
        # The manual form omits the internal marker; fields and responsible-review
        # checks must still agree, not merely mention the state somewhere in text.
        for label,value in expected.items():
            if label=='Captured file manifest':continue
            value=re.sub(r'<!-- records-desk-submission:[^>]+ -->','',value).strip()
            if sections.get(label,'').strip()!=value:
                raise ConnectorError('A GitHub form field differs from this preview. Prepare a matching reviewed preview before linking the issue.')
    issue.update(state='published',url=remote['html_url'],published_at=time.time(),reconciled=True)
    db.put('issue',key,issue);return issue

def export_package(db,issue):
    verify_snapshot(db,issue)
    if not issue['artifacts']:raise ConnectorError('Select captured attachments when preparing this intake package.')
    if sum(a['bytes'] for a in issue['artifacts'])>50*1024*1024:raise ConnectorError('Select at most 50 MiB for one local export package.')
    db.guard(); exports=db.root/'Exports';exports.mkdir(mode=0o700,exist_ok=True)
    # A newly-created per-export directory gets Python 3.13's Windows DACL:
    # current user and administrators only. Plaintext export is explicit, not DPAPI.
    directory=exports/uuid.uuid4().hex;directory.mkdir(mode=0o700)
    db.guard()
    target=directory/f"records-{issue['id']}-{uuid.uuid4().hex[:8]}.zip"
    manifest={'case_id':issue['case_id'],'submission_id':issue['id'],'files':[],
              'warning':'PRIVATE originals. Redact before public sharing. Source/status intake only, not production import.'}
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',compression=zipfile.ZIP_STORED) as z:
        for a in issue['artifacts']:
            artifact=db.get('artifact',a['id']);blob=db.get('blob',a['id'])
            if not artifact or not blob or artifact['case_id']!=issue['case_id'] or artifact['sha256']!=a['sha256']:raise ConnectorError('Captured artifact identity changed.')
            content=base64.b64decode(blob['base64'],validate=True)
            if hashlib.sha256(content).hexdigest()!=a['sha256']:raise ConnectorError('Captured artifact digest does not match.')
            name=re.sub(r'[^A-Za-z0-9._-]','_',a['filename']).strip(' .')[:120] or 'unnamed.bin'
            entry=f"files/{a['id'][:12]}-{name}"
            z.writestr(entry,content);manifest['files'].append({**artifact,'export_entry':entry})
        z.writestr('PRIVATE-manifest.json',json.dumps(manifest,indent=2))
        z.writestr('PUBLIC-issue-preview.md',issue['title']+'\n\n'+issue['body'])
        z.writestr('READ-ME.txt','Local, unredacted originals. Never upload without inspecting every file and removing unnecessary personal data. The GitHub records-response issue is a review handoff; no import or promotion is automatic.\n')
    temporary=target.with_suffix('.partial')
    try:
        with temporary.open('xb') as handle:
            handle.write(memory.getvalue());handle.flush();os.fsync(handle.fileno())
        temporary.rename(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'exported':True,'path':str(target),'sha256':hashlib.sha256(memory.getvalue()).hexdigest(),'publicly_uploaded':False,
            'plaintext_warning':'This reviewed export is NOT DPAPI-encrypted. Remove the ZIP/export directory after uploading only redacted files. Encrypted originals remain in quarantine; no automatic deletion occurs.'}

def export_case(db,case,artifact_ids):
    """Explicit local-only handoff, independent of any publication integration."""
    if not isinstance(artifact_ids,list) or len(artifact_ids)>30 or any(not isinstance(x,str) for x in artifact_ids) or len(set(artifact_ids))!=len(artifact_ids):
        raise ConnectorError('Select up to thirty unique captured artifact IDs.')
    files=[];total=0
    for key in artifact_ids:
        artifact=db.get('artifact',key);blob=db.get('blob',key)
        if not artifact or not blob or artifact['case_id']!=case['id']:
            raise ConnectorError('A selected file no longer belongs to this request.')
        content=base64.b64decode(blob['base64'],validate=True)
        if len(content)!=artifact['bytes'] or hashlib.sha256(content).hexdigest()!=artifact['sha256']:
            raise ConnectorError('Captured file bytes differ from the retained provenance.')
        total+=len(content)
        if total>50*1024*1024:raise ConnectorError('Select at most 50 MiB of originals for one export.')
        files.append((artifact,content))
    messages=sorted([m for m in db.all('mail') if m.get('case_id')==case['id']],key=lambda m:m['id'])
    if len(messages)>500:raise ConnectorError('This request has more than 500 messages. Use a reviewed archival procedure; nothing was truncated or exported.')
    saved_messages=[]
    for message in messages:
        body=db.get('body',message['id'])
        saved_messages.append({**message,**({'body':body['body']} if body else {})})
    memory=io.BytesIO();manifest={'case_id':case['id'],'files':[],'exported_at':time.time(),
        'warning':'PRIVATE unredacted local package. Not a public submission. No files were uploaded.'}
    with zipfile.ZipFile(memory,'w',compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('PRIVATE-request.json',json.dumps(case,ensure_ascii=False,indent=2))
        archive.writestr('PRIVATE-correspondence.json',json.dumps(saved_messages,ensure_ascii=False,indent=2))
        for index,(artifact,content) in enumerate(files):
            name=re.sub(r'[^A-Za-z0-9._-]','_',artifact['filename']).strip(' .')[:120] or 'unnamed.bin'
            entry=f'files/{index+1:03d}-{name}'
            archive.writestr(entry,content);manifest['files'].append({**artifact,'export_entry':entry})
        archive.writestr('PRIVATE-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        archive.writestr('READ-ME.txt','PRIVATE, UNREDACTED records and saved correspondence. Inspect every file and remove unnecessary personal information before sharing. Captured originals remain encrypted locally. This export does not send, publish, accept fees or import data.\n')
    content=memory.getvalue()
    if len(content)>65*1024*1024:raise ConnectorError('This export exceeds the 65 MiB package limit. Nothing was exported.')
    db.guard();exports=db.root/'Exports';exports.mkdir(mode=0o700,exist_ok=True);db.guard()
    directory=exports/uuid.uuid4().hex;directory.mkdir(mode=0o700)
    target=directory/'private-request.zip';temporary=directory/'private-request.partial'
    try:
        with temporary.open('xb') as handle:
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        temporary.rename(target)
    finally:temporary.unlink(missing_ok=True)
    return {'exported':True,'path':str(target),'sha256':hashlib.sha256(content).hexdigest(),
            'artifact_count':len(files),'saved_message_count':len(saved_messages),'publicly_uploaded':False,
            'plaintext_warning':'Private plaintext ZIP contains unredacted request details and saved correspondence. Review before sharing.'}
