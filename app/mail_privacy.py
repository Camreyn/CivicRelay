"""Previewed mailbox configuration and conservative local-only import cleanup."""
import hashlib
import re
import time
import uuid

import mail_scope
from secure_store import ConnectorError, canonical

ARGUMENTS = {
    'desk_get_mail_scope': set(),
    'desk_preview_mail_scope': {'mode', 'incoming_folder', 'sent_folder', 'import_history'},
    'desk_apply_mail_scope': {'preview_id', 'expected_digest'},
    'desk_preview_mail_cleanup': {'message_ids'},
    'desk_apply_mail_cleanup': {'preview_id', 'expected_digest'},
}
READ_ONLY = {'desk_get_mail_scope'}
TTL = 600


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def protected_ids(service, messages):
    """Never clean case evidence, originals, send chains or audit references."""
    protected = {m['id'] for m in messages if m.get('case_id') or m.get('captured') or m.get('raw_blob_id') or m.get('artifact_ids')}
    referenced = set()
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            referenced.add(value)
            referenced.update(re.findall(r'(?:[0-9a-f]{24}:)?(?:INBOX|Sent):[0-9]+:[0-9]+', value))
            referenced.update(re.findall(r'<[^<>\s]{1,200}>', value))
    for kind in ('case', 'artifact', 'issue', 'event', 'campaign'):
        for value in service.db.all(kind):
            walk(value)
    # Read local immutable draft identities only; never touch SMTP/IMAP or quota.
    if (service.mail_store.root / 'drafts.sqlite3').exists():
        with service.mail_store.database(readonly=True) as con:
            for row in con.execute('SELECT * FROM drafts'):
                draft = service.mail_store.decode(row)
                for key in ('message_id', 'in_reply_to', 'references'):
                    walk(draft.get(key))
    protected.update(m['id'] for m in messages if m['id'] in referenced)
    # Preserve the entire connected reply chain, including unassigned ancestors.
    by_token = {}
    tokens = {}
    for m in messages:
        values = set(re.findall(r'<[^<>\s]{1,200}>', ' '.join(str(m.get(k, '')) for k in ('message_id', 'in_reply_to', 'references'))))
        tokens[m['id']] = values
        for value in values:
            by_token.setdefault(value, set()).add(m['id'])
    pending = list(referenced)
    for key in protected:
        pending.extend(tokens.get(key, ()))
    seen = set()
    while pending:
        token = pending.pop()
        if token in seen:
            continue
        seen.add(token)
        for key in by_token.get(token, ()):
            if key not in protected:
                protected.add(key)
                pending.extend(tokens[key])
    return protected


def overview(service):
    scope = mail_scope.summary(service.mail_store)
    messages = service.db.all('mail')
    hidden = [m for m in messages if not mail_scope.visible(scope, m)]
    return {'scope': scope, 'hidden_imports': len(hidden),
            'saved_messages': len(messages), 'network_accessed': False,
            'guidance': 'New connections start from the preview boundary. Use custom CivicRelay folders/labels for a personal account. Existing case-linked records stay available locally. Scope changes never delete originals or reset send history.'}


def save_preview(service, kind, payload):
    key = uuid.uuid4().hex
    plan = {'id': key, 'created_at': time.time(), 'expires_at': time.time() + TTL, **payload}
    plan['digest'] = digest(plan)
    service.db.put(kind, key, plan)
    return plan


def get_preview(service, kind, args):
    key = args.get('preview_id')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key):
        raise ConnectorError('Choose an exact privacy preview.')
    plan = service.db.get(kind, key)
    if not plan or plan.get('digest') != args.get('expected_digest'):
        raise ConnectorError('Privacy preview digest changed or was not found.')
    if plan.get('applied'):
        return plan
    if digest({k: v for k, v in plan.items() if k != 'digest'}) != plan['digest'] or plan['expires_at'] < time.time():
        raise ConnectorError('Privacy preview expired or changed. Prepare a new preview.')
    return plan


