"""Receipt-backed send reconciliation shared by mutations and read-only queues."""
import equipment


def outcome(draft):
    """An accepted state alone is not evidence that SMTP accepted this message."""
    state = draft.get('state', 'unavailable')
    if state == 'accepted' and not equipment.valid_receipt(draft):
        return 'receipt_invalid'
    return state


def reconciled(case, draft, draft_id):
    """Whether the saved workflow already consumed this draft's current outcome.

    A reply can have the same outcome as its predecessor, so state alone is
    insufficient. Older cases lack the draft marker; their saved accepted
    timestamp identifies a receipt already consumed by the previous code.
    This preserves subsequent operator choices such as closing a case.
    """
    state = outcome(draft)
    if case.get('latest_send_state') != state:
        return False
    recorded_id = case.get('latest_send_draft_id')
    if recorded_id is not None:
        return recorded_id == draft_id
    if state == 'accepted':
        return case.get('last_sent_at') == draft['receipt']['accepted_at']
    return True
