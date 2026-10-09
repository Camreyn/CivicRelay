// Maintainer-only packaging of the exact clean, reviewed Git commit. No private inputs.
import {execFileSync, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {assertPublicPath, validatePublicBytes} from './publication-policy.mjs';
import {pythonExecutable} from '../runtime-config.mjs';
const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const git = args => execFileSync('git', args, {cwd: root, encoding: 'utf8', windowsHide: true});
if (path.resolve(git(['rev-parse', '--show-toplevel']).trim()).toLowerCase() !== root.toLowerCase() || git(['status', '--porcelain']).trim()) throw Error('Package only a clean standalone checkout of the reviewed release commit.');
const commit = git(['rev-parse', 'HEAD']).trim();
const files = git(['ls-files', '-z']).split('\0').filter(Boolean);
for (const file of files) assertPublicPath(file);
for (const file of files) {
  const bytes = execFileSync('git', ['show', `${commit}:${file}`], {cwd: root, windowsHide: true, maxBuffer: 2_000_001});
  validatePublicBytes(file, bytes);
}
const child = spawnSync(pythonExecutable(), ['-B', '-E', '-s', '-S', path.join(root, 'scripts/build-update-package.py')], {
  cwd: root, encoding: 'utf8', windowsHide: true, shell: false,
  input: JSON.stringify({commit, files}), maxBuffer: 1_000_000,
});
if (child.status !== 0) throw Error(child.stderr || 'Release packaging did not complete.');
console.log(child.stdout.trim());
