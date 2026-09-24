// Windows PowerShell 5.1 tests: package installation and external actions are mocked.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {readRuntimePaths,runtimeExecutable,pythonExecutable} from '../runtime-config.mjs';
import {workerEnvironment} from '../connector/server.mjs';
const root=path.resolve(fileURLToPath(new URL('..',import.meta.url)));
const shell=path.join(process.env.SystemRoot||'C:\\Windows','System32/WindowsPowerShell/v1.0/powershell.exe');
const q=value=>"'"+value.replaceAll("'","''")+"'";
function temporary(){return fs.mkdtempSync(path.join(os.tmpdir(),"civic-relay-install-test-O'Brien-"));}
function cleanup(directory){
 assert.equal(path.dirname(path.resolve(directory)),path.resolve(os.tmpdir()));
 assert.ok(path.basename(directory).startsWith('civic-relay-install-test-'));
 assert.equal(fs.lstatSync(directory).isSymbolicLink(),false);
 fs.rmSync(directory,{recursive:true,force:true});
}
function ps(code,directory=root){
 const source=`$ErrorActionPreference='Stop'\n. ${q(path.join(root,'scripts/install-support.ps1'))}\n$root=${q(directory)}\n${code}`;
 const result=spawnSync(shell,['-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',Buffer.from(source,'utf16le').toString('base64')],
  {cwd:directory,encoding:'utf8',windowsHide:true,shell:false,timeout:30000,
   env:{...workerEnvironment(),OS:'Windows_NT',Path:process.env.Path||process.env.PATH,ProgramFiles:process.env.ProgramFiles,
    ComSpec:path.join(process.env.SystemRoot||'C:\\Windows','System32/cmd.exe'),PATHEXT:'.COM;.EXE;.BAT;.CMD',
    CRM_PROTON_PYTHON:'',RECORDS_DESK_NODE:'',RECORDS_DESK_GH:''}});
 assert.equal(result.status,0,result.stderr||result.stdout||result.error?.message);
 return JSON.parse(result.stdout.trim().split(/\r?\n/).findLast(line=>line.startsWith('@@JSON@@')).slice(8));
}
const emit=value=>`Write-Output ('@@JSON@@'+(${value}|ConvertTo-Json -Depth 12 -Compress))`;
function sourceFixture(directory){
 for(const file of ['package.json','package-lock.json','app/server.py','connector/desktop.py','scripts/check-install.mjs']){
  const target=path.join(directory,file);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,'synthetic fixture');
 }
}
const complete=`@{python='C:\\Synthetic Python\\python.exe';node='C:\\Synthetic Node\\node.exe';gh='C:\\Synthetic GH\\gh.exe';bridge='C:\\Synthetic Bridge\\bridge-gui.exe';winget='C:\\WindowsApps\\winget.exe'}`;

test('all PowerShell entry points parse under the Windows 5.1 host',()=>{
 const result=ps(`$failures=@(); foreach($file in (Get-ChildItem -LiteralPath ${q(root)} -Filter '*.ps1')+(Get-ChildItem -LiteralPath ${q(path.join(root,'scripts'))} -Filter '*.ps1')) { $tokens=$null; $errors=$null; $null=[Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors); if($errors){$failures+=$errors.Message} }; ${emit('@{errors=@($failures)}')}`);
 assert.deepEqual(result.errors,[]);
});

