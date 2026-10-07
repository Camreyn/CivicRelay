// Native/HTTP only: keep the existing 64-tool WebMCP budget.
const integer = (minimum, maximum) => ({type:'integer', minimum, ...(maximum ? {maximum} : {})});
export const SENDING_LIMIT_TOOLS = [
  {name:'desk_get_send_limits', readOnly:true, page:false,
    description:'Read CivicRelay sending limits, revision, defaults and rolling usage locally. No mailbox connection, credentials, reservation or settings change. Proton limits are independent.',
    schema:{type:'object', properties:{}, required:[], additionalProperties:false}},
  {name:'desk_save_send_limits', readOnly:false, page:false,
    description:'Change the local rolling-24-hour send-attempt cap and minimum spacing using the current revision. Requires explicit user authority to change these settings; an ordinary send request or a blocked quota is NOT permission to raise them. Defaults are 10 attempts and 60 seconds. Does not reset history, enable sending, retry uncertain drafts, connect, send, or override Proton limits.',
    schema:{type:'object', properties:{revision:integer(0), max_attempts_per_24h:integer(1,1000), minimum_interval_seconds:integer(1,3600)},
      required:['revision','max_attempts_per_24h','minimum_interval_seconds'], additionalProperties:false}},
];
