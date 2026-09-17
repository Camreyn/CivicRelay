import test from 'node:test';
import assert from 'node:assert/strict';
import {createSendControls, formatWait} from './static/send-controls.mjs';

class Element {
  constructor(tag, text, className) { Object.assign(this, {tag, textContent: text, className, children: [], disabled: false, hidden: false}); }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute() {}
}
const available = overrides => ({ready: true, retry_after_seconds: 0, attempts_remaining: 9,
  max_attempts: 10, reason: 'ready', ...overrides});
function fixture({policy = () => available(), sendResult = () => ({state: 'accepted'}), onResult = async () => {}, canStart = () => {}, unknownOutcome = '', onUnknownOutcome = () => {}, configured = true, sendingEnabled = true} = {}) {
  let time = 0, sequence = 0, active = true;
  const tasks = new Map(), calls = [], notices = [];
  const op = async (name, args) => {
    calls.push({name, args});
    if (name === 'desk_status') return {connector: {configured, sending_enabled: sendingEnabled, send_window: await policy()}};
    if (name === 'desk_send_email') return sendResult();
    throw Error('Unexpected synthetic operation');
  };
  const c = createSendControls({el: (tag, text, cls) => new Element(tag, text, cls), op,
    caseId: 'synthetic-case', draft: {state: 'draft', draft_id: 'synthetic-draft', digest: 'a'.repeat(64)},
    notice: (...n) => notices.push(n), onResult, onReconcile: async () => {}, isCurrent: () => active, canStart, unknownOutcome, onUnknownOutcome,
    now: () => time, schedule: (fn, delay) => {tasks.set(++sequence, {fn, due: time + delay}); return sequence;}, cancel: id => tasks.delete(id)});
  const byClass = cls => c.node.children.find(n => n.className === cls);
  const [send, recheck, reconcile] = byClass('actions').children;
  return {c, calls, notices, send, recheck, reconcile, byClass, tasks, deactivate: () => {active = false;},
    async tick(ms) {time += ms; for (const [id, task] of [...tasks]) if (task.due <= time) {tasks.delete(id); task.fn();} await new Promise(resolve => setImmediate(resolve));}};
}

test('countdown is visible, disables Send, and expiry only refreshes local eligibility', async () => {
  let checks = 0;
  const f = fixture({policy: () => ++checks === 1 ? available({ready: false, retry_after_seconds: 2, reason: 'cooldown'}) : available()});
  await f.c.ready;
  assert.equal(f.send.disabled, true); assert.match(f.send.textContent, /2s/);
  await f.send.onclick(); assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0);
  await f.tick(1000); assert.match(f.byClass('send-status').textContent, /1s remaining/);
  await f.tick(1000); assert.equal(f.send.disabled, false); assert.equal(checks, 2);
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0);
  assert.equal(f.tasks.size, 0); f.c.destroy();
});

test('click rechecks availability and never sends when another window used the slot', async () => {
  let checks = 0;
  const f = fixture({policy: () => ++checks === 1 ? available() : available({ready: false, retry_after_seconds: 60, reason: 'cooldown'})});
  await f.c.ready; await f.send.onclick();
  assert.equal(f.send.disabled, true); assert.match(f.byClass('send-status').textContent, /1m 0s/);
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0); f.c.destroy();
});

test('daily cap shows readable wait and zero remaining attempts without starting a send', async () => {
  const f = fixture({policy: () => available({ready: false, retry_after_seconds: 3661, attempts_remaining: 0, reason: 'daily_limit'})});
  await f.c.ready;
  assert.equal(f.send.disabled, true); assert.match(f.byClass('send-status').textContent, /Daily sending limit: 1h 1m 1s/);
  assert.match(f.byClass('help').textContent, /0 of 10/); f.c.destroy();
});

test('fresh eligible click submits only the exact immutable identity, once', async () => {
  let release;
  const pending = new Promise(resolve => {release = resolve;});
  const f = fixture({sendResult: () => pending});
  await f.c.ready; const send = f.send.onclick(); await new Promise(resolve => setImmediate(resolve));
  await f.send.onclick(); release({state: 'accepted'}); await send;
  const calls = f.calls.filter(x => x.name === 'desk_send_email');
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].args, {case_id: 'synthetic-case', draft_id: 'synthetic-draft', expected_digest: 'a'.repeat(64)});
  assert.equal(f.send.disabled, true); assert.match(f.byClass('send-status').textContent, /Accepted by Proton Bridge/);
  f.c.destroy();
});

test('a legacy no-attempt result leaves the draft available and never retries by itself', async () => {
  const f = fixture({sendResult: () => ({state: 'draft', messages_sent: 0})});
  await f.c.ready; await f.send.onclick();
  assert.equal(f.byClass('send-feedback').hidden, false);
  assert.match(f.byClass('send-feedback').textContent, /No send attempt was recorded/);
  assert.equal(f.byClass('send-error').hidden, true);
  assert.equal(f.send.disabled, false); assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1);
  f.c.destroy();
});

test('unknown transport outcome remains locked with inline error and receipt reload', async () => {
  const f = fixture({sendResult: () => {throw Error('Synthetic connection interrupted');}});
  await f.c.ready; await f.send.onclick();
  assert.equal(f.send.disabled, true); assert.equal(f.reconcile.hidden, false);
  assert.equal(f.byClass('send-error').hidden, false);
  assert.match(f.byClass('send-error').textContent, /Synthetic connection interrupted/);
  assert.match(f.byClass('send-status').textContent, /No automatic retry/);
  await f.recheck.onclick(); await f.send.onclick();
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1); f.c.destroy();
});

