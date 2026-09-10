import test from 'node:test';
import assert from 'node:assert/strict';
import {assertPublicPath,sensitiveMarkers,validatePublicBytes} from './publication-policy.mjs';
test('publication path policy admits release source and refuses private paths/traversal',()=>{
  for(const file of ['README.md','.gitattributes','Open CivicRelay.cmd','docs/SETUP.md','app/static/index.html','.github/workflows/ci.yml']) assert.doesNotThrow(()=>assertPublicPath(file));
  for(const file of ['.private/notes.md','.codex/config.toml','app/reply.eml','docs/screenshot.png','../README.md','app/../README.md','unknown.txt','app\\source.py']) assert.throws(()=>assertPublicPath(file));
});
test('token detection reports categories without exposing matched values',()=>{
  const fixtures=['ghp_'+'A'.repeat(40),'sk-proj-'+'Z'.repeat(50),'AKIA'+'Z'.repeat(16),'-----BEGIN '+'PRIVATE KEY-----'];
  for(const value of fixtures) {
    assert.equal(sensitiveMarkers(value).length,1);
    assert.throws(()=>validatePublicBytes('app/source.py',Buffer.from(value)),error=>error.message.includes('value withheld')&&!error.message.includes(value));
  }
  assert.deepEqual(sensitiveMarkers('password = "synthetic-test-credential"'),[]);
});
test('publication content rejects binary or malformed UTF-8 and allows reviewed text',()=>{
  assert.throws(()=>validatePublicBytes('app/source.py',Buffer.from([0,1,2])),/binary/);
  assert.throws(()=>validatePublicBytes('app/source.py',Buffer.from([0xff])),/UTF-8/);
  assert.doesNotThrow(()=>validatePublicBytes('README.md',Buffer.from('# CivicRelay\n')));
});
