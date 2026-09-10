// Only allowlisted Git-visible source and staged blobs are inspected, never ignored private files.
import {execFileSync} from 'node:child_process';
import {readFileSync,lstatSync,realpathSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {assertPublicPath,validatePublicBytes} from './publication-policy.mjs';
import {loadCatalog} from '../app/catalog.mjs';
const root=path.resolve(fileURLToPath(new URL('..',import.meta.url)));
const git=(args)=>execFileSync('git',args,{cwd:root,encoding:'utf8',windowsHide:true});
if(path.resolve(git(['rev-parse','--show-toplevel']).trim()).toLowerCase()!==root.toLowerCase()) throw Error('Run inside the standalone Git repository.');
const files=[...new Set(git(['ls-files','--cached','--others','--exclude-standard','-z']).split('\0').filter(Boolean))];
for(const file of files) assertPublicPath(file); // Refuse every bad path before reading any file bodies.
for(const file of files) {
  const target=path.join(root,file),info=lstatSync(target);
  const relative=path.relative(root,realpathSync(target));
  if(!info.isFile()||info.isSymbolicLink()||info.nlink>1||relative.startsWith('..')||path.isAbsolute(relative))
    throw Error('Linked or redirected publication input: '+file);
  validatePublicBytes(file,readFileSync(target));
}
const indexed=git(['ls-files','--stage','-z']).split('\0').filter(Boolean);
for(const row of indexed) {
  const match=row.match(/^(\d+) ([0-9a-f]+) (\d+)\t(.+)$/s);
  if(!match||match[3]!=='0'||match[1]!=='100644') throw Error('Unexpected index mode or unresolved entry; review before publication.');
  const file=match[4];assertPublicPath(file);
  let bytes;
  try {bytes=execFileSync('git',['cat-file','blob',match[2]],{cwd:root,windowsHide:true,maxBuffer:2_000_001,stdio:['ignore','pipe','pipe']});}
  catch {throw Error('Could not safely inspect staged source: '+file);}
  validatePublicBytes(file,bytes);
}
for(const example of ['.private/operations/note.md','.private/collections/source.pdf','.codex/config.toml','.env.local','settings.dpapi','drafts.sqlite3','reply.eml','app/send-flow-cooldown.png']) {
  if(!git(['check-ignore','--no-index',example]).trim()) throw Error('Missing Git exclusion: '+example);
}
loadCatalog();
console.log(JSON.stringify({ok:true,git_visible_files:files.length,indexed_blobs_checked:indexed.length,private_paths_excluded:true,
  snapshot_verified:true,remote_publication_performed:false,caveat:'Limited path/token checks are not a substitute for manual content and permission review before publishing.'}));