test('installer plan includes only selected missing requirements; fixed WinGet arguments retain integrity checks',()=>{
 const value=ps(`$empty=@{}; $all=${complete}; $partial=@{python=$all.python}; $arguments=@{}; foreach($id in (Get-CivicRelayInstallPlan $empty $true $true)) {$arguments[$id]=@(Get-CivicRelayPackageArguments $id)}; $blocked=$false; try {Get-CivicRelayPackageArguments 'Untrusted.Package'} catch {$blocked=$true}; ${emit('@{core=@(Get-CivicRelayInstallPlan $empty $false $false);full=@(Get-CivicRelayInstallPlan $empty $true $true);existing=@(Get-CivicRelayInstallPlan $all $true $true);partial=@(Get-CivicRelayInstallPlan $partial $false $false);arguments=$arguments;blocked=$blocked}')}`);
 assert.deepEqual(value.core,['Python.Python.3.13','OpenJS.NodeJS.LTS']);
 assert.deepEqual(value.full,[...value.core,'Proton.ProtonMailBridge','GitHub.cli']);
 assert.deepEqual(value.existing,[]);assert.deepEqual(value.partial,['OpenJS.NodeJS.LTS']);assert.equal(value.blocked,true);
 for(const [id,args] of Object.entries(value.arguments)){
  assert.equal(args[args.indexOf('--id')+1],id);assert.equal(args[args.indexOf('--source')+1],'winget');
  assert.ok(args.includes('--exact'));assert.ok(args.includes('--accept-package-agreements'));
  assert.ok(!args.some(x=>/ignore-security|force|allow-reboot|uninstall|override/.test(x)));
 }
 assert.ok(value.arguments['Python.Python.3.13'].includes('Include_tcltk=1 InstallLauncherAllUsers=0'));
});

test('runtime file interoperates across PowerShell/Node, overrides are process-local, and repeat saves are safe',()=>{
 const directory=temporary();
 try{
  const beforeUser=ps(emit("@{python=[Environment]::GetEnvironmentVariable('CRM_PROTON_PYTHON','User')}"));
  const value=ps(`$paths=${complete}; Save-CivicRelayRuntimePaths $root $paths; Save-CivicRelayRuntimePaths $root $paths; $env:CRM_PROTON_PYTHON='C:\\Override\\python.exe'; Use-CivicRelayRuntimePaths $root; ${emit("@{python=$env:CRM_PROTON_PYTHON;node=$env:RECORDS_DESK_NODE;gh=$env:RECORDS_DESK_GH;user=[Environment]::GetEnvironmentVariable('CRM_PROTON_PYTHON','User')}")}`,directory);
  assert.equal(value.python,'C:\\Override\\python.exe');assert.equal(value.node,'C:\\Synthetic Node\\node.exe');assert.equal(value.user,beforeUser.python);
  const config=readRuntimePaths(directory);assert.equal(config.schema_version,1);assert.deepEqual(Object.keys(config).sort(),['gh','node','python','schema_version']);
  assert.equal(runtimeExecutable('python',{},directory),config.python);
  assert.equal(runtimeExecutable('python',{CRM_PROTON_PYTHON:pythonExecutable()},directory),pythonExecutable());
  assert.equal(fs.readdirSync(path.join(directory,'.local')).length,1);
 }finally{cleanup(directory);}
});

test('runtime paths reject malformed/unknown/relative/control/linked configuration without execution',()=>{
 const directory=temporary();
 try{
  fs.mkdirSync(path.join(directory,'.local'));
  const file=path.join(directory,'.local/runtime-paths.json');
  for(const config of [null,[],{schema_version:2},{schema_version:'1'},{schema_version:true},{schema_version:1,password:'not a setting'},{schema_version:1,python:'python.exe'},
   {schema_version:1,node:'C:node.exe'},{schema_version:1,gh:'\\\\server\\share\\gh.exe'},
   {schema_version:1,python:'C:\\bad\npython.exe'},{schema_version:1,node:'C:\\node.cmd'}]){
   fs.writeFileSync(file,JSON.stringify(config));assert.throws(()=>readRuntimePaths(directory));
   const result=ps(`$failed=$false; try {$null=Read-CivicRelayRuntimePaths $root} catch {$failed=$true}; ${emit('@{failed=$failed}')}`,directory);
   assert.equal(result.failed,true,JSON.stringify(config));
  }
  fs.writeFileSync(file,'not JSON');assert.throws(()=>readRuntimePaths(directory),/JSON/);
  fs.writeFileSync(file,' '.repeat(8193));assert.throws(()=>readRuntimePaths(directory),/Invalid/);
  fs.rmSync(file);fs.rmdirSync(path.join(directory,'.local'));
  const target=path.join(directory,'synthetic-target');fs.mkdirSync(target);fs.symlinkSync(target,path.join(directory,'.local'),'junction');
  assert.throws(()=>readRuntimePaths(directory),/linked/);
  const linked=ps(`$failed=$false; try {$null=Read-CivicRelayRuntimePaths $root} catch {$failed=$true}; ${emit('@{failed=$failed}')}`,directory);
  assert.equal(linked.failed,true);fs.unlinkSync(path.join(directory,'.local'));
 }finally{cleanup(directory);}
});

