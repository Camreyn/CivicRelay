// Settings edits policy only. No mailbox connections, retries or send actions.
export function createSendingLimits({host, api}) {
  let busy = false, dirty = false, current = null, editRevision = null;
  const el = (tag, text) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  host.append(el('h3', 'CivicRelay sending limits'), el('p',
    'These are local safeguards, not your Proton allowance. Defaults: 10 send attempts per rolling 24 hours, at least 60 seconds apart. A send attempt counts once, even with several recipients; Proton may count each recipient separately.'));
  const provider = el('a', 'Proton sending limits and restrictions');
  provider.href = 'https://proton.me/support/email-sending-limits';
  provider.target = '_blank'; provider.rel = 'noopener noreferrer';
  host.append(provider, el('p',
    'Changing these numbers does not reset attempts, enable sending, retry uncertain messages or start a sending queue. Failed or uncertain attempts can count. Provider restrictions still apply; this is not a bulk-mailing tool.'));
  const usage = el('p'); usage.className = 'settings-note';
  const status = el('p'); status.className = 'settings-status';
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const fields = el('div'); fields.className = 'settings-import';
  function number(labelText, min, max) {
    const label = el('label', labelText), input = el('input');
    input.type = 'number'; input.min = String(min); input.max = String(max); input.step = '1'; input.required = true;
    input.addEventListener('input', () => {dirty = true; status.textContent = 'Unsaved limits. Save explicitly to apply them.';});
    label.append(input); fields.append(label); return input;
  }
  const maximum = number('Maximum send attempts per rolling 24 hours (1–1,000)', 1, 1000);
  const interval = number('Minimum seconds between attempts (1–3,600)', 1, 3600);
  const actions = el('div'); actions.className = 'settings-source-toolbar';
  const save = el('button', 'Save sending limits'), reload = el('button', 'Reload saved limits (discard edits)');
  save.type = reload.type = 'button';
  actions.append(save, reload); host.append(usage, fields, actions, status);
  function controls() {
    save.disabled = busy || !current?.configured || editRevision === null;
    maximum.disabled = interval.disabled = busy || !current?.configured;
    reload.disabled = busy;
  }
  function show(value, discard = false) {
    if (!Number.isSafeInteger(value?.revision) || value.revision < 0 ||
        !Number.isSafeInteger(value.max_attempts_per_24h) || value.max_attempts_per_24h < 1 || value.max_attempts_per_24h > 1000 ||
        !Number.isSafeInteger(value.minimum_interval_seconds) || value.minimum_interval_seconds < 1 || value.minimum_interval_seconds > 3600 ||
        typeof value.configured !== 'boolean' || !Number.isSafeInteger(value.send_window?.attempts_used)) {
      throw Error('Saved sending limits could not be verified. Reload the updated application.');
    }
    current = value;
    usage.textContent = `Saved: ${value.max_attempts_per_24h} attempts per rolling 24 hours, ${value.minimum_interval_seconds} seconds apart. Used: ${value.send_window.attempts_used}; remaining: ${value.send_window.attempts_remaining}. ${value.send_window.message}`;
    if (!dirty || discard) {
      maximum.value = String(value.max_attempts_per_24h); interval.value = String(value.minimum_interval_seconds);
      editRevision = value.revision; dirty = false;
    }
    status.textContent = !value.configured ? 'Enroll your mail connection in the local Proton setup window before changing limits.'
      : dirty ? 'Unsaved edits preserved. If settings changed elsewhere, reload and review before saving.'
      : value.revision === 0 ? 'Using the default limits. No custom policy has been saved.' : 'Saved limits loaded. Nothing was sent.';
  }
  async function run(fn) {
    if (busy) return;
    busy = true; controls();
    try { await fn(); }
    catch (error) { status.textContent = error.message || 'Could not verify the operation. Reload saved limits before trying again.'; }
    finally { busy = false; controls(); }
  }
  async function load(discard = false) {
    return run(async () => {
      try { show(await api('desk_get_send_limits', {}), discard); }
      catch (error) {current = null; throw error;}
    });
  }
  reload.onclick = () => {void load(true);};
  save.onclick = () => {void run(async () => {
    if (!maximum.checkValidity() || !interval.checkValidity()) throw Error('Enter whole numbers within the displayed ranges.');
    const max = Number(maximum.value), seconds = Number(interval.value);
    if (!Number.isSafeInteger(max) || max < 1 || max > 1000 || !Number.isSafeInteger(seconds) || seconds < 1 || seconds > 3600) throw Error('Enter whole numbers within the displayed ranges.');
    show(await api('desk_save_send_limits', {revision:editRevision, max_attempts_per_24h:max, minimum_interval_seconds:seconds}), true);
    status.textContent = 'Sending limits saved. Existing attempt history is unchanged. Nothing was sent. Close Settings and use Check sending availability on an open draft to refresh its display.';
  });};
  controls();
  return {load};
}