def dispatch(service, name, args):
    if name == 'desk_get_mail_scope':
        return overview(service)
    if name == 'desk_preview_mail_scope':
        old = mail_scope.read(service.mail_store)
        scope = mail_scope.snapshot(service.settings(), args.get('mode'), args.get('incoming_folder', ''),
                                    args.get('sent_folder', ''), args.get('import_history', False))
        plan = save_preview(service, 'mail_scope_preview', {'scope': scope, 'expected_revision': old['revision']})
        return {'preview_id': plan['id'], 'digest': plan['digest'], 'expires_at': plan['expires_at'],
                'scope': {k: v for k, v in scope.items() if k != 'identity'},
                'warning': 'Dedicated mode exposes the selected account Inbox and Sent. Use folders mode for a personal account. Import history includes all existing mail in the selected folders. No mail has been imported or deleted.',
                'message_bodies_read': 0, 'message_headers_read': 0, 'network_accessed': True}
    if name == 'desk_apply_mail_scope':
        plan = get_preview(service, 'mail_scope_preview', args)
        current = mail_scope.read(service.mail_store)
        # Recover an applied atomic scope write even if the caller lost its reply.
        if current.get('id') != plan['scope']['id']:
            if plan.get('applied'):
                raise ConnectorError('A newer scope is active. Reload saved mail privacy settings.')
            service.mail_store.save_mail_scope(plan['scope'], plan['expected_revision'])
        service.db.put('mail_scope_preview', plan['id'], {**plan, 'applied': True})
        return {**overview(service), 'mail_imported': 0, 'messages_deleted_from_proton': 0}
    if name == 'desk_preview_mail_cleanup':
        messages = service.db.all('mail')
        protected = protected_ids(service, messages)
        scope = mail_scope.read(service.mail_store)
        ids = args.get('message_ids')
        if ids is not None:
            if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
                raise ConnectorError('Choose 1–100 distinct saved message IDs for cleanup.')
            known = {m['id'] for m in messages}
            if set(ids) - known:
                raise ConnectorError('A selected message is no longer saved. Preview again.')
            if set(ids) & protected:
                raise ConnectorError('Selected mail is protected by case, attachment, draft, reply-chain or audit evidence. It will not be removed by this tool.')
            candidates = [m for m in messages if m['id'] in ids]
            remaining = 0
        else:
            candidates = [m for m in messages if m['id'] not in protected and not mail_scope.visible(scope, m)]
            remaining = max(0, len(candidates) - 100)
            candidates = candidates[:100]
        plan = save_preview(service, 'mail_cleanup', {'messages': [{'id': m['id'], 'hash': digest(m),
            'body_hash': digest(service.db.get('body', m['id'])), 'exclusion': mail_scope.header_fingerprint(m)} for m in candidates]})
        return {'preview_id': plan['id'], 'digest': plan['digest'], 'expires_at': plan['expires_at'],
                'candidates': [{k: m.get(k) for k in ('id', 'folder', 'from', 'subject', 'date', 'body_loaded')} for m in candidates],
                'count': len(candidates), 'remaining_hidden_candidates': remaining, 'protected_count': len(protected),
                'warning': 'Removes only these local imported headers and cached bodies. Original Proton mail, case-linked evidence, captured originals, drafts, receipts and quotas are not deleted. This cannot erase assistant transcripts, prior exports or backups. Header fingerprints prevent routine re-import.',
                'network_accessed': False}
    if name == 'desk_apply_mail_cleanup':
        plan = get_preview(service, 'mail_cleanup', args)
        if plan.get('applied'):
            return plan['receipt']
        messages = service.db.all('mail')
        protected = protected_ids(service, messages)
        if {m['id'] for m in plan['messages']} & protected:
            raise ConnectorError('A candidate became protected evidence. Nothing was removed; preview again.')
        receipt = {'removed_local_messages': len(plan['messages']), 'messages_deleted_from_proton': 0,
                   'drafts_or_receipts_changed': 0, 'network_accessed': False, 'preview_id': plan['id']}
        service.db.remove_mail_imports(plan, receipt)
        return receipt
    raise ConnectorError('Unknown mail privacy operation.')
