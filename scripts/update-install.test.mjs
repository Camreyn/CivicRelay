// Windows PowerShell 5.1 updater tests. All package/process/external actions are mocked.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {pythonExecutable} from '../runtime-config.mjs';
import {workerEnvironment} from '../connector/server.mjs';

const root=path.resolve(fileURLToPath(new URL('..',import.meta.url)));
const shell=path.join(process.env.SystemRoot||'C:\\Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
const python=pythonExecutable();
const q=value=>"'"+String(value).replaceAll("'","''")+"'";
const temporary=()=>fs.mkdtempSync(path.join(os.tmpdir(),'civicrelay-update-install-O\'Brien-'));
function safeTempPath(directory,prefixes){
 assert.equal(path.dirname(path.resolve(directory)),path.resolve(os.tmpdir()));
 assert.ok(prefixes.some(prefix=>path.basename(directory).startsWith(prefix)));
 assert.equal(fs.lstatSync(directory).isSymbolicLink(),false);
}
function cleanup(directory,destination){
 safeTempPath(directory,['civicrelay-update-install-']);
 if(fs.existsSync(destination)){
  safeTempPath(destination,['CivicRelay-v9.9.9-']);
  fs.rmSync(destination,{recursive:true,force:true});
 }
 fs.rmSync(directory,{recursive:true,force:true});
}
function ps(code,directory=root,extraEnv={}){
 const source=`$ErrorActionPreference='Stop'\n. ${q(path.join(root,'scripts/install-support.ps1'))}\n$root=${q(directory)}\n${code}`;
 const result=spawnSync(shell,['-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',Buffer.from(source,'utf16le').toString('base64')],{
  cwd:directory,encoding:'utf8',windowsHide:true,shell:false,timeout:60000,
  env:{...workerEnvironment(),OS:'Windows_NT',Path:process.env.Path||process.env.PATH,
   ComSpec:path.join(process.env.SystemRoot||'C:\\Windows','System32/cmd.exe'),PATHEXT:'.COM;.EXE;.BAT;.CMD',
   CRM_PROTON_PYTHON:'',RECORDS_DESK_NODE:'',RECORDS_DESK_GH:'',...extraEnv},
 });
 if(result.error) throw result.error;
 assert.equal(result.status,0,result.stderr||result.stdout||result.error?.message);
 const line=result.stdout.trim().split(/\r?\n/).findLast(value=>value.startsWith('@@JSON@@'));
 return line?JSON.parse(line.slice(8)):null;
}
const emit=value=>`Write-Output ('@@JSON@@'+(${value}|ConvertTo-Json -Depth 12 -Compress))`;
function sourceFixture(directory){
 for(const file of ['package.json','package-lock.json','app/server.py','connector/desktop.py','scripts/check-install.mjs']){
  const target=path.join(directory,file);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,'old source sentinel','utf8');
 }
 fs.mkdirSync(path.join(directory,'.codex'),{recursive:true});
 fs.writeFileSync(path.join(directory,'.codex/config.toml'),'old host configuration sentinel','utf8');
 fs.mkdirSync(path.join(directory,'.private'),{recursive:true});
 fs.writeFileSync(path.join(directory,'.private/encrypted-mail-store.db'),'synthetic private-store sentinel','utf8');
 fs.mkdirSync(path.join(directory,'.local'),{recursive:true});
 fs.writeFileSync(path.join(directory,'.local/runtime-paths.json'),'old runtime configuration sentinel','utf8');
}
function supportFixture(directory){
 const sourceSupport=path.join(root,'scripts/install-support.ps1');
 return `. ${q(sourceSupport)}
function Add-TestEvent([string]$value) {
  if ($env:CRM_TEST_LOG) { [IO.File]::AppendAllText($env:CRM_TEST_LOG,$value+[Environment]::NewLine) }
}
function Get-CivicRelayInventory([string]$ignored) {
  Add-TestEvent 'inventory'
  return @{python=$env:CRM_TEST_PYTHON_PATH;node='C:\\Synthetic Node\\node.exe';gh=$null;bridge=$null;winget=$null}
}
function Read-Host([string]$prompt) { Add-TestEvent 'confirm'; return $env:CRM_TEST_CONFIRM }
function Invoke-RestMethod { if ($env:CRM_TEST_BUSY -eq 'dashboard') { return @{distribution='civic-records-desk'} }; throw 'synthetic no server' }
function Get-CimInstance {
  Add-TestEvent 'cim'
  if ($env:CRM_TEST_BUSY -eq 'mcp') { return [pscustomobject]@{CommandLine=($root+'\\app\\tools.mjs')} }
  if ($env:CRM_TEST_BUSY -eq 'worker') { return [pscustomobject]@{CommandLine=($root+'\\connector\\worker.py')} }
  return @()
}
function Invoke-CivicRelayDependencies([string]$destination,[hashtable]$inventory,[bool]$developer) {
  Add-TestEvent ('dependencies:'+([string]$developer))
  if ($env:CRM_TEST_MODE -eq 'dependency-fail') { throw 'synthetic dependency failure' }
}
function Stop-Process { Add-TestEvent 'UNEXPECTED:Stop-Process'; throw 'process control was not allowed' }
function Start-Process { Add-TestEvent 'UNEXPECTED:Start-Process'; throw 'auto launch was not allowed' }
function Invoke-Item { Add-TestEvent 'UNEXPECTED:Invoke-Item'; throw 'auto launch was not allowed' }
`;
}
function bridgeFixture(){
 return String.raw`import json, os, sys
from pathlib import Path
destination=Path(os.environ['CRM_TEST_DESTINATION'])
log=Path(os.environ['CRM_TEST_LOG'])
mode=os.environ.get('CRM_TEST_MODE','')
def event(value):
    with log.open('a', encoding='utf-8') as stream:
        stream.write(value+'\n')
command=sys.argv[1] if len(sys.argv)==2 else ''
if command == 'describe':
    print(json.dumps({'version':'9.9.9','destination':str(destination),'stage':'ready'}))
elif command == 'extract':
    event('extract')
    destination.mkdir(parents=True, exist_ok=True)
    if mode == 'extract-fail':
        print('synthetic extraction failure', file=sys.stderr)
        raise SystemExit(2)
    files={
      'package.json':'synthetic package',
      'package-lock.json':'synthetic lock',
      'app/server.py':'synthetic server',
      'connector/desktop.py':'synthetic connector',
      'scripts/check-install.mjs':'synthetic check',
    }
    for name, value in files.items():
        target=destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')
    print(str(destination))
elif command in ('installed','failed'):
    event(command)
else:
    print('unknown update command', file=sys.stderr)
    raise SystemExit(1)
`;
}
function fixture({confirm='INSTALL',busy='',mode='' }={}){
 const directory=temporary();
 const destination=path.join(path.dirname(directory),`CivicRelay-v9.9.9-${path.basename(directory).slice(-8)}`);
 sourceFixture(directory);
 fs.mkdirSync(path.join(directory,'scripts'),{recursive:true});
 fs.copyFileSync(path.join(root,'scripts/apply-update.ps1'),path.join(directory,'scripts/apply-update.ps1'));
 fs.writeFileSync(path.join(directory,'scripts/install-support.ps1'),supportFixture(directory),'utf8');
 fs.writeFileSync(path.join(directory,'scripts/update-command.py'),bridgeFixture(),'utf8');
 const log=path.join(directory,'events.log');
 return {directory,destination,log,env:{CRM_TEST_CONFIRM:confirm,CRM_TEST_BUSY:busy,CRM_TEST_MODE:mode,CRM_TEST_LOG:log,CRM_TEST_DESTINATION:destination,CRM_TEST_PYTHON_PATH:python}};
}
function runApply(item){
 const source=`$ErrorActionPreference='Stop'\n& ${q(path.join(item.directory,'scripts/apply-update.ps1'))}`;
 return spawnSync(shell,['-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',Buffer.from(source,'utf16le').toString('base64')],{
  cwd:item.directory,encoding:'utf8',windowsHide:true,shell:false,timeout:60000,
  env:{...workerEnvironment(),OS:'Windows_NT',Path:process.env.Path||process.env.PATH,
   ComSpec:path.join(process.env.SystemRoot||'C:\\Windows','System32/cmd.exe'),PATHEXT:'.COM;.EXE;.BAT;.CMD',
   CRM_PROTON_PYTHON:'',RECORDS_DESK_NODE:'',RECORDS_DESK_GH:'',...item.env},
 });
}
function events(item){return fs.existsSync(item.log)?fs.readFileSync(item.log,'utf8').trim().split(/\r?\n/).filter(Boolean):[];}
function oldSentinels(item){
 return Object.fromEntries(['package.json','.codex/config.toml','.private/encrypted-mail-store.db','.local/runtime-paths.json'].map(file=>[file,fs.readFileSync(path.join(item.directory,file),'utf8')]));
}
function packageFixture(item,name){
 const directory=path.join(item.directory,"Sibling Space O'Brien");
 fs.mkdirSync(directory,{recursive:true});
 fs.writeFileSync(path.join(directory,'package.json'),JSON.stringify({name,version:'9.9.9'}),'utf8');
 return directory;
}
function updateIdleResult(command){
 return ps(`
 function Invoke-RestMethod { throw 'synthetic no server' }
 function Get-CimInstance { return [pscustomobject]@{CommandLine=${q(command)} } }
 $ok=$true; $message=''; try { Assert-CivicRelayUpdateIdle $root } catch { $ok=$false; $message=$_.Exception.Message }
 ${emit('@{ok=$ok;message=$message}')}`);
}

