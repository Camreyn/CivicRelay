import path from 'node:path';
export function pythonExecutable(env=process.env) {
  const value=env.CRM_PROTON_PYTHON || (process.platform==='win32'?'C:\\Python313\\python.exe':'/usr/bin/python3');
  if(!path.isAbsolute(value)) throw Error('Configure an absolute Python executable path.');
  return value;
}
