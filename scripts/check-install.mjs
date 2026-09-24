// Read-only dependency smoke check. No application worker, store, mail or server.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import {pythonExecutable} from '../runtime-config.mjs';

try {
  if(process.platform!=='win32'||Number(process.versions.node.split('.')[0])<22)throw Error('Windows and Node.js 22 or later are required.');
  await import('@modelcontextprotocol/server');
  await import('@modelcontextprotocol/server/stdio');
  const {loadCatalog}=await import('../app/catalog.mjs');
  loadCatalog();
  const result=spawnSync(pythonExecutable(),['-B','-E','-s','-S','-c',
    'import sys,tkinter,ssl,sqlite3,ctypes; assert sys.version_info[:2] == (3,13); assert ctypes.sizeof(ctypes.c_void_p) == 8; tkinter.Tcl(); print(sys.version.split()[0])'],
    {encoding:'utf8',windowsHide:true,shell:false,timeout:15000});
  if(result.error)throw Error(`Could not launch Python (${result.error.code||'process error'}). Run setup in a normal local Windows session; do not change organization policy.`);
  if(result.status!==0)throw Error('Python 3.13 (64-bit) with working Tcl/Tk, SSL, SQLite and ctypes is required.');
  const version=JSON.parse(fs.readFileSync(new URL('../package.json',import.meta.url),'utf8')).version;
  console.log(`CivicRelay ${version}: Node ${process.versions.node}, Python ${result.stdout.trim()}, MCP dependencies and public catalog OK. No mail or network accessed.`);
} catch(error) {
  console.error(`Dependency check failed: ${error.message}\nRun Install CivicRelay.cmd; see docs/INSTALL.md.`);
  process.exitCode=1;
}