test('updater requires exact INSTALL confirmation and cancellation leaves the current folder untouched',()=>{
 const item=fixture({confirm:''});
 try{
  const before=oldSentinels(item);const result=runApply(item);
  assert.equal(result.status,0,result.stderr||result.error?.message);
  assert.match(result.stdout,/Cancelled; no installation changes/);
  assert.deepEqual(events(item),['inventory','confirm']);
  assert.deepEqual(oldSentinels(item),before);assert.equal(fs.existsSync(item.destination),false);
 }finally{cleanup(item.directory,item.destination);}
});

for(const busy of ['dashboard','mcp','worker']) test(`updater refuses active old-root ${busy} processes without killing them`,()=>{
 const item=fixture({busy});
 try{
  const before=oldSentinels(item);const result=runApply(item);
  assert.equal(result.status,1,result.stdout||result.stderr||result.error?.message);
  assert.match(result.stdout,/Update stopped:/);
  const log=events(item);assert.ok(log.includes('inventory'));assert.ok(log.includes('confirm'));assert.ok(!log.some(value=>value.startsWith('UNEXPECTED:')));
  assert.equal(log.includes('extract'),false);assert.equal(log.includes('dependencies:false'),false);
  assert.deepEqual(oldSentinels(item),before);assert.equal(fs.existsSync(item.destination),false);
 }finally{cleanup(item.directory,item.destination);}
});

