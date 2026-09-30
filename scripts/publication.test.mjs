import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {assertPublicPath,sensitiveMarkers,validatePublicBytes} from './publication-policy.mjs';
import {REVIEWED_SCREENSHOTS} from './reviewed-screenshots.mjs';
test('publication path policy admits release source and refuses private paths/traversal',()=>{
  for(const file of ['README.md','.gitattributes','Open CivicRelay.cmd','Install CivicRelay.cmd','Check CivicRelay.cmd','Open Proton Setup.cmd','docs/INSTALL.md','docs/SETUP.md','app/static/index.html','.github/workflows/ci.yml']) assert.doesNotThrow(()=>assertPublicPath(file));
  for(const file of ['.private/notes.md','.local/runtime-paths.json','.codex/config.toml','app/reply.eml','docs/screenshot.png','docs/images/unreviewed.jpg','docs/images/demo-national-overview.png','docs/images/../images/demo-national-overview.jpg','../README.md','app/../README.md','unknown.txt','app\\source.py']) assert.throws(()=>assertPublicPath(file));
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
test('only the exact reviewed screenshot bytes are publishable, including staged-blob validation',()=>{
  assert.equal(Object.keys(REVIEWED_SCREENSHOTS).length,3);
  for(const file of Object.keys(REVIEWED_SCREENSHOTS)) {
    const bytes=readFileSync(new URL('../'+file,import.meta.url));
    assert.doesNotThrow(()=>validatePublicBytes(file,bytes));
    const changed=Buffer.from(bytes);changed[100]^=1;
    for(const value of [changed,Buffer.from('replacement'),Buffer.concat([bytes,Buffer.from('private note')])])
      assert.throws(()=>validatePublicBytes(file,value),/privacy review/);
    assert.throws(()=>validatePublicBytes('docs/images/unreviewed.jpg',bytes),/private Git-visible path/);
  }
});
test('reviewed demo JPEGs have no metadata comments, EXIF or trailing payloads',()=>{
  for(const file of Object.keys(REVIEWED_SCREENSHOTS)) {
    const bytes=readFileSync(new URL('../'+file,import.meta.url));
    assert.equal(bytes.readUInt16BE(0),0xffd8);
    assert.equal(bytes.readUInt16BE(bytes.length-2),0xffd9);
    let offset=2,sawFrame=false,sawScan=false;
    while(offset<bytes.length-2) {
      assert.equal(bytes[offset],0xff);
      const marker=bytes[offset+1],size=bytes.readUInt16BE(offset+2);
      assert.ok(size>=2&&offset+2+size<=bytes.length);
      assert.ok([0xe0,0xdb,0xc0,0xc4,0xda].includes(marker),'Unexpected JPEG metadata or marker');
      if(marker===0xe0) {
        assert.equal(size,16);assert.equal(bytes.toString('ascii',offset+4,offset+9),'JFIF\0');
        assert.equal(bytes.readUInt16BE(offset+16),0); // No embedded thumbnail.
      }
      if(marker===0xc0) {
        assert.equal(bytes.readUInt16BE(offset+5),712);
        assert.equal(bytes.readUInt16BE(offset+7),1265);sawFrame=true;
      }
      offset+=2+size;
      if(marker===0xda) {
        sawScan=true;
        // Baseline JPEG scan permits byte-stuffing and restart markers only.
        for(;offset<bytes.length-2;offset++) if(bytes[offset]===0xff) {
          const next=bytes[++offset];
          assert.ok(next===0||next>=0xd0&&next<=0xd7,'Unexpected scan payload marker');
        }
        break;
      }
    }
    assert.ok(sawFrame&&sawScan);
  }
});
