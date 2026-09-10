// Narrow publication guard, not a general secret scanner or privacy review.
import path from 'node:path';
const roots=new Set(['.gitignore','.gitattributes','AGENTS.md','README.md','LICENSE','NOTICE','SECURITY.md',
  'package.json','package-lock.json','runtime-config.mjs','Open CivicRelay.cmd','Open Records Desk.cmd',
  'Open-Records-Desk.ps1','Open-Proton-Setup.ps1']);
const deny=/(^|\/)(\.private|\.local|\.codex|node_modules|collections|exports|attachments|quarantine|__pycache__)(\/|$)|\.(dpapi|sqlite\w*|db|eml|mbox|pst|ost|pem|key|p12|pfx|log|png|zip|csv|pdf)$/i;
const allowed=/^(app|connector|scripts)\/[\w./-]+\.(py|mjs|js|html|css|json|ps1)$|^docs\/[\w./-]+\.(md|toml)$|^data\/(catalog\.json|snapshot-provenance\.json|records-response\.yml)$|^\.github\/workflows\/ci\.yml$/;
export function assertPublicPath(file) {
  if(path.posix.normalize(file)!==file||file.includes('\\')||file.startsWith('../')||path.posix.isAbsolute(file)||deny.test(file)||(!roots.has(file)&&!allowed.test(file)))
    throw Error('Unexpected or private Git-visible path: '+file);
}
export function sensitiveMarkers(text) {
  const checks=[
    ['private-key block',/-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----/],
    ['GitHub token',/\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,})\b/],
    ['OpenAI-style token',/\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b/],
    ['AWS access-key ID',/\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/],
  ];
  return checks.filter(([,pattern])=>pattern.test(text)).map(([name])=>name);
}
export function validatePublicBytes(file,bytes) {
  assertPublicPath(file);
  if(bytes.length>2_000_000||bytes.includes(0)) throw Error('Oversized or binary publication input: '+file);
  let value;
  try {value=new TextDecoder('utf-8',{fatal:true}).decode(bytes);} catch {throw Error('Expected UTF-8 source text: '+file);}
  const found=sensitiveMarkers(value);
  if(found.length) throw Error('Sensitive marker in '+file+': '+found.join(', ')+' (value withheld)');
}