test('successful updater uses the new folder, preserves old source/private/host files, and saves only nonsecret runtime paths there',()=>{
 const item=fixture();
 try{
  const before=oldSentinels(item);const result=runApply(item);
  assert.equal(result.status,0,result.stdout||result.stderr||result.error?.message);
  assert.match(result.stdout,/The new version passed installation checks/);
  assert.deepEqual(events(item),['inventory','confirm','cim','cim','extract','cim','cim','dependencies:False','installed']);
  assert.deepEqual(oldSentinels(item),before);
  assert.equal(fs.existsSync(path.join(item.directory,'.codex/config.toml')),true);
  assert.equal(fs.existsSync(path.join(item.destination,'.codex')),false);
  assert.equal(fs.existsSync(path.join(item.destination,'.private')),false);
  const config=JSON.parse(fs.readFileSync(path.join(item.destination,'.local/runtime-paths.json'),'utf8'));
  assert.deepEqual(config,{schema_version:1,python, node:'C:\\Synthetic Node\\node.exe'});
  assert.equal(fs.existsSync(path.join(item.directory,'.local/runtime-paths.json')),true);
  assert.ok(!events(item).some(value=>value.startsWith('UNEXPECTED:')));
 }finally{cleanup(item.directory,item.destination);}
});

for(const mode of ['extract-fail','dependency-fail']) test(`updater ${mode} retains source and never records a successful install`,()=>{
 const item=fixture({mode});
 try{
  const before=oldSentinels(item);const result=runApply(item);
  assert.equal(result.status,1,result.stdout||result.stderr||result.error?.message);
  assert.match(result.stdout,/Update stopped:/);
  assert.deepEqual(oldSentinels(item),before);
  assert.equal(fs.existsSync(path.join(item.directory,'.local/runtime-paths.json')),true);
  assert.equal(fs.existsSync(path.join(item.destination,'.local/runtime-paths.json')),false);
  const log=events(item);assert.ok(log.includes('extract'));assert.equal(log.includes('installed'),false);
  if(mode==='extract-fail') assert.equal(log.includes('failed'),false);
  if(mode==='dependency-fail') assert.ok(log.includes('failed'));
 }finally{cleanup(item.directory,item.destination);}
});

