"""Explicit local sending-policy edits, independent of credentials and mail scope."""
import time
import connector

ARGUMENTS = {
    'desk_get_send_limits': set(),
    'desk_save_send_limits': {'revision', 'max_attempts_per_24h', 'minimum_interval_seconds'},
}
READ_ONLY = {'desk_get_send_limits'}


def dispatch(service, name, args):
    if name == 'desk_get_send_limits':
        result = service.mail_store.get_send_limits(time.time())
        result['configured'] = connector.account_summary(service.mail_store)['configured']
        return result
    # Credential validation remains local; never accept credentials or enable sending here.
    service.settings()
    result = service.mail_store.save_send_limits(args.get('revision'),
        args.get('max_attempts_per_24h'), args.get('minimum_interval_seconds'), time.time())
    return {**result, 'configured': True}
