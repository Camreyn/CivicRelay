// Dashboard-only updater; no MCP/page action, automatic download, or app shutdown.
export function createUpdates({host, request = updateRequest, onAvailable = () => {}}) {
  let saved = null, busy = false, dirty = false, started = false, timer;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (label, run) => {
    const node = el('button', label);
    node.type = 'button';
    node.addEventListener('click', () => { void run(); });
    return node;
  };
  const info = el('p'), status = el('p', '', 'settings-status');
  status.id = 'settings-update-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const form = el('form'), label = el('label', 'Automatically check for updates while this dashboard is open (at most once per day)', 'settings-update-preference');
  const automatic = el('input');
  automatic.type = 'checkbox';
  automatic.addEventListener('change', () => { dirty = true; });
  label.prepend(automatic);
  const save = el('button', 'Save update preference');
  save.type = 'submit';
  form.append(label, save);
  form.addEventListener('submit', event => {
    event.preventDefault();
    void action('preferences', {automatic_checks: automatic.checked}, 'Saving update preference…', () => { dirty = false; });
  });
  const reload = button('Reload update status', () => load());
  const check = button('Check for updates', () => action('check', {automatic: false}, 'Checking the official CivicRelay release…'));
  const approve = button('Approve and download update', () => {
    if (!saved?.update_available || !saved.latest?.package || busy) return;
    void action('approve', {version: saved.latest.version, sha256: saved.latest.package.sha256}, 'Downloading and verifying the approved package… No installation files are being replaced.');
  });
  const cancel = button('Cancel ready update plan', () => action('cancel', {}, 'Cancelling the not-yet-installed plan… The archive and receipt will be retained.'));
  const release = el('div'), guide = el('div'), unsaved = el('p', '', 'settings-note');
  const toolbar = el('div', undefined, 'settings-update-toolbar');
  toolbar.append(reload, check, approve, cancel);
  host.append(el('h3', 'CivicRelay updates'), el('p', 'Checks contact the public Camreyn/CivicRelay release service only. They send no credentials, mailbox content, requester details, local paths or installation IDs. Automatic checks start off disabled and never download or install software.'), info, form, unsaved, toolbar, status, release, guide);
  function controls() {
    for (const node of [automatic, save, reload, check]) node.disabled = busy;
    const stage = saved?.approved?.stage;
    approve.disabled = busy || !saved?.update_available || !saved.latest?.package || ['ready', 'extracted'].includes(stage) || stage === 'installed' && saved.approved.release?.version === saved.latest.version;
    cancel.hidden = stage !== 'ready'; cancel.disabled = busy;
    host.setAttribute('aria-busy', String(busy));
  }
  function render() {
    onAvailable(saved?.update_available === true);
    info.textContent = saved ? `Installed version: ${saved.installed_version} · Last check: ${saved.last_checked_at ? new Date(saved.last_checked_at * 1000).toLocaleString() : 'Not yet'}` : 'Update status has not loaded.';
    if (saved && !dirty) automatic.checked = saved.automatic_checks === true;
    unsaved.textContent = dirty ? 'You have an unsaved update-check preference. Reloading status does not discard it.' : '';
    release.replaceChildren();
    if (saved?.latest) {
      release.append(el('h4', saved.update_available ? `Version ${saved.latest.version} is available` : 'No newer stable version is available'));
      // Never execute release Markdown/HTML or trust a URL from release notes.
      const url = `https://github.com/Camreyn/CivicRelay/releases/tag/v${saved.latest.version}`;
      if (/^\d+\.\d+\.\d+$/.test(saved.latest.version)) {
        const link = el('a', 'Read the official release notes');
        link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        release.append(link);
      }
      const notes = el('pre', typeof saved.latest.notes === 'string' ? saved.latest.notes.slice(0, 12000) : '');
      notes.className = 'settings-update-notes';
      release.append(notes);
      if (saved.update_available && !saved.latest.package) release.append(el('p', 'This release has no verified guided-update package. Use the manual upgrade guide; no automatic source ZIP installation is attempted.'));
    }
    if (saved?.last_error) release.append(el('p', saved.last_error, 'settings-last-error'));
    guide.replaceChildren();
    const approved = saved?.approved;
    if (approved) {
      guide.append(el('h4', approved.stage === 'installed' ? 'New version installed; switch over manually' : approved.stage === 'failed' ? 'Installation did not complete' : approved.stage === 'cancelled' ? 'Update plan cancelled; files retained' : approved.stage === 'extracted' ? 'Installation completion is not yet confirmed' : 'Approved package is ready'));
      if (['failed', 'cancelled'].includes(approved.stage)) {
        guide.append(el('p', 'The old app is unchanged. Any prior archive/candidate is retained for review. Check the release and approve a fresh download to retry.'));
        return controls();
      }
      const steps = el('ol');
      for (const text of [
        'Finish active work. Close the dashboard SERVER, not just this browser tab, and stop both CivicRelay assistant connections. The updater will not stop processes for you.',
        'In the CURRENT app folder, double-click Update CivicRelay.cmd. Review the version and new folder, then type INSTALL to approve installation. The installer verifies the package, installs locked dependencies, and runs synthetic tests.',
        `After the installer reports success, open the new permanent folder: ${approved.destination}. Start its Open CivicRelay.cmd and update your shortcut.`,
        'Review your assistant connection paths for the new folder, preserving tool allowlists and permissions, then reconnect both tool servers. Do not run both versions.',
      ]) steps.append(el('li', text));
      guide.append(steps, el('p', 'Templates, requester defaults, credentials, receipts and records remain in their existing Windows-user storage. The old application folder and its .private, .local and .codex directories remain untouched and are not copied. This is not a data backup or an automatic database rollback.', 'settings-note'));
    }
    controls();
  }
  async function action(name, args, message, after) {
    if (busy) return;
    busy = true; status.textContent = message; controls();
    try {
      const result = await request(name, args);
      if (!result || typeof result.automatic_checks !== 'boolean' || typeof result.installed_version !== 'string') throw Error('Update status was not returned.');
      saved = result;
      after?.();
      status.textContent = name === 'approve' ? 'Approved package verified and ready. It has NOT been installed; follow the steps below.'
        : result.last_error && name === 'check' ? 'The release check failed. The previous result is retained; nothing was installed.'
        : name === 'preferences' ? 'Update preference saved. No software was downloaded or installed.' : name === 'cancel' ? 'Ready update plan cancelled. Its files and receipt were retained.' : 'Update status loaded. Nothing was installed.';
    } catch (error) {
      status.textContent = `Could not confirm the update action. ${typeof error?.message === 'string' ? error.message.slice(0, 500) : 'Reload status before retrying.'} There is no automatic installation or retry.`;
    } finally { busy = false; render(); }
  }
  async function load() { await action('status', {}, 'Loading saved update status…'); }
  async function automaticCheck() {
    if (document.visibilityState !== 'visible' || busy || !saved?.automatic_checks) return;
    if (saved.last_checked_at && Date.now() / 1000 - saved.last_checked_at < (saved.check_interval_seconds || 86400)) return;
    await action('check', {automatic: true}, 'Checking for updates (enabled preference)…');
  }
  function start(initial) {
    if (started || !initial || typeof initial.automatic_checks !== 'boolean') return;
    started = true; saved = initial; render();
    void automaticCheck();
    timer = setInterval(() => { void automaticCheck(); }, 60 * 60 * 1000);
    document.addEventListener('visibilitychange', automaticCheck);
    window.addEventListener('pagehide', () => {
      clearInterval(timer); document.removeEventListener('visibilitychange', automaticCheck); started = false;
    }, {once: true});
  }
  function resume(event) {
    if (event.persisted && saved) start(saved);
  }
  window.addEventListener('pageshow', resume);
  automatic.addEventListener('change', render);
  controls();
  return {load, start};
}

async function updateRequest(action, args) {
  const response = await fetch('/api/updates', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Records-Desk': '1'}, body: JSON.stringify({action, arguments: args})});
  const result = await response.json();
  if (!response.ok || result.ok !== true) throw Error(result.error || 'The updater is unavailable.');
  return result.result;
}
