// Standalone runtime: reviewed public snapshot only. Modified 2026-09-10.
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export function validateCatalog(value) {
  if (!value || !Array.isArray(value.states) || !Array.isArray(value.cases) || !value.issue)
    throw Error('Public catalog shape is invalid.');
  const {sha256, ...payload} = value;
  if (crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex') !== sha256)
    throw Error('Public catalog hash mismatch. Review and refresh the snapshot.');
  if (value.states.length !== 51 || new Set(value.states.map(s => s.code)).size !== 51 ||
      new Set(value.cases.map(c => c.id)).size !== value.cases.length ||
      value.issue.repository !== 'Camreyn/civicresultmaps' || value.issue.template !== 'records-response.yml')
    throw Error('Public catalog identities or intake destination changed.');
  for (const c of value.cases)
    if (!c.body.includes('[requester name]') || !c.body.includes('[requester email]'))
      throw Error('Public templates must not contain personalized correspondence.');
  return value;
}
export function loadCatalog() {
  const bytes = fs.readFileSync(new URL('../data/catalog.json', import.meta.url));
  if (bytes.length > 2_000_000) throw Error('Public catalog exceeds size limit.');
  const value = validateCatalog(JSON.parse(bytes));
  const form = fs.readFileSync(new URL('../data/records-response.yml', import.meta.url));
  if (crypto.createHash('sha256').update(form).digest('hex') !== value.issue.template_sha256)
    throw Error('Public intake form differs from reviewed catalog.');
  return value;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  process.stdout.write(JSON.stringify(loadCatalog()));