test('read-only probes verify real Python/Tk and Node/npm without enrolling or connecting to mail',()=>{
 const result=ps(`$diagnostic=''; try {$diagnostic=& ${q(process.execPath)} --version} catch {$diagnostic=$_.Exception.Message}; ${emit(`@{diagnostic=$diagnostic;python=Test-CivicRelayRuntime 'python' ${q(pythonExecutable())};node=Test-CivicRelayRuntime 'node' ${q(process.execPath)};missing=Test-CivicRelayRuntime 'python' 'C:\\not-installed\\python.exe';alias=Test-CivicRelayRuntime 'python' 'C:\\Example\\Microsoft\\WindowsApps\\python.exe'}`)}`);
 assert.equal(result.python,true,JSON.stringify(result));assert.equal(result.node,true,JSON.stringify(result));assert.equal(result.missing,false);assert.equal(result.alias,false);
});

test('detection rejects a broken explicit runtime instead of switching installations silently',()=>{
 const result=ps(`function Test-CivicRelayRuntime {return $false}; $env:CRM_PROTON_PYTHON='C:\\Missing\\python.exe'; $failed=$false; try {Find-CivicRelayRuntime 'python' @{}} catch {$failed=$_.Exception.Message}; ${emit('@{failed=$failed}')}`);
 assert.match(result.failed,/No alternate runtime was silently selected/);
});

test('fresh ZIP-style install and repeat install preserve existing assistant/private sentinels',()=>{
 const directory=temporary();
 try{
  sourceFixture(directory);fs.mkdirSync(path.join(directory,'.codex'));fs.writeFileSync(path.join(directory,'.codex/config.toml'),'existing private host choices');
  fs.mkdirSync(path.join(directory,'.private'));fs.writeFileSync(path.join(directory,'.private/synthetic.txt'),'synthetic mail sentinel');
  const result=ps(`
   $script:events=[Collections.Generic.List[string]]::new(); $script:inventory=@{winget='C:\\WindowsApps\\winget.exe'};
   function Assert-CivicRelayIdle {$script:events.Add('idle')}
   function Get-CivicRelayInventory {return $script:inventory}
   function Install-CivicRelayPackage($Winget,$Id) { $script:events.Add($Id); $key=@{'Python.Python.3.13'='python';'OpenJS.NodeJS.LTS'='node';'Proton.ProtonMailBridge'='bridge';'GitHub.cli'='gh'}[$Id]; $script:inventory[$key]=(${complete})[$key] }
   function Invoke-CivicRelayDependencies {$script:events.Add('dependencies')}
   function Invoke-CivicRelayCommand {throw 'No native process should run in this fixture'}
   Invoke-CivicRelayInstall $root $script:inventory $true $true $true $false
   $first=@($script:events.ToArray()); $script:events.Clear()
   Invoke-CivicRelayInstall $root $script:inventory $true $true $true $false
   ${emit('@{first=$first;repeat=@($script:events.ToArray());paths=(Read-CivicRelayRuntimePaths $root)}')}`,directory);
  assert.deepEqual(result.first,['idle','Python.Python.3.13','OpenJS.NodeJS.LTS','Proton.ProtonMailBridge','GitHub.cli','dependencies']);
  assert.deepEqual(result.repeat,['idle','dependencies']);assert.equal(result.paths.python,'C:\\Synthetic Python\\python.exe');
  assert.equal(fs.readFileSync(path.join(directory,'.codex/config.toml'),'utf8'),'existing private host choices');
  assert.equal(fs.readFileSync(path.join(directory,'.private/synthetic.txt'),'utf8'),'synthetic mail sentinel');
  assert.equal(fs.existsSync(path.join(directory,'.git')),false,'source ZIP needs no Git');
 }finally{cleanup(directory);}
});

