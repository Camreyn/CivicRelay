import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {renderToolReference} from './generate-tool-reference.mjs';
import {TOOLS as deskTools} from '../app/static/tool-contracts.mjs';
import {TOOLS as mailTools} from '../connector/server.mjs';
const root=fileURLToPath(new URL('..',import.meta.url));
const docs=['README.md','AGENTS.md','SECURITY.md',...fs.readdirSync(path.join(root,'docs')).filter(x=>x.endsWith('.md')).map(x=>'docs/'+x)];
const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
let links=0,commands=0;
for(const file of docs) {
  const content=fs.readFileSync(path.join(root,file),'utf8');
  for(const match of content.matchAll(/\[[^\]\n]*\]\(([^)\s]+)\)/g)) {
    const href=match[1];if(/^(https?:|mailto:|#)/.test(href)) continue;
    const target=path.resolve(root,path.dirname(file),decodeURIComponent(href.split('#')[0]));
    const relative=path.relative(root,target);
    if(relative.startsWith('..')||path.isAbsolute(relative)||!fs.statSync(target).isFile()) throw Error('Broken or outside-project documentation link in '+file+': '+href);
    links++;
  }
  for(const match of content.matchAll(/npm(?:\.cmd)? run ([\w:-]+)/g)) {
    if(!pkg.scripts[match[1]]) throw Error('Unknown documented npm script in '+file+': '+match[1]);
    commands++;
  }
}
if(fs.readFileSync(path.join(root,'docs/TOOL-REFERENCE.md'),'utf8').replaceAll('\r\n','\n')!==renderToolReference()) throw Error('Tool documentation drifted; run npm.cmd run docs:generate and review the changes.');
console.log(JSON.stringify({ok:true,markdown_files:docs.length,local_links_checked:links,documented_commands_checked:commands,native_tool_schemas:deskTools.length+mailTools.length,network_accessed:false}));
