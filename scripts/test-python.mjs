import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {pythonExecutable} from '../runtime-config.mjs';
const root=fileURLToPath(new URL('..',import.meta.url));
for(const folder of ['app','connector']) {
  const child=spawnSync(pythonExecutable(),['-E','-s','-S','-m','unittest','discover','-s',folder,'-p','test_*.py','-v'],{cwd:root,stdio:'inherit',windowsHide:true,shell:false,env:{...process.env,RECORDS_DESK_NODE:process.execPath}});
  if(child.status!==0) process.exit(child.status??1);
}
