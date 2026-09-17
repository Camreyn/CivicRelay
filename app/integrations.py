"""Explicit, private publication configuration. Templates never choose destinations."""
import copy
import hashlib
import re
import time
import uuid
import connector
import intake
from secure_store import ConnectorError, canonical

ARGUMENTS = {
    'desk_list_destinations': set(),
    'desk_save_destination': {'destination_id','revision','name','repository','template','labels','fields','enabled'},
    'desk_prepare_publication': {'case_id','destination_id','fields','artifact_ids'},
    'desk_export_case': {'case_id','artifact_ids'},
}
READ_ONLY = {'desk_list_destinations'}

def text(value, limit, blank=False):
    if blank and value == '': return ''
    return connector.clean_text(value, limit)

def validate_definition(args):
    repository = text(args.get('repository'), 200)
    intake.validate_repository(repository)
    template = text(args.get('template',''), 100, True)
    if template and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.ya?ml',template):
        raise ConnectorError('Use the GitHub issue-form filename, not a URL or path.')
    labels=args.get('labels',[])
    if not isinstance(labels,list) or len(labels)>10 or any(not isinstance(x,str) for x in labels) or len(set(labels))!=len(labels):
        raise ConnectorError('Use up to ten unique labels.')
    labels=[text(x,80) for x in labels]
    fields=args.get('fields')
    if not isinstance(fields,list) or not 1<=len(fields)<=20:
        raise ConnectorError('Configure one to twenty issue fields.')
    result=[]
    for field in fields:
        if not isinstance(field,dict) or set(field)!={'id','label','type','required','options'}:
            raise ConnectorError('Use the documented destination field schema.')
        key=text(field['id'],60)
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,59}',key): raise ConnectorError('Field IDs use lowercase letters, numbers and underscores.')
        label=text(field['label'],160)
        if any(x['id']==key or x['label']==label for x in result): raise ConnectorError('Issue field IDs and labels must be unique.')
        if field['type'] not in ('input','textarea','dropdown') or type(field['required']) is not bool:
            raise ConnectorError('Use text, textarea or dropdown fields with an explicit required flag.')
        options=field['options']
        if not isinstance(options,list) or len(options)>30 or (field['type']=='dropdown' and not options) or (field['type']!='dropdown' and options):
            raise ConnectorError('Only dropdowns have options; provide one to thirty options.')
        options=[text(x,200) for x in options]
        if len(set(options))!=len(options): raise ConnectorError('Dropdown options must be unique.')
        result.append({**field,'id':key,'label':label,'options':options,'checklist':[]})
    if type(args.get('enabled',True)) is not bool: raise ConnectorError('Enabled must be true or false.')
    definition={'name':text(args.get('name'),120),'repository':repository,'template':template,
                'labels':labels,'fields':result,'enabled':args.get('enabled',True),
                'url':f'https://github.com/{repository}/issues/new'}
    intake.check_public_text(canonical(definition).decode())
    return definition

def list_destinations(service):
    return {'destinations':service.db.all('destination'),'network_accessed':False}

def save_destination(service,args):
    definition=validate_definition(args)
    key=args.get('destination_id')
    if key is not None and (not isinstance(key,str) or not key):
        raise ConnectorError('Destination ID must be nonempty text.')
    previous=service.db.get('destination',key) if isinstance(key,str) else None
    if key and not previous: raise ConnectorError('Publication destination not found.')
    if previous and (type(args.get('revision')) is not int or args['revision']!=previous['revision']):
        raise ConnectorError('Destination revision changed. Reload before editing.')
    if not previous and (type(args.get('revision',0)) is not int or args.get('revision',0)!=0): raise ConnectorError('A new destination starts at revision zero.')
    key=key or 'destination-'+uuid.uuid4().hex
    value={**definition,'id':key,'revision':previous['revision']+1 if previous else 1,'updated_at':time.time()}
    # Include the revision: changing settings invalidates an earlier publish preview,
    # even if a destination is later changed back to the same text.
    value['template_sha256']=hashlib.sha256(canonical(value)).hexdigest()
    service.db.put('destination',key,value)
    return {'destination':value,'network_accessed':False}

def dispatch(service,name,args):
    if name=='desk_list_destinations': return list_destinations(service)
    if name=='desk_save_destination': return save_destination(service,args)
    if name=='desk_export_case':
        return intake.export_case(service.db,service.case(args.get('case_id')),args.get('artifact_ids',[]))
    if name=='desk_prepare_publication':
        case=service.case(args.get('case_id'))
        target=service.db.get('destination',args.get('destination_id'))
        if not target or not target['enabled']: raise ConnectorError('Select an enabled, locally configured publication destination.')
        definition=copy.deepcopy(target)
        issue=intake.prepare(service.db,service.catalog,case,args.get('fields'),args.get('artifact_ids',[]),definition=definition)
        if issue['id'] not in case['issues']:
            case['issues'].append(issue['id']);service.save(case)
        return {'issue':issue,'published':issue['state']=='published','network_accessed':False}
    raise ConnectorError('Unknown integration operation.')
