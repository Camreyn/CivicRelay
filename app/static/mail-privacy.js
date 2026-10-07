// Local, explicit privacy setup. No automatic mailbox connection or cleanup.
export function createMailPrivacy({host, api, onChanged = async () => {}}) {
  const el = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
  const button = (label, fn) => { const n = el('button', label); n.type = 'button'; n.onclick = () => void run(fn); return n; };
  let busy = false, preview = null, cleanup = null, dirty = false;
  const title = el('h3', 'Choose what CivicRelay may read');
  const current = el('p', 'Load saved mail scope to begin.'), result = el('p');
  result.setAttribute('role', 'status'); result.setAttribute('aria-live', 'polite');
  const explanation = el('p', 'Personal account? Use dedicated CivicRelay folders or labels. CivicRelay never scans your whole inbox to guess which mail is relevant. Create the folders in Proton first, then move/label selected replies there or configure your own Proton filters. No mail is moved automatically.');
  const form = el('div'); form.className = 'settings-import mail-privacy-form';
  const modeLabel = el('label', 'Mailbox access mode'), mode = el('select');
  for (const [value, text] of [['folders', 'Existing account: selected custom folders only'], ['dedicated', 'Dedicated account/address: Inbox and Sent']]) {const o = el('option', text); o.value = value; mode.append(o);}
  modeLabel.append(mode);
  const incomingLabel = el('label', 'Incoming Bridge folder path'), incoming = el('input'); incoming.value = 'Folders/CivicRelay'; incoming.maxLength = 160; incomingLabel.append(incoming);
  const sentLabel = el('label', 'Sent Bridge folder path (optional)'), sent = el('input'); sent.maxLength = 160; sent.placeholder = 'Labels/CivicRelay Sent'; sentLabel.append(sent);
  const historyLabel = el('label'), history = el('input'); historyLabel.className = 'mail-history-choice'; history.type = 'checkbox'; historyLabel.append(history, document.createTextNode(' Import existing messages in the selected folders (off by default)'));
  const warning = el('p', 'Default: start from the preview point, not from the oldest email. Leaving Sent blank disables remote Sent inspection; sending and saved receipts still work. Dedicated mode exposes every new message in Inbox and Sent—do not use it for a personal inbox.');
  const scopePreview = el('div'); scopePreview.className = 'settings-source'; scopePreview.hidden = true;
  const applyScope = button('Apply reviewed mail scope', async () => {
    if (!preview) return;
    const response = await api('desk_apply_mail_scope', {preview_id: preview.preview_id, expected_digest: preview.digest});
    preview = null; scopePreview.replaceChildren(); scopePreview.hidden = true; dirty = false;
    showCurrent(response); result.textContent = 'Mail scope saved. No messages were imported or deleted. Use Check mail when ready.';
    await changed();
  });
  const previewScope = button('Preview mail scope', async () => {
    preview = null; scopePreview.hidden = true;
    const args = {mode: mode.value, import_history: history.checked};
    if (mode.value === 'folders') Object.assign(args, {incoming_folder: incoming.value, sent_folder: sent.value});
    const response = await api('desk_preview_mail_scope', args);
    preview = response; scopePreview.replaceChildren(el('h4', 'Review before activating'));
    scopePreview.append(el('p', response.warning));
    for (const [role, folder] of Object.entries(response.scope.folders)) {
      scopePreview.append(el('p', `${role}: ${folder.remote_folder}. Existing messages: ${folder.existing_messages_at_preview ?? 'count unavailable'}. ${response.scope.import_history ? 'Existing history WILL be included.' : 'Existing history will be skipped; only arrivals after this preview will be imported.'}`));
    }
    scopePreview.append(el('p', 'Preview expires in ten minutes. No headers or bodies were read.'), applyScope); scopePreview.hidden = false;
    result.textContent = 'Preview ready. Inspect its folder scope and history choice before applying.';
  });
  const cleanupBox = el('div'); cleanupBox.className = 'settings-source'; cleanupBox.hidden = true;
  const applyCleanup = button('Remove listed local imports', async () => {
    if (!cleanup?.count) return;
    const response = await api('desk_apply_mail_cleanup', {preview_id: cleanup.preview_id, expected_digest: cleanup.digest});
    cleanup = null; cleanupBox.replaceChildren(); cleanupBox.hidden = true;
    result.textContent = `Removed ${response.removed_local_messages} local imports. No Proton messages, drafts or receipts were deleted.`;
    await loadCurrent(); await changed();
  });
  const previewCleanup = button('Preview cleanup of hidden imports', async () => {
    cleanup = null; cleanupBox.hidden = true;
    cleanup = await api('desk_preview_mail_cleanup', {});
    cleanupBox.replaceChildren(el('h4', `${cleanup.count} local imports proposed for removal`), el('p', cleanup.warning));
    const list = el('ul');
    for (const candidate of cleanup.candidates) list.append(el('li', `${candidate.from || '(no sender)'} — ${candidate.subject || '(no subject)'} — ${candidate.date || ''}${candidate.body_loaded ? ' (cached body included)' : ' (header only)'}`));
    cleanupBox.append(list, el('p', `${cleanup.protected_count} messages protected by evidence/history. ${cleanup.remaining_hidden_candidates} additional candidates require another preview.`));
    if (cleanup.count) cleanupBox.append(applyCleanup);
    cleanupBox.hidden = false; result.textContent = 'Cleanup preview ready. Nothing has been deleted.';
  });
  const reload = button('Reload saved mail privacy', loadCurrent);
  form.append(modeLabel, incomingLabel, sentLabel, historyLabel, warning, previewScope);
  host.append(title, current, explanation, reload, form, scopePreview, el('h3', 'Recover from an accidental import'), el('p', 'Changing scope hides unrelated old imports without deleting them. Case-linked evidence remains available. Review this local-only cleanup separately. It cannot erase previous assistant transcripts, exports or backups.'), previewCleanup, cleanupBox, result);
  function inputsChanged() {
    dirty = true; preview = null; scopePreview.replaceChildren(); scopePreview.hidden = true;
    incomingLabel.hidden = sentLabel.hidden = mode.value !== 'folders'; controls();
  }
  for (const input of [mode, incoming, sent, history]) input.addEventListener('input', inputsChanged);
  function controls() {for (const n of host.querySelectorAll('button,input,select')) n.disabled = busy; host.setAttribute('aria-busy', String(busy));}
  function showCurrent(response) {
    const scope = response.scope;
    current.textContent = scope.configured ? `Active: ${scope.mode === 'folders' ? 'Selected folders only' : 'Dedicated mailbox'}. ${Object.entries(scope.folders).map(([role, x]) => `${role}: ${x.remote_folder}`).join('; ')}. ${response.hidden_imports} old imports hidden.` : `Mail reading is paused until a scope is selected. ${response.hidden_imports} old imports hidden; saved case evidence is retained.`;
    if (!dirty && scope.configured) {mode.value = scope.mode; incoming.value = scope.folders.INBOX.remote_folder; sent.value = scope.mode === 'folders' ? scope.folders.Sent?.remote_folder || '' : ''; history.checked = false;}
    incomingLabel.hidden = sentLabel.hidden = mode.value !== 'folders';
  }
  async function loadCurrent() {showCurrent(await api('desk_get_mail_scope', {}));}
  async function changed() {try {await onChanged();} catch {result.textContent += ' Saved successfully, but the dashboard did not reload. Reload its saved view; do not repeat the action.';}}
  async function run(fn) {
    if (busy) return;
    busy = true; controls();
    try {await fn();} catch (error) {result.textContent = error?.message || 'Operation could not be confirmed. Reload saved mail privacy before retrying.';}
    finally {busy = false; controls();}
  }
  return {load: () => run(loadCurrent)};
}