test('accepted send plus refresh failure retains outcome and blocks a repeat send', async () => {
  const f = fixture({onResult: async () => {throw Error('Synthetic render failure');}});
  await f.c.ready; await f.send.onclick();
  assert.match(f.byClass('send-status').textContent, /Accepted by Proton Bridge/);
  assert.match(f.byClass('send-error').textContent, /dashboard could not refresh/);
  assert.equal(f.send.disabled, true); assert.equal(f.reconcile.hidden, false);
  await f.send.onclick(); assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1); f.c.destroy();
});

test('uncertain and receipt-persistence states never become sendable again', async () => {
  for (const state of ['uncertain', 'failed_before_data', 'receipt_persistence_uncertain']) {
    const f = fixture({sendResult: () => ({state})});
    await f.c.ready; await f.send.onclick();
    assert.equal(f.send.disabled, true); assert.match(f.byClass('send-status').textContent, /Check the saved receipt/);
    await f.send.onclick(); assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1); f.c.destroy();
  }
});

test('status failure and incompatible older connector fail closed with nearby errors', async () => {
  for (const policy of [() => {throw Error('Synthetic status unavailable');}, () => undefined]) {
    const f = fixture({policy}); await f.c.ready;
    assert.equal(f.send.disabled, true); assert.equal(f.byClass('send-error').hidden, false);
    assert.match(f.byClass('send-status').textContent, /No send was started/);
    assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0); f.c.destroy();
  }
});

test('navigation during preflight or destroyed countdown cannot dispatch or keep polling', async () => {
  let checks = 0, release;
  const pending = new Promise(resolve => {release = resolve;});
  const f = fixture({policy: () => ++checks === 1 ? available() : pending});
  await f.c.ready; const sending = f.send.onclick(); f.deactivate(); release(available()); await sending;
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0); f.c.destroy();
  const g = fixture({policy: () => available({ready: false, retry_after_seconds: 60, reason: 'cooldown'})});
  await g.c.ready; assert.equal(g.tasks.size, 1); g.c.destroy(); await g.tick(60000);
  assert.equal(g.tasks.size, 0); assert.equal(g.calls.length, 1);
});

test('unsaved edits appearing during preflight prevent the send and remain untouched', async () => {
  let calls = 0;
  const f = fixture({canStart: () => {if (++calls === 2) throw Error('Unsaved workspace edits are present.');}});
  await f.c.ready; await f.send.onclick();
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0);
  assert.match(f.byClass('send-error').textContent, /Unsaved workspace edits/); f.c.destroy();
});

test('wait formatting is nonnegative and rounds up fractional seconds', () => {
  assert.equal(formatWait(-1), '0s'); assert.equal(formatWait(0.1), '1s'); assert.equal(formatWait(60), '1m 0s');
});

test('a replaced control still reconciles a returned accepted or uncertain result by case ID', async () => {
  for (const state of ['accepted', 'uncertain']) {
    let release, reconciled;
    const pending = new Promise(resolve => {release = resolve;});
    const f = fixture({sendResult: () => pending, onResult: async result => {reconciled = result.state;}});
    await f.c.ready; const sending = f.send.onclick(); await new Promise(resolve => setImmediate(resolve));
    f.c.destroy(); release({state}); await sending;
    assert.equal(reconciled, state); assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1);
  }
});

test('explicit preflight rejection shows no-send explanation without an uncertainty lock', async () => {
  const f = fixture({sendResult: () => {throw Object.assign(Error('Routing review is stale.'), {sendNotStarted: true});}});
  await f.c.ready; await f.send.onclick();
  assert.match(f.byClass('send-status').textContent, /No send was started/);
  assert.match(f.byClass('send-error').textContent, /Routing review is stale/);
  assert.equal(f.recheck.disabled, false); assert.equal(f.reconcile.hidden, true);
  assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 1);
  f.c.destroy();
});

test('unknown outcome after navigation is reported and retained for a replacement control', async () => {
  let reject, warning;
  const pending = new Promise((_, fail) => {reject = fail;});
  const f = fixture({sendResult: () => pending, onUnknownOutcome: value => {warning = value;}});
  await f.c.ready; const sending = f.send.onclick(); await new Promise(resolve => setImmediate(resolve));
  f.c.destroy(); reject(Error('Synthetic response lost')); await sending;
  assert.match(warning, /send outcome is unconfirmed/);
  assert.equal(f.notices.at(-1)[1], true);
  const g = fixture({unknownOutcome: warning}); await g.c.ready;
  assert.equal(g.send.disabled, true); assert.equal(g.reconcile.hidden, false);
  assert.equal(g.calls.length, 0, 'a recreated uncertain control cannot recheck or send');
  g.c.destroy();
});

test('unconfigured or disabled connectors fail closed without opening a send', async () => {
  for (const policy of [{configured: false}, {sendingEnabled: false}]) {
    const f = fixture(policy); await f.c.ready; await f.send.onclick();
    assert.equal(f.send.disabled, true); assert.equal(f.byClass('send-error').hidden, false);
    assert.equal(f.calls.filter(x => x.name === 'desk_send_email').length, 0); f.c.destroy();
  }
});

test('a late availability response cannot replace an unknown-outcome lock', async () => {
  let release;
  const pending = new Promise(resolve => {release = resolve;});
  const f = fixture({policy: () => pending});
  f.c.markUnknown('Synthetic response lost; inspect the saved receipt.');
  release(available()); await f.c.ready;
  assert.equal(f.send.disabled, true); assert.equal(f.recheck.disabled, true);
  assert.match(f.byClass('send-error').textContent, /Synthetic response lost/);
  assert.match(f.byClass('send-status').textContent, /No automatic retry/);
  assert.equal(f.reconcile.hidden, false); f.c.destroy();
});
