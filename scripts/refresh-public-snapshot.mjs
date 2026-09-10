// Maintainer-only refresh from a reviewed checkout. Modified for extraction 2026-09-10.
import fs from 'node:fs';
import path from 'node:path';
import Module, {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
if(process.argv.length!==4 || process.argv[3]!=='--trusted-source' || !path.isAbsolute(process.argv[2]))
  throw Error('Usage: node scripts/refresh-public-snapshot.mjs ABSOLUTE_CRM_CHECKOUT --trusted-source (executes reviewed public loaders).');
const root=fs.realpathSync(process.argv[2]);
if(root===project) throw Error('Select the separate CivicResultMaps checkout.');
const require=createRequire(import.meta.url);
const ts = require('typescript');
const observed=new Set(['scripts/state-metadata.mjs','.github/ISSUE_TEMPLATE/records-response.yml','public/data/national-counties.geojson']);
function load(relative) {
  observed.add(relative);
  const filename = path.join(root, relative);
  const sourceText=fs.readFileSync(filename,'utf8');
  for(const match of sourceText.matchAll(/from\s+["'](\.\.\/\.\.\/data\/[^"']+\.json)["']/g)) {
    const input=path.resolve(path.dirname(filename),match[1]);
    if(!input.startsWith(root+path.sep)) throw Error('Source input outside selected checkout.');
    observed.add(path.relative(root,input).replaceAll('\\','/'));
  }
  const compiled = ts.transpileModule(sourceText, {
    compilerOptions: {module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2022},
  }).outputText;
  const mod = new Module(filename);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(path.dirname(filename));
  mod._compile(compiled, filename);
  return mod.exports;
}
const families = [
  ['source', 'Source records', load('src/lib/source-records-requests.ts').listSourceRecordsRequests()],
  ['electronic', 'Electronic records', load('src/lib/electronic-integrity-requests.ts').listElectronicIntegrityRequests()],
];
const {states}=await import(pathToFileURL(path.join(root,'scripts/state-metadata.mjs')).href);
const cases = families.flatMap(([family, label, result]) => result.summary.draftFiles.map(draft => {
  const contact = result.contacts.find(x => x.state === draft.state);
  return {
    id: `${family}-${draft.state}-2024`, state: draft.state, year: 2024, family, family_label: label,
    state_name: states.find(x => x.code === draft.state).name,
    subject: draft.subject, body: draft.emailBody, request_ids: draft.requestIds,
    recipient: contact?.recipientEmail || '', custodian: contact?.primaryCustodian || '',
    portal_url: contact?.recipientPortalUrl || '', lookup_url: contact?.recipientLookupUrl || '',
    routing_notes: contact?.notes || '', source_file: draft.emailFile,
    catalog_date: result.generatedAt, caveat: result.caveat,
    requests: result.requests.filter(x => draft.requestIds.includes(x.requestId)),
  };
}));
const form = fs.readFileSync(path.join(root, '.github/ISSUE_TEMPLATE/records-response.yml'), 'utf8');
const fieldBlocks = form.split(/\n  - type: /).slice(1);
const fields = fieldBlocks.filter(x => /\n    id: /.test(x)).map(block => ({
  type: block.split(/\r?\n/)[0], id: block.match(/\n    id: (.+)/)[1].trim(),
  label: block.match(/\n      label: (.+)/)?.[1].trim() || '',
  required: /\n      required: true/.test(block),
  options: block.startsWith('dropdown') ? [...block.matchAll(/\n        - (?!label:)(.+)/g)].map(x => x[1].trim()) : [],
  checklist: [...block.matchAll(/\n        - label: (.+)/g)].map(x => x[1].trim()),
}));
const result = {states: states.map(({code,name,fips})=>({code,name,fips})), cases,
  issue: {repository: 'Camreyn/civicresultmaps', template: 'records-response.yml',
    url: 'https://github.com/Camreyn/civicresultmaps/issues/new',
    labels: ['records-request', 'data-review'], fields,
    template_sha256: crypto.createHash('sha256').update(form).digest('hex')},
};
result.sha256 = crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex');
const {validateCatalog}=await import('../app/catalog.mjs');
validateCatalog(result);
const inputs=[...observed].sort().map(relative=>{
  const bytes=fs.readFileSync(path.join(root,relative));
  return {path:relative,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')};
});
let sourceCommit=null,sourceFilesModified=null;
try {
  sourceCommit=execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8',windowsHide:true}).trim();
  sourceFilesModified=!!execFileSync('git',['-C',root,'status','--porcelain','--',...inputs.map(x=>x.path)],{encoding:'utf8',windowsHide:true}).trim();
}catch { /* Input hashes still describe exact source bytes. */ }
const {buildMap}=await import('../app/map.mjs');
const map=buildMap(JSON.parse(fs.readFileSync(path.join(root,'public/data/national-counties.geojson'),'utf8')),states);
// Validate all inputs before writing generated artifacts. Refresh is never automatic.
for(const [relative,text] of [['data/catalog.json',JSON.stringify(result)],['data/records-response.yml',form],['app/static/map.json',JSON.stringify(map)]]) {
  const out=path.join(project,relative);fs.writeFileSync(out+'.tmp',text);fs.renameSync(out+'.tmp',out);
}
const provenance={generated_at_utc:new Date().toISOString(),source_repository:'https://github.com/Camreyn/civicresultmaps',
  source_commit:sourceCommit,source_files_modified:sourceFilesModified,catalog_sha256:result.sha256,
  generated_map_sha256:crypto.createHash('sha256').update(JSON.stringify(map)).digest('hex'),inputs,
  scope:'Public request templates, intake form and workflow-only map; no private cases, mailbox or credential input.',
  caveats:['Snapshot does not refresh at runtime. Review changes and routing before use.','County-derived display map is not a new official boundary product.']};
fs.writeFileSync(path.join(project,'data/snapshot-provenance.json'),JSON.stringify(provenance,null,2)+'\n');
console.log(JSON.stringify({cases:cases.length,states:states.length,catalog_sha256:result.sha256,source_commit:sourceCommit,source_files_modified:sourceFilesModified}));
