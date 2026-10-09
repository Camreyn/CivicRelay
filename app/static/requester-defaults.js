// Private template defaults, never sender credentials or automatic signature text.
export const requesterFields = [
  ['requester_name', 'Requester name', 'text', 300, 'rname'],
  ['requester_address', 'Postal address', 'textarea', 1500, 'raddress'],
  ['requester_phone', 'Phone number', 'tel', 80, 'rphone'],
  ['requester_email', 'Contact email', 'email', 254, 'remail'],
  ['organization', 'Organization', 'text', 300, 'org'],
  ['requester_title', 'Title / role', 'text', 300, 'rtitle'],
  ['signature', 'Signature', 'textarea', 4000, 'sign'],
];
const el = (tag, text) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
};

export function identityForm({host, workspace, account = {}, prefix = 'defaults', onEdit = () => {}}) {
  const controls = new Map();
  for (const [key, labelText, type, limit, suffix] of requesterFields) {
    const row = el('fieldset'); row.className = 'requester-default-field';
    row.append(el('legend', labelText));
    const label = el('label', `${labelText} value`), input = el(type === 'textarea' ? 'textarea' : 'input');
    input.id = `${prefix}-${suffix}`;
    if (type !== 'textarea') input.type = type;
    else input.rows = key === 'signature' ? 4 : 3;
    input.maxLength = limit; input.value = workspace[key] || '';
    if (key === 'requester_email') input.placeholder = account.email || 'Optional contact address';
    label.append(input);
    const toggle = el('label', `Use ${labelText.toLowerCase()} by default`), enabled = el('input');
    toggle.className = 'requester-default-toggle'; enabled.type = 'checkbox';
    enabled.checked = workspace.identity_enabled?.[key] ?? ['organization', 'signature', 'requester_email'].includes(key);
    toggle.append(enabled);
    const hint = el('p', `Template variable: {{${key}}}`); hint.className = 'settings-note';
    row.append(label, toggle, hint); host.append(row); controls.set(key, {input, enabled});
    input.addEventListener('input', onEdit); enabled.addEventListener('change', onEdit);
  }
  return {
    read() {
      const result = {identity_enabled: {}};
      for (const [key, {input, enabled}] of controls) {
        if (!input.checkValidity()) throw Error('Check the contact email and the displayed field lengths.');
        result[key] = input.value; result.identity_enabled[key] = enabled.checked;
      }
      return result;
    },
    disable(value) {for (const {input, enabled} of controls.values()) input.disabled = enabled.disabled = value;},
  };
}

export function createRequesterDefaults({host, api, onChanged = async () => {}}) {
  let busy = false, dirty = false, editRevision = null, form = null;
  host.append(el('h3', 'Requester defaults'), el('p',
    'Save your own identity once and reference it in reusable templates. Each switch controls only that field’s saved default. Disabled values stay private and stored; they are not inserted automatically.'));
  host.append(el('p',
    'Nothing is appended unless the template references its variable. Explicit per-request values override defaults, including blank values. Contact email does not change the sending account; when enabled and blank it uses the enrolled sender email. Existing cases and prepared drafts never change.'));
  const fields = el('div'); fields.className = 'requester-defaults-grid';
  const actions = el('div'); actions.className = 'settings-source-toolbar';
  const save = el('button', 'Save requester defaults'), reload = el('button', 'Reload saved defaults (discard edits)');
  save.type = reload.type = 'button'; actions.append(save, reload);
  const status = el('p'); status.className = 'settings-status';
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  host.append(fields, actions, status);
  function controls() {save.disabled = busy || !form; reload.disabled = busy; form?.disable(busy);}
  function show(result, discard = false) {
    const workspace = result.workspace;
    if (!Number.isSafeInteger(workspace?.revision) || !workspace.identity_enabled) throw Error('Requester defaults could not be verified. Reload the updated application.');
    if (!dirty || discard) {
      fields.replaceChildren(); editRevision = workspace.revision; dirty = false;
      form = identityForm({host: fields, workspace, account: result.account, onEdit: () => {
        dirty = true; status.textContent = 'Unsaved defaults. Save explicitly to apply them to future requests.';
      }});
    }
    status.textContent = dirty ? 'Unsaved edits preserved. Reload if this workspace changed elsewhere.' : 'Saved requester defaults loaded. Nothing was sent.';
  }
  async function run(fn) {
    if (busy) return;
    busy = true; controls();
    try {await fn();} catch (error) {status.textContent = error.message || 'Could not confirm the save. Reload before retrying.';}
    finally {busy = false; controls();}
  }
  async function load(discard = false) {return run(async () => {show(await api('desk_get_workspace', {}), discard);});}
  reload.onclick = () => {void load(true);};
  save.onclick = () => {
    if (busy || !form) return;
    let values;
    try {values = form.read();} catch (error) {status.textContent = error.message; return;}
    void run(async () => {
    const result = await api('desk_save_workspace', {revision: editRevision, ...values});
    show(result, true);
    const saved = 'Requester defaults saved privately. Existing cases, drafts and sender identity are unchanged.';
    status.textContent = 'Defaults saved. Refreshing inherited values…';
    try {await onChanged(); status.textContent = saved;}
    catch {status.textContent = saved + ' The dashboard could not refresh; do not repeat the save. Reload saved defaults.';}
    });
  };
  controls(); return {load};
}
