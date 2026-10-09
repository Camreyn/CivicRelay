// Maintainer release rehearsal: actual verified ZIP + installer, fictional user stores only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {pythonExecutable} from '../runtime-config.mjs';
import {workerEnvironment} from '../connector/server.mjs';
const root = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const asset = path.join(root, '.local/release', `civicrelay-v${pkg.version}.zip`);
const raw = fs.readFileSync(asset), digest = crypto.createHash('sha256').update(raw).digest('hex');
const python = pythonExecutable(), base = fs.mkdtempSync(path.join(os.tmpdir(), 'civicrelay-update-rehearsal-'));
const old = path.join(base, 'old'), appdata = path.join(base, 'fictional-AppData');
const id = crypto.randomBytes(16).toString('hex'), destination = path.join(base, `CivicRelay-v${pkg.version}-${id.slice(0, 8)}`);
function write(relative, contents) {
  const target = path.join(old, relative); fs.mkdirSync(path.dirname(target), {recursive: true}); fs.writeFileSync(target, contents);
}
let success = false;
try {
  fs.mkdirSync(appdata, {recursive: true});
  fs.writeFileSync(path.join(appdata, 'records.sqlite3'), 'fictional records sentinel');
  fs.writeFileSync(path.join(appdata, 'settings.dpapi'), 'fictional credentials sentinel');
  write('package.json', JSON.stringify({name: 'civic-relay', version: '0.0.0'}));
  write('.private/research.txt', 'fictional research sentinel');
  write('.codex/config.toml', 'fictional host permission sentinel');
  write('.local/runtime-paths.json', JSON.stringify({schema_version: 1, python, node: process.execPath}));
  for (const file of ['app/updates.py', 'scripts/update-command.py', 'scripts/apply-update.ps1', 'scripts/runtime-paths.ps1', 'scripts/install-support.ps1']) write(file, fs.readFileSync(path.join(root, file)));
  // The real installer functions run, but this fixture has no live process inventory.
  fs.appendFileSync(path.join(old, 'scripts/install-support.ps1'), '\nfunction Assert-CivicRelayUpdateIdle { }\nfunction Read-Host { return "INSTALL" }\n');
  const probe = spawnSync(python, ['-B', '-E', '-s', '-S', '-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(z.read("civicrelay-release.json").decode())', asset], {encoding: 'utf8', windowsHide: true, shell: false});
  assert.equal(probe.status, 0, probe.stderr);
  const manifest = JSON.parse(probe.stdout);
  write('.local/updates/' + id + '.zip', raw);
  write('.local/updates/status.json', JSON.stringify({schema_version: 1, automatic_checks: false, last_checked_at: null, latest: null, last_error: null,
    approved: {id, approved_at: 1, stage: 'ready', destination,
      release: {version: pkg.version, commit: manifest.commit, package: {sha256: digest, size: raw.length}}}}));
  const sentinels = [path.join(old, 'package.json'), path.join(old, '.private/research.txt'), path.join(old, '.codex/config.toml'), path.join(old, '.local/runtime-paths.json'), path.join(appdata, 'records.sqlite3'), path.join(appdata, 'settings.dpapi')];
  const before = sentinels.map(file => fs.readFileSync(file));
  const shell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32/WindowsPowerShell/v1.0/powershell.exe');
  const result = spawnSync(shell, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(old, 'scripts/apply-update.ps1')], {
    // Windows CI's full synthetic suite takes about nine minutes on hosted runners.
    // Keep a bounded rehearsal timeout without skipping or truncating those tests.
    cwd: old, encoding: 'utf8', windowsHide: true, shell: false, timeout: 900000, maxBuffer: 4_000_000,
    env: {...workerEnvironment(), OS: 'Windows_NT', Path: process.env.Path || process.env.PATH,
      ComSpec: path.join(process.env.SystemRoot || 'C:\\Windows', 'System32/cmd.exe'), PATHEXT: '.COM;.EXE;.BAT;.CMD',
      LOCALAPPDATA: appdata, APPDATA: appdata, CRM_PROTON_PYTHON: python, RECORDS_DESK_NODE: process.execPath,
      npm_config_cache: path.join(base, 'npm-cache'), npm_config_update_notifier: 'false'},
  });
  assert.equal(result.status, 0, (result.stderr || result.stdout || result.error?.message || '').slice(-10000));
  assert.match(result.stdout, /The new version passed installation checks/);
  assert.equal(JSON.parse(fs.readFileSync(path.join(old, '.local/updates/status.json'), 'utf8')).approved.stage, 'installed');
  for (const [index, file] of sentinels.entries()) assert.deepEqual(fs.readFileSync(file), before[index], 'A fictional old user-data sentinel changed');
  assert.equal(fs.existsSync(path.join(destination, '.private')), false);
  assert.equal(fs.existsSync(path.join(destination, '.codex')), false);
  assert.equal(JSON.parse(fs.readFileSync(path.join(destination, 'package.json'), 'utf8')).version, pkg.version);
  for (const [file, expected] of Object.entries(manifest.files)) assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(destination, file))).digest('hex'), expected);
  success = true;
  console.log(JSON.stringify({ok: true, version: pkg.version, source_commit: manifest.commit, package_sha256: digest, actual_installer_and_dependency_tests: true,
    old_source_and_fictional_data_unchanged: true, live_process_inventory_mocked: true, app_activation_performed: false}));
} finally {
  if (success) {
    assert.equal(path.dirname(path.resolve(base)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(base).startsWith('civicrelay-update-rehearsal-'));
    assert.equal(fs.lstatSync(base).isSymbolicLink(), false);
    assert.equal(path.dirname(fs.realpathSync(base)), fs.realpathSync(os.tmpdir()));
    // Only the explicitly verified disposable rehearsal root is removed.
    fs.rmSync(base, {recursive: true});
  } else console.error('Failed synthetic rehearsal retained for inspection: ' + base);
}
