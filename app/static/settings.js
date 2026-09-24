// Local settings read saved metadata; only an explicit refresh fetches a reviewed public source.
export function createSettings({host, api, onSourcesChanged = async () => {}}) {
  let inventory = [], loading = false, refreshing = false, readingFile = false, pendingResult = null;
  let opener = null, selectedTab = 'sources', loadVersion = 0;
  const imports = new Map();
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const text = (value, max = 1500) => typeof value === 'string' ? value.slice(0, max) : '';
  const when = value => {
    if (!value) return 'Not yet';
    const date = new Date(typeof value === 'number' ? value * 1000 : value);
    return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString();
  };
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString() : 'Unknown';
  const button = (label, fn, className) => {
    const node = el('button', label, className);
    node.type = 'button';
    node.addEventListener('click', fn);
    return node;
  };
  function sourceLink(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password) throw Error();
      const a = el('a', url.href);
      a.href = url.href;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      return a;
    } catch {
      return el('span', 'Source URL unavailable or unsafe; no link opened.');
    }
  }

  const dialog = el('dialog', undefined, 'settings-dialog');
  dialog.id = 'civic-settings';
  dialog.setAttribute('aria-labelledby', 'settings-title');
  const head = el('div', undefined, 'settings-heading');
  const title = el('h2', 'Settings');
  title.id = 'settings-title';
  const closeButton = button('Close settings', close);
  closeButton.className = 'settings-close';
  head.append(title, closeButton);
  const intro = el('p', 'Manage public-source refreshes and see how this local workspace behaves.', 'settings-intro');
  const tabs = el('div', undefined, 'settings-tabs');
  tabs.setAttribute('role', 'tablist');
  tabs.setAttribute('aria-label', 'Settings sections');
  const panels = new Map(), tabButtons = new Map();
  for (const [id, label] of [['sources', 'Sources'], ['guides', 'State guides'], ['privacy', 'Privacy & accounts']]) {
    const tab = button(label, () => selectTab(id));
    tab.id = `settings-tab-${id}`;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', `settings-panel-${id}`);
    tab.addEventListener('keydown', event => {
      const ids = [...tabButtons.keys()], position = ids.indexOf(id);
      const target = event.key === 'ArrowRight' ? ids[(position + 1) % ids.length]
        : event.key === 'ArrowLeft' ? ids[(position + ids.length - 1) % ids.length]
        : event.key === 'Home' ? ids[0] : event.key === 'End' ? ids.at(-1) : null;
      if (target) {
        event.preventDefault();
        selectTab(target);
        tabButtons.get(target).focus();
      }
    });
    const panel = el('section', undefined, 'settings-panel');
    panel.id = `settings-panel-${id}`;
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', tab.id);
    panel.tabIndex = 0;
    tabs.append(tab);
    panels.set(id, panel);
    tabButtons.set(id, tab);
  }
  function selectTab(id) {
    selectedTab = id;
    for (const [key, tab] of tabButtons) {
      const selected = key === id;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panels.get(key).hidden = !selected;
    }
  }

  const sourcePanel = panels.get('sources');
  sourcePanel.append(el('h3', 'Official public sources'), el('p', 'Refresh source re-collects the selected, supported public directory. It does not check email, send requests, accept fees, or change case routing. Sources are fixed and reviewed; arbitrary URLs cannot be added here.'));
  const toolbar = el('div', undefined, 'settings-source-toolbar');
  const reloadButton = button('Reload saved status', () => { void loadInventory(); });
  const status = el('p', '', 'settings-status');
  status.id = 'settings-source-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  toolbar.append(reloadButton, status);
  const rows = el('div', undefined, 'settings-source-list');
  rows.id = 'settings-source-list';
  sourcePanel.append(toolbar, rows, el('p', 'A successful collection verifies what the source publishes, not that every contact is a designated records custodian. Verify the filing role before routing a request. If a refresh fails, the last successful collection is retained.', 'settings-note'));

  const guides = panels.get('guides');
  guides.append(el('h3', 'Guides appear with the selected state'), el('p', 'When a guide is available, CivicRelay automatically places it beside the selected state. It starts collapsed; open its heading to read the guidance and source links.'), el('p', 'A guide is reference material, not an automatically sent request. Selecting a state or opening a guide does not refresh a website, check the mailbox, change case routing, or authorize any action.'), el('p', 'Guides exist only for supported states. Source dates and limitations remain visible inside the guide. A source-directory refresh updates collected contacts, not the bundled legal guidance or deadline rules.', 'settings-note'));
  const privacy = panels.get('privacy');
  privacy.append(el('h3', 'Local workspace, separate permissions'), el('p', 'Private cases, correspondence and collected contacts stay in the existing local workspace. Refresh diagnostics describe the public-source operation; do not paste credentials or private correspondence into source notes.'), el('p', 'This settings panel does not edit Proton credentials, sending limits, TLS trust, assistant-host permissions, publication destinations, or account identity.'), el('p', 'Use the local Proton setup window for account enrollment and trusted connection settings. Existing workspace and template controls remain in the dashboard. Opening Settings never starts automatic source refresh, mailbox polling or sending.', 'settings-note'));
  dialog.append(head, intro, tabs, ...panels.values());

  const resultDialog = el('dialog', undefined, 'settings-result-dialog');
  resultDialog.id = 'settings-refresh-result';
  resultDialog.setAttribute('aria-labelledby', 'settings-result-title');
  resultDialog.setAttribute('aria-describedby', 'settings-result-message');
  const resultTitle = el('h2');
  resultTitle.id = 'settings-result-title';
  const resultMessage = el('p');
  resultMessage.id = 'settings-result-message';
  const resultMeta = el('p', '', 'settings-note');
  const debug = el('details', undefined, 'settings-debug');
  debug.append(el('summary', 'Technical details'));
  const debugBody = el('pre');
  debug.append(debugBody);
  const doneButton = button('Done', () => resultDialog.close());
  resultDialog.append(resultTitle, resultMessage, resultMeta, debug, doneButton);
  host.append(dialog, resultDialog);
  dialog.addEventListener('close', () => {
    if (!resultDialog.open && opener?.isConnected) opener.focus();
  });
  resultDialog.addEventListener('close', () => {
    if (dialog.open) closeButton.focus();
    else if (opener?.isConnected) opener.focus();
  });
  selectTab(selectedTab);

  function busyControls() {
    reloadButton.disabled = loading || refreshing || readingFile;
    for (const node of rows.querySelectorAll('button,input,textarea')) node.disabled = loading || refreshing || readingFile;
    rows.setAttribute('aria-busy', String(loading || refreshing || readingFile));
  }
  function renderSources() {
    rows.replaceChildren();
    for (const source of inventory) {
      const card = el('article', undefined, 'settings-source');
      card.dataset.sourceId = source.id;
      const heading = el('div', undefined, 'settings-source-heading');
      heading.append(el('h4', text(source.label) || 'Public source'), el('span', text(source.state, 20), 'settings-source-state'));
      card.append(heading, el('p', text(source.description)), sourceLink(source.url));
      const dates = el('dl', undefined, 'settings-source-facts');
      for (const [key, value] of [['Last collection attempt', when(source.last_attempt_at)], ['Last successful collection', when(source.last_success_at)], ['Saved records', count(source.record_count)]]) {
        dates.append(el('dt', key), el('dd', value));
      }
      if (source.checked_on) dates.append(el('dt', 'Official source checked on'), el('dd', text(source.checked_on, 10)));
      if (Number.isSafeInteger(source.expected_count)) dates.append(el('dt', 'Directory coverage'), el('dd', `${count(source.record_count)} of ${count(source.expected_count)} expected entries`));
      if (source.collection_mode) dates.append(el('dt', 'Collection method'), el('dd', source.collection_mode === 'reviewed_text_import' ? 'Reviewed directory text import' : source.collection_mode === 'direct_fetch' ? 'Direct website fetch' : text(source.collection_mode, 80)));
      card.append(dates);
      if (source.stale === true) card.append(el('p', 'Collection needs a recheck. Saved contacts have not been automatically refreshed.', 'settings-last-error'));
      const result = source.last_result;
      if (result) {
        const message = el('p', `${result.ok === true ? 'Last result' : 'Last error'}: ${text(result.message) || text(result.code) || 'No detail supplied.'}`, result.ok === true ? 'settings-last-success' : 'settings-last-error');
        card.append(message);
        if (Array.isArray(result.debug) && result.debug.length) {
          const previous = el('details', undefined, 'settings-debug');
          previous.append(el('summary', 'Last result details'), el('pre', result.debug.slice(0, 12).map(value => text(value, 500)).filter(Boolean).join('\n')));
          card.append(previous);
        }
      }
      const refresh = button('Refresh source', () => { void refreshSource(source); });
      refresh.setAttribute('aria-label', `Refresh source: ${text(source.label) || source.id}`);
      card.append(refresh);
      const pasted = imports.get(source.id) || {text: '', checked_on: '', open: false};
      imports.set(source.id, pasted);
      const manual = el('details', undefined, 'settings-import');
      manual.open = pasted.open;
      manual.append(el('summary', 'Import reviewed directory text'), el('p', 'Use this fallback if the official website blocks a direct fetch. Collect the full directory from the exact official source linked above, verify its date, then paste its plain text or choose a local .txt file. Only the supported directory format is accepted; HTML is not executed. Preserve the ## Municipality headings and Email: / Phone: labels. The Massachusetts directory must include all 351 cities and towns. Published elections contacts do not become designated records custodians.'));
      manual.addEventListener('toggle', () => { pasted.open = manual.open; });
      const dayLabel = el('label', 'Date the official source was checked (UTC)'), day = el('input');
      day.type = 'date';
      day.value = pasted.checked_on;
      day.required = true;
      day.max = new Date().toISOString().slice(0, 10);
      day.addEventListener('input', () => { pasted.checked_on = day.value; });
      dayLabel.append(day);
      const contentLabel = el('label', 'Complete reviewed directory text'), content = el('textarea');
      content.value = pasted.text;
      content.maxLength = 200000;
      content.rows = 7;
      content.required = true;
      content.spellcheck = false;
      content.addEventListener('input', () => { pasted.text = content.value; });
      contentLabel.append(content);
      const fileLabel = el('label', 'Choose local .txt file (optional)'), fileInput = el('input');
      fileInput.type = 'file';
      fileInput.accept = '.txt,text/plain';
      fileLabel.append(fileInput);
      const fileStatus = el('p', pasted.file_message || '', 'settings-note');
      fileStatus.setAttribute('role', 'status');
      fileStatus.setAttribute('aria-live', 'polite');
      fileInput.addEventListener('change', async () => {
        const file = fileInput.files?.[0];
        if (!file || loading || refreshing || readingFile) return;
        readingFile = true;
        busyControls();
        try {
          if (!file.name.toLowerCase().endsWith('.txt') || (file.type && file.type !== 'text/plain')) throw Error('Choose a plain-text .txt file, not HTML or another format. Existing text is unchanged.');
          if (!file.size || file.size > 200000) throw Error('The .txt file must contain 1–200,000 bytes. Existing text is unchanged.');
          fileStatus.textContent = 'Reading the local text file in this browser… Nothing is being imported yet.';
          const value = await file.text();
          if (!value.trim() || value.length > 200000) throw Error('The file must contain nonempty text of at most 200,000 characters. Existing text is unchanged.');
          pasted.text = value;
          content.value = value;
          pasted.file_message = `Loaded ${text(file.name, 160)} into the unsaved text field. Review the source-check date and text, then choose Import reviewed text. No file path is sent to the server.`;
        } catch (error) {
          pasted.file_message = text(error?.message) || 'The local text file could not be read. Existing text is unchanged.';
        } finally {
          fileStatus.textContent = pasted.file_message;
          fileInput.value = '';
          readingFile = false;
          busyControls();
        }
      });
      const form = el('form');
      const save = el('button', 'Import reviewed text');
      save.type = 'submit';
      const clear = button('Clear pasted text', () => { pasted.text = ''; content.value = ''; pasted.file_message = ''; fileStatus.textContent = ''; });
      form.append(dayLabel, fileLabel, el('p', 'Optional UTF-8 plain-text .txt file, at most 200,000 bytes and 200,000 characters. Selecting it only fills the text field; nothing is saved until you import.', 'settings-note'), fileStatus, contentLabel, save, clear);
      form.addEventListener('submit', event => {
        event.preventDefault();
        if (readingFile || !form.reportValidity() || !content.value.trim()) return;
        void sourceOperation(source, 'desk_import_source', {source_id: source.id, checked_on: day.value, text: content.value}, 'Importing reviewed text from');
      });
      manual.append(form, el('p', 'Pasted text is kept while this page remains open, including after a failed import. It is cleared after success. Reloading the page discards text that has not been imported.', 'settings-note'));
      card.append(manual);
      rows.append(card);
    }
    if (!inventory.length && !loading) rows.append(el('p', 'No supported refreshable sources are configured. Existing guides and saved case evidence are unaffected.', 'settings-note'));
    busyControls();
  }
  async function loadInventory() {
    if (loading || refreshing || readingFile) return;
    const version = ++loadVersion;
    loading = true;
    status.textContent = 'Loading saved source status…';
    busyControls();
    try {
      const data = await api('desk_get_sources', {});
      if (!data || !Array.isArray(data.sources)) throw Error('The saved source inventory was not returned.');
      if (version !== loadVersion) return;
      inventory = data.sources;
      renderSources();
      status.textContent = `${inventory.length} supported source${inventory.length === 1 ? '' : 's'}. Opening this menu does not refresh the websites.`;
    } catch (error) {
      status.textContent = `Could not load saved source status. ${text(error?.message) || 'Please try again.'} Any previously displayed collection is unchanged.`;
    } finally {
      if (version === loadVersion) {
        loading = false;
        busyControls();
      }
    }
  }
  function showResult(result) {
    if (!dialog.open) {
      pendingResult = result;
      return;
    }
    pendingResult = null;
    const ok = result.ok === true;
    resultDialog.dataset.outcome = ok ? 'success' : 'error';
    resultTitle.textContent = ok ? (result.collection_mode === 'reviewed_text_import' ? 'Reviewed source text imported' : 'Source refreshed') : 'Source could not be refreshed';
    resultMessage.textContent = text(result.message) || (ok ? 'Public source collection completed.' : 'The last successful collection was kept.');
    resultMeta.textContent = `Result: ${text(result.code, 80) || 'not supplied'} · Attempted: ${when(result.attempted_at)} · Saved records: ${count(result.record_count)}`;
    const lines = Array.isArray(result.debug) ? result.debug.slice(0, 12).map(value => text(value, 500)).filter(Boolean) : [];
    debug.hidden = lines.length === 0;
    debug.open = false;
    debugBody.textContent = lines.join('\n');
    if (!resultDialog.open) resultDialog.showModal();
    doneButton.focus();
  }
  async function refreshSource(source) {
    return sourceOperation(source, 'desk_refresh_source', {source_id: source.id}, 'Refreshing');
  }
  async function sourceOperation(source, tool, args, action) {
    if (loading || refreshing || readingFile) return;
    refreshing = true;
    status.textContent = `${action} ${text(source.label) || 'public source'}… Closing Settings does not cancel this operation.`;
    busyControls();
    let result;
    try {
      result = await api(tool, args);
      if (!result || typeof result.ok !== 'boolean') throw Error('The source refresh did not return a completion result.');
      // If reloading the inventory fails, retain the receipt beside the prior saved collection.
      inventory = inventory.map(item => item.id === source.id ? {...item,
        last_attempt_at: result.attempted_at || item.last_attempt_at,
        last_success_at: result.last_success_at || item.last_success_at,
        record_count: Number.isSafeInteger(result.record_count) ? result.record_count : item.record_count,
        collection_mode: result.collection_mode || item.collection_mode,
        checked_on: result.checked_on || item.checked_on,
        last_result: result,
      } : item);
      try {
        const saved = await api('desk_get_sources', {});
        if (!saved || !Array.isArray(saved.sources)) throw Error('Saved inventory unavailable.');
        inventory = saved.sources;
      } catch {
        result = {...result, debug: [...(Array.isArray(result.debug) ? result.debug : []), 'The inventory view could not reload. The refresh receipt above is retained; use Reload saved status.']};
      }
      if (result.ok) {
        if (tool === 'desk_import_source') imports.set(source.id, {...imports.get(source.id), text: '', file_message: ''});
        try { await onSourcesChanged(result); }
        catch { result = {...result, debug: [...(Array.isArray(result.debug) ? result.debug : []), 'Collection succeeded, but another dashboard view could not refresh. Reopen that view to load the saved data.']}; }
      }
      status.textContent = result.ok ? 'Refresh completed. No request was sent or rerouted.' : 'Refresh did not complete. The last successful collection is retained.';
    } catch (error) {
      result = {ok: false, code: 'refresh_outcome_unconfirmed', message: 'A completion result could not be confirmed. Reload saved status before deciding whether to retry.', debug: [text(error?.message) || 'The source operation could not be reached.'], record_count: source.record_count};
      status.textContent = 'Refresh outcome unconfirmed. There is no automatic retry; reload saved status first.';
    } finally {
      refreshing = false;
      renderSources();
    }
    showResult(result);
  }
  function open() {
    if (dialog.open) return;
    opener = document.activeElement;
    dialog.showModal();
    tabButtons.get(selectedTab).focus();
    if (pendingResult) showResult(pendingResult);
    void loadInventory();
  }
  function close() {
    if (resultDialog.open) resultDialog.close();
    if (dialog.open) dialog.close();
  }
  return {open, close};
}
