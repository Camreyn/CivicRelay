// Public schemas only. Imports do not start workers, read mail, or register live servers.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {TOOLS as desk} from '../app/static/tool-contracts.mjs';
import {TOOLS as proton} from '../connector/server.mjs';
export function renderToolReference() {
  const lines=['# Native tool reference','','Generated from the checked-in schemas. Regenerate with `npm.cmd run docs:generate`;',
    '`npm.cmd run test:docs` detects drift. No private account data is used.','',
    'Use the [operator guide](OPERATOR-TOOLS.md) for order, authorization, thread safety,',
    'pagination and handling uncertain outcomes. The schema lists allowed arguments,',
    'not permission to perform the action. Never automate desktop confirmations.','',
    'Each native response includes text and structured content. Inspect `ok` and',
    '`isError`; a lost response is not evidence that a side effect failed. Python',
    'independently validates operations. No tool can set credentials, sending policy,',
    'a server URL, an executable path or a production-data import target.',''];
  for(const [title,tools,source] of [['Records workflow (20 tools)',desk,'../app/static/tool-contracts.mjs'],['Proton connector (8 tools)',proton,'../connector/server.mjs']]) {
    lines.push('## '+title,'','Schema source: [implementation]('+source+').','');
    for(const tool of tools) {
      const read=tool.readOnly??tool.annotations?.readOnlyHint;
      lines.push('### `'+tool.name+'`','',tool.description,'','Operation annotation: '+(read?'read-only':'may write; follow the specific review/confirmation rules')+'.','',
        '```json',JSON.stringify(tool.schema,null,2),'```','');
    }
  }
  return lines.join('\n');
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  fs.writeFileSync(new URL('../docs/TOOL-REFERENCE.md',import.meta.url),renderToolReference());
  console.log('Generated docs/TOOL-REFERENCE.md from 28 public schemas. No workers or mail operations ran.');
}
