"""Shared, fail-closed mailbox boundary for the desk and low-level mail tools.

Folder selection is a local operator decision, never inferred from message text.
No default ALL/INBOX import is permitted, including after a UIDVALIDITY change.
"""
import hashlib
import re
import time
import uuid

from secure_store import ConnectorError, Store, canonical

SETUP_REQUIRED = 'Choose and preview a mailbox scope in Settings > Mail privacy before checking mail.'
EPOCH_CHANGED = 'Mailbox identity changed. Import stopped; earlier successful batches remain saved. Review a new scope preview in Settings > Mail privacy; history is never re-imported automatically.'
SYSTEM_FOLDERS = {'inbox', 'sent', 'all mail', 'all', 'archive', 'trash', 'spam', 'drafts', 'starred'}


def folder_name(value):
    # Printable ASCII also permits Proton's modified-UTF-7 folder names. No
    # control characters, IMAP wildcard, quoting, or backslash injection.
    if not isinstance(value, str) or not 1 <= len(value) <= 160 or value != value.strip() or not re.fullmatch(r'[\x20-\x7e]+', value) or any(c in value for c in '"\\*%'):
        raise ConnectorError('Enter an exact Bridge folder path (up to 160 printable ASCII characters; no quotes, backslashes or wildcards).')
    return value


def quoted_folder(value):
    return '"' + folder_name(value) + '"'


def read(store, required=False):
    value = store.mail_scope()
    if value is None:
        if required:
            raise ConnectorError(SETUP_REQUIRED)
        return {'configured': False, 'revision': 0, 'mode': 'unconfigured', 'folders': {}, 'setup_required': True}
    if value.get('version') != 1 or value.get('mode') not in ('dedicated', 'folders') or type(value.get('revision')) is not int or value['revision'] < 1:
        raise ConnectorError('Saved mail scope is invalid. Review local mail privacy settings.')
    if value.get('identity') != list(Store._identity(store.settings())):
        raise ConnectorError('Mail scope belongs to a different enrolled identity.')
    if not re.fullmatch(r'[0-9a-f]{32}', value.get('id', '')) or type(value.get('import_history')) is not bool:
        raise ConnectorError('Saved mail scope is invalid.')
    folders = value.get('folders')
    if not isinstance(folders, dict) or set(folders) - {'INBOX', 'Sent'} or 'INBOX' not in folders:
        raise ConnectorError('Saved mail folders are invalid.')
    for role, entry in folders.items():
        if not isinstance(entry, dict):
            raise ConnectorError('Saved mail folder boundary is invalid.')
        folder_name(entry.get('remote_folder'))
        for key, minimum in (('uid_validity', 1), ('minimum_uid', 0)):
            if type(entry.get(key)) is not int or not minimum <= entry[key] <= 4294967295:
                raise ConnectorError('Saved mail boundary is invalid.')
        if value['mode'] == 'dedicated' and entry['remote_folder'] != role:
            raise ConnectorError('Dedicated mailbox scope is invalid.')
        if value['mode'] == 'folders' and entry['remote_folder'].casefold() in SYSTEM_FOLDERS:
            raise ConnectorError('Shared mailboxes require dedicated custom folders or labels, not system folders.')
    if len({x['remote_folder'] for x in folders.values()}) != len(folders):
        raise ConnectorError('Incoming and sent folders must be different.')
    return {**value, 'configured': True, 'setup_required': False}


def summary(store):
    scope = read(store)
    return {k: v for k, v in scope.items() if k != 'identity'}


def entry(scope, role):
    if not scope.get('configured'):
        raise ConnectorError(SETUP_REQUIRED)
    if role not in ('INBOX', 'Sent') or role not in scope['folders']:
        raise ConnectorError('This mail folder is outside the selected scope. Configure a dedicated Sent folder/label if Sent inspection is needed; existing drafts and send receipts remain available.')
    return scope['folders'][role]


