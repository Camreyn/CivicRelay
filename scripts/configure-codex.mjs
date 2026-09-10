// Generates ignored local configuration only; never edits global trust/settings.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {pythonExecutable} from '../runtime-config.mjs';
const root=path.resolve(fileURLToPath(new URL('..',import.meta.url)));
export function buildMcpConfig(template, values) {
  for(const [key,value] of Object.entries(values)) {
    if(!path.isAbsolute(value)||/[\r\n'\x00-\x1f]/.test(value)) throw Error('Configuration requires absolute paths without TOML control characters.');
    template=template.replaceAll(`__${key}__`,value);
  }
  if(/__(NODE|ROOT|PYTHON|GH)__/.test(template)) throw Error('Missing runtime path.');
  return template;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if(process.platform!=='win32') throw Error('This project requires Windows DPAPI and desktop confirmation.');
  if(process.argv.length!==2) throw Error('Run without arguments; existing configurations are never overwritten.');
  const values={ROOT:root,NODE:process.execPath,PYTHON:pythonExecutable(),GH:process.env.RECORDS_DESK_GH||'C:\\Program Files\\GitHub CLI\\gh.exe'};
  const config=buildMcpConfig(fs.readFileSync(new URL('../docs/mcp-config.example.toml',import.meta.url),'utf8'),values);
  for(const file of [values.NODE,values.PYTHON]) if(!fs.statSync(file).isFile()) throw Error('Configured runtime executable does not exist.');
  const directory=path.join(root,'.codex');
  fs.mkdirSync(directory,{recursive:true});
  if(fs.lstatSync(directory).isSymbolicLink()) throw Error('Refusing a linked configuration directory.');
  const target=path.join(directory,'config.toml');
  fs.writeFileSync(target,config,{encoding:'utf8',flag:'wx'});
  console.log('Created ignored .codex/config.toml. Review it, open this trusted project, and restart its mail MCP connections. Global settings were not changed.');
}
