import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const names={python:'CRM_PROTON_PYTHON',node:'RECORDS_DESK_NODE',gh:'RECORDS_DESK_GH'};

export function readRuntimePaths(directory=root) {
  const local=path.join(directory,'.local'),file=path.join(local,'runtime-paths.json');
  for(const candidate of [local,file]) {
    let stat;
    try {stat=fs.lstatSync(candidate);} catch(error) {if(error.code==='ENOENT')continue;throw error;}
    if(stat.isSymbolicLink()) throw Error('Refusing a linked runtime configuration. See docs/INSTALL.md.');
    if(candidate===file&&(!stat.isFile()||stat.size>8192)) throw Error('Invalid runtime configuration.');
  }
  if(!fs.existsSync(file))return {};
  let config;
  try {config=JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));} catch {throw Error('Invalid JSON in .local/runtime-paths.json.');}
  if(!config||Array.isArray(config)||config.schema_version!==1)throw Error('Unsupported runtime-paths schema.');
  for(const [key,value] of Object.entries(config)) {
    if(key==='schema_version')continue;
    if(!Object.hasOwn(names,key)||typeof value!=='string'||!/^[A-Za-z]:[\\/]/.test(value)||!/\.exe$/i.test(value)||/[\x00-\x1f"<>|?*]/.test(value))
      throw Error('Runtime configuration accepts only absolute local python/node/gh executable paths.');
  }
  return config;
}

export function runtimeExecutable(kind,env=process.env,directory=root) {
  const defaults={python:process.platform==='win32'?'C:\\Python313\\python.exe':'/usr/bin/python3',node:process.execPath,gh:'C:\\Program Files\\GitHub CLI\\gh.exe'};
  if(!Object.hasOwn(names,kind))throw Error('Unknown runtime.');
  const value=env[names[kind]]||readRuntimePaths(directory)[kind]||defaults[kind];
  if(typeof value!=='string'||!path.isAbsolute(value)||/[\x00-\x1f"<>|?*]/.test(value))throw Error('Configure an absolute runtime executable path.');
  return value;
}
export function pythonExecutable(env=process.env) {return runtimeExecutable('python',env);}