def select(connection, scope, role):
    import bridge
    target = entry(scope, role)
    validity = bridge.select_readonly(connection, quoted_folder(target['remote_folder']))
    if validity != target['uid_validity']:
        raise ConnectorError(EPOCH_CHANGED)
    return validity


def check_uid(scope, role, validity, uid):
    target = entry(scope, role)
    if validity != target['uid_validity']:
        raise ConnectorError(EPOCH_CHANGED)
    if type(uid) is not int or not target['minimum_uid'] < uid <= 4294967295:
        raise ConnectorError('This message predates the selected mail boundary or is outside its scope.')


def snapshot(settings, mode, incoming_folder='', sent_folder='', import_history=False):
    """SELECT/UIDNEXT only: preview never fetches headers, bodies or attachments."""
    import bridge
    if mode not in ('dedicated', 'folders') or type(import_history) is not bool:
        raise ConnectorError('Choose dedicated or folders mode and an explicit history choice.')
    if mode == 'dedicated':
        if incoming_folder or sent_folder:
            raise ConnectorError('Custom folders are only accepted in folders mode.')
        requested = {'INBOX': 'INBOX', 'Sent': 'Sent'}
    else:
        requested = {'INBOX': folder_name(incoming_folder)}
        if sent_folder:
            requested['Sent'] = folder_name(sent_folder)
        if any(x.casefold() in SYSTEM_FOLDERS for x in requested.values()):
            raise ConnectorError('For an existing personal account, select custom CivicRelay folders/labels, never Inbox, Sent or All Mail.')
        if len(set(requested.values())) != len(requested):
            raise ConnectorError('Incoming and sent folders must be different.')
    folders = {}
    with bridge.imap_connection(settings) as connection:
        for role, remote in requested.items():
            validity = bridge.select_readonly(connection, quoted_folder(remote))
            _, values = connection.response('UIDNEXT')
            if not values or len(values) != 1 or not values[0] or not re.fullmatch(rb'[0-9]+', values[0]):
                raise ConnectorError('Bridge did not supply UIDNEXT. No boundary was saved; do not fall back to importing all mail.')
            next_uid = int(values[0])
            if not 1 <= next_uid <= 4294967295:
                raise ConnectorError('Bridge supplied an invalid mailbox boundary.')
            _, counts = connection.response('EXISTS')
            count = int(counts[0]) if counts and len(counts) == 1 and counts[0] and re.fullmatch(rb'[0-9]+', counts[0]) else None
            folders[role] = {'remote_folder': remote, 'uid_validity': validity,
                             'minimum_uid': 0 if import_history else next_uid - 1,
                             'existing_messages_at_preview': count}
    return {'version': 1, 'id': uuid.uuid4().hex, 'mode': mode,
            'identity': list(Store._identity(settings)), 'import_history': import_history,
            'folders': folders, 'created_at': time.time()}


def message_key(role, validity, uid, remote_folder=None):
    prefix = '' if not remote_folder or remote_folder == role else hashlib.sha256(remote_folder.encode()).hexdigest()[:24] + ':'
    return f'{prefix}{role}:{validity}:{uid}'


def visible(scope, message):
    # Explicit case evidence is retained even if the operator changes the live
    # scope. This permits local review, never an out-of-scope remote body fetch.
    if message.get('case_id'):
        return True
    if not scope.get('configured'):
        return False
    target = scope['folders'].get(message.get('folder'))
    if not target or message.get('remote_folder', message.get('folder')) != target['remote_folder']:
        return False
    if message.get('mail_scope_id') == scope['id']:
        return True
    return (scope['import_history'] and message.get('uid_validity') == target['uid_validity']
            and message.get('uid', 0) > target['minimum_uid'])


def header_fingerprint(message):
    # Retains no plaintext mail in an exclusion record. This is an import
    # suppression key, not a claim that RFC Message-ID alone proves identity.
    keys = ('from', 'to', 'cc', 'subject', 'date', 'message_id', 'in_reply_to', 'references', 'reply_to')
    return hashlib.sha256(canonical({k: message.get(k, '') for k in keys})).hexdigest()
