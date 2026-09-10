// Read-only countdowns never queue a send. Only a fresh user click can send.
export function formatWait(seconds) {
  const n = Math.max(0, Math.ceil(seconds));
  if (n >= 3600) return `${Math.floor(n / 3600)}h ${Math.floor(n % 3600 / 60)}m ${n % 60}s`;
  if (n >= 60) return `${Math.floor(n / 60)}m ${n % 60}s`;
  return `${n}s`;
}

export function createSendControls({el, op, caseId, draft, notice, onResult, onReconcile,
  isCurrent = () => true, canStart = () => {}, feedback = '',
  unknownOutcome = '', onUnknownOutcome = () => {},
  now = () => performance.now(), schedule = setTimeout, cancel = clearTimeout}) {
  const node = el('div', undefined, 'send-controls');
  const status = el('p', 'Checking local sending limits…', 'send-status');
  const quota = el('p', '', 'help');
  const info = el('p', feedback, 'send-feedback');
  const error = el('p', '', 'send-error');
  const actions = el('div', undefined, 'actions');
  const send = el('button', 'Checking sending limits…', 'primary');
  const recheck = el('button', 'Check sending availability');
  const reconcile = el('button', 'Reload saved receipt');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  error.setAttribute('role', 'alert');
  info.setAttribute('role', 'status');
  info.hidden = !feedback;
  error.hidden = true;
  for (const b of [send, recheck, reconcile]) b.type = 'button';
  send.disabled = true;
  reconcile.hidden = true;
  actions.append(send, recheck, reconcile);
  node.append(status, quota, info, error, actions);
  let disposed = false, timer = null, window = null, observedAt = 0;
  let busy = false, checking = false, terminal = draft.state !== 'draft', needsReceipt = false;
  const live = () => !disposed && isCurrent();
  const stopTimer = () => { if (timer !== null) cancel(timer); timer = null; };
  const showError = text => { error.textContent = text; error.hidden = !text; };

  function markUnknown(message) {
    needsReceipt = true; stopTimer();
    if (!live()) return;
    send.disabled = true; recheck.disabled = true; reconcile.hidden = false;
    send.textContent = 'Check the saved receipt before retrying';
    status.textContent = 'The send operation did not return a confirmed outcome. No automatic retry will occur. Check any open confirmation window and Proton Sent.';
    showError(message);
  }

  async function readWindow() {
    const {connector} = await op('desk_status', {});
    if (!connector?.configured) throw Error('The connector is not configured. Open its local setup before sending.');
    if (!connector.sending_enabled) throw Error('Sending is disabled in the local connector setup.');
    const w = connector.send_window;
    if (!w || typeof w.ready !== 'boolean' || !Number.isInteger(w.retry_after_seconds) ||
        w.retry_after_seconds < 0 || !Number.isInteger(w.attempts_remaining) ||
        w.attempts_remaining < 0 || !Number.isInteger(w.max_attempts) || w.max_attempts < 1 ||
        w.attempts_remaining > w.max_attempts ||
        !['ready', 'cooldown', 'daily_limit'].includes(w.reason) ||
        (w.ready ? w.retry_after_seconds !== 0 || w.reason !== 'ready' || w.attempts_remaining === 0
          : w.retry_after_seconds === 0 || w.reason === 'ready')) {
      throw Error('Current sending limits could not be verified. Reload the updated local connector before sending.');
    }
    return w;
  }

  function renderWindow() {
    stopTimer();
    if (!live() || busy || checking || terminal || needsReceipt || !window) return;
    const remaining = Math.max(0, Math.ceil(window.retry_after_seconds - (now() - observedAt) / 1000));
    quota.textContent = `${window.attempts_remaining} of ${window.max_attempts} send attempts available in the rolling 24-hour window.`;
    recheck.disabled = false;
    if (!window.ready && remaining > 0) {
      send.disabled = true;
      send.textContent = `Send available in ${formatWait(remaining)}`;
      status.textContent = `${window.reason === 'daily_limit' ? 'Daily sending limit' : 'Waiting period'}: ${formatWait(remaining)} remaining. Nothing is queued or sent automatically.`;
      timer = schedule(() => renderWindow(), 1000);
    } else if (!window.ready) {
      // Refresh local eligibility once the timer expires; never invoke a send.
      void refreshLimits();
    } else {
      send.disabled = false;
      send.textContent = 'Review and send this one email';
      status.textContent = 'Ready for your review. The next step is the required desktop confirmation.';
    }
  }

  async function refreshLimits() {
    if (!live() || busy || checking || terminal || needsReceipt) return;
    stopTimer(); checking = true; send.disabled = true; recheck.disabled = true;
    send.textContent = 'Checking sending limits…';
    status.textContent = 'Checking local sending limits. This check does not send email.';
    try {
      const latest = await readWindow();
      if (!live() || needsReceipt) return;
      window = latest; observedAt = now();
    } catch (e) {
      if (!live() || needsReceipt) return;
      window = null; quota.textContent = '';
      send.textContent = 'Sending availability unverified';
      status.textContent = 'Could not verify sending availability. No send was started.';
      showError(e.message);
    } finally {
      checking = false;
      if (live()) { recheck.disabled = needsReceipt || terminal; renderWindow(); }
    }
  }

  send.onclick = async () => {
    if (!live() || send.disabled || busy || checking || terminal || needsReceipt) return;
    stopTimer(); busy = true; send.disabled = true; recheck.disabled = true; showError(''); info.hidden = true;
    let dispatched = false;
    try {
      canStart();
      status.textContent = 'Checking sending limits before opening confirmation…';
      const latest = await readWindow();
      if (!live()) return;
      window = latest; observedAt = now();
      if (!window.ready) return;
      canStart(); // A person may have edited or navigated during the check.
      status.textContent = 'Check the desktop confirmation window. Nothing sends unless you approve that exact message.';
      send.textContent = 'Awaiting your confirmation…';
      dispatched = true;
      const result = await op('desk_send_email', {case_id: caseId, draft_id: draft.draft_id,
        expected_digest: draft.digest, confirmation: 'SEND_REVIEWED_EMAIL'});
      terminal = result.state !== 'draft';
      const message = result.state === 'accepted'
        ? 'Accepted by Proton Bridge; recipient delivery is not yet confirmed.'
        : result.state === 'draft' ? 'Approval cancelled or expired. Nothing was sent.'
        : `Send state: ${result.state || 'unavailable'}. Check the saved receipt and Proton Sent; do not send again automatically.`;
      notice(message, !['accepted', 'draft'].includes(result.state));
      if (live()) {
        status.textContent = message;
        if (result.state === 'draft') { info.textContent = message; info.hidden = false; }
        send.textContent = terminal ? 'Send attempt recorded — do not resend' : 'Approval cancelled';
      }
      // A refresh may have replaced this control while the request was pending.
      // Still reconcile by case ID; the workspace preserves edits and selection.
      try { await onResult(result); }
      catch {
        const warning = 'The outcome above was returned, but the dashboard could not refresh. Reload the saved receipt; do not repeat Send.';
        if (live()) { needsReceipt = true; reconcile.hidden = false; showError(warning); }
        else notice(warning, true);
      }
    } catch (e) {
      if (dispatched && e.sendNotStarted !== true) {
        const warning = `${e.message} The send outcome is unconfirmed. Check the saved receipt, any open confirmation window and Proton Sent; do not repeat Send.`;
        // Keep the warning even if navigation replaced the originating control.
        notice(warning, true);
        onUnknownOutcome(warning);
        markUnknown(e.message);
      } else {
        if (!live()) return;
        showError(e.message);
        window = null;
        send.textContent = 'Resolve the issue before sending';
        status.textContent = 'No send was started. Resolve the issue, then check availability again.';
      }
    } finally {
      busy = false;
      if (live()) { recheck.disabled = needsReceipt || terminal; renderWindow(); }
    }
  };
  recheck.onclick = async () => { showError(''); await refreshLimits(); };
  reconcile.onclick = async () => {
    if (!live() || reconcile.disabled) return;
    reconcile.disabled = true;
    try { await onReconcile(); }
    catch { if (live()) showError('Could not reload the saved receipt. Inspect Proton Sent before considering another attempt.'); }
    finally { if (live()) reconcile.disabled = false; }
  };
  if (unknownOutcome) markUnknown(unknownOutcome);
  const ready = refreshLimits();
  return {node, ready, refresh: refreshLimits, markUnknown, destroy() {disposed = true; stopTimer();}};
}
