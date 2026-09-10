import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {loadCatalog,validateCatalog} from '../app/catalog.mjs';
import {pythonExecutable} from '../runtime-config.mjs';
import {buildMcpConfig} from './configure-codex.mjs';
test('self-contained snapshot retains existing catalog and form identity',()=>{
 const c=loadCatalog();assert.equal(c.states.length,51);assert.equal(c.cases.length,14);
 assert.equal(c.sha256,'2a1fb5841220f9b76d4e19a59f609942dcd7daf344cd185463d781745e8ddee4');
 const p=JSON.parse(fs.readFileSync(new URL('../data/snapshot-provenance.json',import.meta.url)));
 assert.equal(p.catalog_sha256,c.sha256);assert.ok(p.inputs.length>=12);
 const map=JSON.parse(fs.readFileSync(new URL('../app/static/map.json',import.meta.url)));
 assert.equal(map.states.length,51);assert.ok(map.states.every(s=>s.path&&Number.isFinite(s.x)&&Number.isFinite(s.y)));
});
test('snapshot drift or personalized correspondence fails closed',()=>{
 const c=structuredClone(loadCatalog());c.cases[0].body='Personalized text';assert.throws(()=>validateCatalog(c),/hash/);
 const {sha256,...payload}=c;c.sha256=crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
 assert.throws(()=>validateCatalog(c),/personalized/);
});
test('runtime executable configuration must be absolute',()=>{
 assert.throws(()=>pythonExecutable({CRM_PROTON_PYTHON:'relative-python'}),/absolute/);assert.ok(pythonExecutable({}));
});

test('local MCP configuration preserves both narrow tool sets and approval prompts',()=>{
 const template=fs.readFileSync(new URL('../docs/mcp-config.example.toml',import.meta.url),'utf8');
 const root=process.cwd();
 const result=buildMcpConfig(template,{ROOT:root,NODE:process.execPath,PYTHON:pythonExecutable(),GH:process.execPath});
 assert.equal((result.match(/approval_mode = 'prompt'/g)||[]).length,4);
 assert.equal((result.match(/default_tools_approval_mode = 'writes'/g)||[]).length,2);
 assert.ok(result.includes('[mcp_servers.proton_mail]'));assert.ok(result.includes('[mcp_servers.records_desk]'));
 assert.ok(!result.includes('[mcp_servers.civicresultmaps]'));assert.ok(!result.includes('__ROOT__'));
 assert.ok(result.includes(`RECORDS_DESK_GH = '${process.execPath}'`));assert.ok(!result.includes('__GH__'));
 assert.throws(()=>buildMcpConfig(template,{ROOT:'relative',NODE:process.execPath,PYTHON:pythonExecutable()}),/absolute/);
 assert.throws(()=>buildMcpConfig(template,{ROOT:root+"'unsafe",NODE:process.execPath,PYTHON:pythonExecutable()}),/absolute/);
 assert.throws(()=>buildMcpConfig(template,{ROOT:root}),/Missing/);
});
