// MA helper tools are native-only to preserve the existing 64-tool WebMCP surface.
// The dashboard buttons use these same schemas/backend, without page registration.
const str=maxLength=>({type:'string',maxLength});
const id={...str(150),minLength:1};
const choice=values=>({type:'string',enum:values});
const object=(properties,required=[])=>({type:'object',additionalProperties:false,properties,required});
const revision={type:'integer',minimum:0};
const review={
 case_id:id,revision,response_message_id:id,
 response_kind:choice(['internal_referral','local_referral','no_records','partial_response','records_received','withheld','clarification']),
 summary:str(2500),categories:{type:'array',maxItems:12,items:object({key:str(100),status:choice(['not_addressed','pending','partial','received','agency_reports_not_held','withheld','not_requested']),note:str(1500)},['key','status','note'])},
 referral_level:choice(['','state','municipality','unknown']),referral_target:str(250),
 referral_status:choice(['','reported_forwarded','suggested_routing','receipt_confirmed']),referral_note:str(2500),
 response_date:str(10),date_basis:str(1500),follow_up_on:str(10),
};
export const MA_TOOLS=[
 {name:'desk_get_ma_follow_up',readOnly:true,page:false,description:'Read MA response checklists, per-message reviews, source-dated official state contacts, suggested municipal routing, internal reminders and 90-calendar-day appeal planning watches. Referrals are not fulfillment or municipal coverage. No bodies parsed, network or writes. Supports electronic starter-pack and equipment cases; generic cases remain manual.',schema:object({case_id:id})},
 {name:'desk_save_ma_review',readOnly:false,page:false,description:'Save a complete PRIVATE MA response review at the current case revision. Requires a fully read, linked incoming message. Provide all fields, preserving the existing review. Distinguish internal forwarding from city/town routing suggestions; agency_reports_not_held is not statewide nonexistence. Response date and basis are operator-reviewed inputs for an unverified appeal estimate. Does not close cases, satisfy legal checkpoints, mark mail reviewed, reroute, send, incur fees or file appeals.',schema:object(review,Object.keys(review))},
 {name:'desk_preview_ma_follow_up',readOnly:true,page:false,description:'Generate read-only MA clarification text from a current saved response review. confirm_referral requires an internal referral; clarify_categories preserves the original scope. Returns the exact reply message ID and saved recipient as an unverified lead. Does not save correspondence or create/send a draft. Use existing save/prepare tools only after reviewing current official routing and exact text.',schema:object({case_id:id,revision,response_message_id:id,purpose:choice(['confirm_referral','clarify_categories'])},['case_id','revision','response_message_id','purpose'])},
];