test('missing WinGet, package failure, failed postcheck, and failed self-tests stop without saving success',()=>{
 for(const mode of ['winget','package','postcheck','self-tests']){
  const directory=temporary();
  try{
   sourceFixture(directory);
   const result=ps(`
    $script:events=[Collections.Generic.List[string]]::new(); $mode=${q(mode)}; $input=@{winget='C:\\WindowsApps\\winget.exe'}; if($mode -eq 'winget'){$input=@{}}
    function Assert-CivicRelayIdle {}
    function Install-CivicRelayPackage { $script:events.Add('package'); if($mode -eq 'package'){throw 'synthetic package failure'} }
    function Get-CivicRelayInventory { if($mode -eq 'postcheck'){return @{}}; return ${complete} }
    function Invoke-CivicRelayDependencies { $script:events.Add('tests'); throw 'synthetic self-test failure' }
    function Set-CivicRelayAssistantConfig {throw 'should not reach assistant setup'}
    $errorMessage=''; try {Invoke-CivicRelayInstall $root $input $false $false $true $false} catch {$errorMessage=$_.Exception.Message}
    ${emit('@{message=$errorMessage;events=@($script:events.ToArray())}')}`,directory);
   assert.ok(result.message);assert.equal(fs.existsSync(path.join(directory,'.local/runtime-paths.json')),false);
   if(mode==='winget')assert.deepEqual(result.events,[]);
   if(mode==='package')assert.deepEqual(result.events,['package']);
   if(mode==='postcheck')assert.ok(!result.events.includes('tests'));
  }finally{cleanup(directory);}
 }
});

test('dependency actions use exact Node/npm, locked packages without lifecycle scripts, and optional browser only',()=>{
 const directory=temporary();
 try{
  const result=ps(`$script:calls=[Collections.Generic.List[object]]::new(); function Invoke-CivicRelayCommand($Executable,$Arguments,$Label) {$script:calls.Add(@{exe=$Executable;args=$Arguments;label=$Label})}; Invoke-CivicRelayDependencies $root (${complete}) $false; $core=@($script:calls.ToArray()); $script:calls.Clear(); Invoke-CivicRelayDependencies $root (${complete}) $true; ${emit('@{core=$core;developer=@($script:calls.ToArray())}')}`,directory);
  assert.equal(result.core.length,3);assert.equal(result.developer.length,5);
  assert.ok(result.core.every(call=>call.exe==='C:\\Synthetic Node\\node.exe'));
  assert.deepEqual(result.core[0].args.slice(1),['ci','--ignore-scripts','--include=dev','--no-audit','--no-fund']);
  assert.equal(result.core[2].args[1],'test');assert.deepEqual(result.developer[3].args.slice(1),['install','chromium']);
 }finally{cleanup(directory);}
});

test('busy dashboard/MCP checks fail without killing any process',()=>{
 const result=ps(`
  function Invoke-RestMethod {return @{distribution='civic-records-desk'}}
  $http='';try {Assert-CivicRelayIdle $root} catch {$http=$_.Exception.Message}
  function Invoke-RestMethod {throw 'synthetic no server'}
  function Get-CimInstance {return @{CommandLine=($root+'\\app\\tools.mjs')}}
  $mcp='';try {Assert-CivicRelayIdle $root} catch {$mcp=$_.Exception.Message}
  ${emit('@{http=$http;mcp=$mcp}')}`);
 assert.match(result.http,/running CivicRelay/);assert.match(result.mcp,/active dashboard or MCP/);
});
