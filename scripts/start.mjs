import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {pythonExecutable} from '../runtime-config.mjs';
const root=fileURLToPath(new URL('..',import.meta.url));
const child=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('../app/server.py',import.meta.url))],{cwd:root,stdio:'inherit',windowsHide:true,shell:false,env:{...process.env,RECORDS_DESK_NODE:process.execPath}});
child.on('error',()=>{console.error('Could not start Python. See docs/SETUP.md.');process.exitCode=1;});
child.on('exit',code=>{process.exitCode=code??1;});
