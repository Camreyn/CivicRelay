// Evidence-only edits and read-only projections; never send, sync, accept fees or file appeals.
const text = maxLength => ({type:'string', maxLength});
const choice = values => ({type:'string', enum:values});
export const DEADLINE_TOOLS = [
 {name:'desk_get_deadlines', description:'Read source-linked deadline estimates for all saved requests or one case. Uses original accepted submissions, saved mail headers and reviewed timing evidence. No network, mailbox sync, mail-body parsing or writes. Estimates are not findings of legal violations; inspect warnings, source freshness and mailbox freshness.', readOnly:true,
  schema:{type:'object',additionalProperties:false,properties:{case_id:{...text(150),minLength:1}},required:[]}},
 {name:'desk_save_deadline_tracking', description:'Save PRIVATE reviewed timing evidence at the current case revision. Partial updates preserve omitted fields. Received date is the reviewed statutory START date (already including any email-receipt adjustment). Satisfying an initial response requires linked incoming mail and a review basis; an acknowledgment alone may not suffice. Extension/agency dates require a linked notice and official source; appeal dates require case-specific source verification. No email, fee acceptance, appeal filing or automatic legal determination.', readOnly:false,
  schema:{type:'object',additionalProperties:false,required:['case_id','revision'],properties:{
   case_id:{...text(150),minLength:1},revision:{type:'integer',minimum:0},
   filing_status:choice(['unverified','formal','inquiry']),received_date:text(10),receipt_basis:text(2500),receipt_message_id:text(150),
   initial_response:choice(['unreviewed','satisfied']),response_message_id:text(150),response_basis:text(2500),
   time_zone:choice(['','Eastern','Central','Mountain','Pacific','Alaska','Hawaii','Arizona','UTC']),excluded_dates:{type:'array',maxItems:80,items:text(10)},
   next_date:text(10),next_kind:choice(['','agency_commitment','extension','appeal','follow_up']),next_source:text(1500),next_basis:text(2500),
   next_checked_date:text(10),next_message_id:text(150),next_completed:{type:'boolean'}
  }}},
];