test('update-idle blocks a quoted sibling CivicRelay process with spaces and apostrophes by public package identity',()=>{
 const item=fixture();
 try{
  const sibling=packageFixture(item,'civic-relay');
  const value=updateIdleResult('"'+sibling+'\\app\\tools.mjs" --synthetic');
  assert.equal(value.ok,false);assert.match(value.message,/Another CivicRelay installation/);
 }finally{cleanup(item.directory,item.destination);}
});

test('update-idle blocks a current-root worker even when the legacy idle scan does not match workers',()=>{
 const item=fixture();
 try{
  const value=updateIdleResult('"'+root+'\\connector\\worker.py" --synthetic');
  assert.equal(value.ok,false);assert.match(value.message,/still active/);
 }finally{cleanup(item.directory,item.destination);}
});

test('update-idle conservatively refuses relative app/tool process paths',()=>{
 const item=fixture();
 try{
  const value=updateIdleResult('node .\\app\\worker.py --synthetic');
  assert.equal(value.ok,false);assert.match(value.message,/relative-path app\/tool process/);
 }finally{cleanup(item.directory,item.destination);}
});

test('update-idle permits an unrelated absolute-path app with a different public package identity',()=>{
 const item=fixture();
 try{
  const sibling=packageFixture(item,'unrelated-local-tool');
  const value=updateIdleResult('"'+sibling+'\\app\\tools.mjs" --synthetic');
  assert.equal(value.ok,true,value.message);
 }finally{cleanup(item.directory,item.destination);}
});

test('dependency helper passes locked npm ci flags with lifecycle scripts disabled and no browser install for updater mode',()=>{
 const value=ps(`$script:calls=[Collections.Generic.List[object]]::new()
 function Invoke-CivicRelayCommand($Executable,$Arguments,$Label) { $script:calls.Add(@{exe=$Executable;args=@($Arguments);label=$Label}) }
 Invoke-CivicRelayDependencies $root @{python='C:\\Synthetic Python\\python.exe';node='C:\\Synthetic Node\\node.exe';gh=$null} $false
 ${emit('@{calls=@($script:calls.ToArray())}')}`);
 assert.equal(value.calls.length,3);
 assert.ok(value.calls.every(call=>call.exe==='C:\\Synthetic Node\\node.exe'));
 assert.deepEqual(value.calls[0].args.slice(1),['ci','--ignore-scripts','--include=dev','--no-audit','--no-fund']);
 assert.match(value.calls[1].args[0],/scripts[\\/]check-install\.mjs$/);
 assert.equal(value.calls[2].args[1],'test');
 assert.ok(value.calls.every(call=>!call.args.includes('install')));
});
