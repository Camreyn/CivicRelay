"""Read-only state help. Availability is explicit, not invented national coverage."""
from copy import deepcopy
import deadlines
import ma_follow_up
from secure_store import ConnectorError

ARGUMENTS={'desk_get_state_guide':{'state'}}
READ_ONLY=set(ARGUMENTS)


def get_guide(service,state):
    names={s['code']:s['name'] for s in service.catalog['states']}
    if state not in names:
        raise ConnectorError('Choose a known state code.')
    rule=deadlines.registry()['rules'].get(state)
    guides=[]
    if state=='MA':
        profile=deepcopy(ma_follow_up.PROFILE)
        guides.append({'id':'ma-response-routing','title':'Massachusetts records and referral guide',
            'checked_on':profile['checked_date'],'sections':[
                {'title':'State response versus municipal requests','text':profile['municipal_routing']},
                {'title':'Formal filing route','text':'Use the designated Records Access Officer of the municipality or agency holding the records. A state RAO is not the filing custodian for every city or town.'},
                {'title':'Municipal contact inventory','text':'The city/town election directory below is collected separately from counties. Election-office contacts are official records-holder leads, not verified designated RAOs. Show source dates and unresolved routing before preparing any local filing.'},
                {'title':'Review replies independently','text':'Internal forwarding is not confirmed receipt. A local referral is not fulfillment. Assess each requested category using the linked response; retain the original submission and separate appeal planning watches.'},
                {'title':'Likely records holders','text':'; '.join(f'{r["role"]}: {r["records"]}' for r in profile['suggested_holders'])},
                {'title':'Boundaries','text':profile['limits']}],
            'sources':profile['sources']+[{'label':'Official request procedure and RAO routing','url':ma_follow_up.BASE+'public-records/public-records-law/public-records-request.htm'}]})
    if rule:
        sources=[{'label':rule['citation'],'url':rule['url']}]
        if rule.get('guidance_url'):sources.append({'label':'Official guidance','url':rule['guidance_url']})
        guides.append({'id':f'timing-{state}','title':f'{names[state]} timing guide',
            'checked_on':deadlines.registry()['checked_date'],
            'sections':[{'title':rule['label'],'text':rule['summary']},
                        {'title':'Scope and limits','text':'Planning estimate only. '+deadlines.registry()['calendar_note']+' Verify recipient, procedure, fees, receipt and any appeal deadline against the current official sources.'}],
            'sources':sources})
    return {'state':state,'state_name':names[state],'available':bool(guides),'guides':guides,
        'display':{'automatic_on_state_selection':True,'default_collapsed':True,'modal':False},
        'municipal_directory_available':state=='MA','network_accessed':False}
