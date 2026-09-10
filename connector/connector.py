"""Narrow mail operations. No scheduling, arbitrary files, URLs, or shell commands."""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime
import hashlib
import hmac
import re
import time
import uuid

import bridge
from secure_store import ConnectorError, SendPreflightError, Store, canonical

VERSION = "0.1.0"
PROJECT_EMAIL = "CivicResultMaps@proton.me"
FOLDERS = ("INBOX", "Sent")
ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}\Z")
MESSAGE_ID = re.compile(r"<[!-~]{1,200}>\Z")
CONTENT_KEYS = ("from", "to", "cc", "subject", "body", "in_reply_to", "references")


def integer(value, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConnectorError("Integer argument is outside the allowed range.")
    return value


def clean_text(value, maximum: int, multiline: bool = False) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ConnectorError("Text is missing or exceeds the allowed length.")
    value = value.replace("\r\n", "\n") if multiline else value
    if any((ord(c) < 32 and not (multiline and c in "\n\t")) or ord(c) == 127 or c in bridge.BIDI for c in value):
        raise ConnectorError("Control characters, header injection, and bidirectional overrides are not allowed.")
    if not value.strip():
        raise ConnectorError("Text must not be blank.")
    return value


def address(value) -> str:
    value = clean_text(value, 254)
    if not ADDRESS.fullmatch(value) or ".." in value or value.startswith("."):
        raise ConnectorError("Use a plain email address without a display name or angle brackets.")
    return value


def message_id(value) -> str:
    value = clean_text(value, 202)
    if not MESSAGE_ID.fullmatch(value) or any(c in value[1:-1] for c in "<> "):
        raise ConnectorError("Invalid reply Message-ID.")
    return value


def validate_settings(settings: dict) -> dict:
    if not isinstance(settings, dict) or settings.get("version") != 1:
        raise ConnectorError("Unknown connector settings version. Run local setup.")
    if address(settings.get("email")).casefold() != PROJECT_EMAIL.casefold():
        raise ConnectorError("Only the reviewed CivicResultMaps project email can be enrolled in this connector.")
    for key in ("imap_port", "smtp_port"):
        integer(settings.get(key), 1024, 65535)
    for key in ("imap_pin", "smtp_pin"):
        if not isinstance(settings.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", settings[key]):
            raise ConnectorError("TLS pin missing. Re-enroll Bridge in local setup.")
    if settings.get("project_mailbox_confirmed") is not True:
        raise ConnectorError("Project mailbox isolation must be confirmed in local setup.")
    if type(settings.get("sending_enabled")) is not bool:
        raise ConnectorError("Invalid send policy. Run local setup.")
    if not isinstance(settings.get("password"), str) or not 1 <= len(settings["password"]) <= 512:
        raise ConnectorError("Bridge credential is missing. Run local setup.")
    return settings


def digest(payload: dict) -> str:
    return hashlib.sha256(canonical({key: payload[key] for key in CONTENT_KEYS})).hexdigest()


def validate_content(arguments: dict, sender: str) -> dict:
    to, cc = arguments.get("to"), arguments.get("cc", [])
    if not isinstance(to, list) or not isinstance(cc, list) or not 1 <= len(to) <= 5 or len(to) + len(cc) > 5:
        raise ConnectorError("A draft needs 1 to 5 total recipients across To and Cc.")
    to, cc = [address(x) for x in to], [address(x) for x in cc]
    if len(set(x.casefold() for x in to + cc)) != len(to + cc):
        raise ConnectorError("Duplicate recipients are not allowed.")
    reply = message_id(arguments["in_reply_to"]) if arguments.get("in_reply_to") else None
    refs = arguments.get("references", [])
    if not isinstance(refs, list) or len(refs) > 20:
        raise ConnectorError("At most 20 reference Message-IDs are allowed.")
    return {"from": address(sender), "to": to, "cc": cc,
            "subject": clean_text(arguments.get("subject"), 250),
            "body": clean_text(arguments.get("body"), 50000, multiline=True),
            "in_reply_to": reply, "references": [message_id(x) for x in refs]}


def build_message(draft: dict) -> bytes:
    message = EmailMessage(policy=SMTP)
    message["From"] = f"CivicResultMaps <{draft['from']}>"
    message["To"] = ", ".join(draft["to"])
    if draft["cc"]:
        message["Cc"] = ", ".join(draft["cc"])
    message["Subject"] = draft["subject"]
    message["Message-ID"] = message_id(draft["message_id"])
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    if draft["in_reply_to"]:
        message["In-Reply-To"] = draft["in_reply_to"]
    if draft["references"]:
        message["References"] = " ".join(draft["references"])
    message.set_content(draft["body"])
    return message.as_bytes()


def _preflight_send(store: Store, settings: dict, arguments: dict) -> tuple[dict, str]:
    """Validate only the checks that occur before any human approval window."""
    if not settings["sending_enabled"]:
        raise ConnectorError("Sending is disabled. Enable it yourself in the local setup window only when ready.")
    if arguments.get("confirmation") != "SEND_PROTON_DRAFT":
        raise ConnectorError("Sending requires SEND_PROTON_DRAFT and explicit user approval.")
    draft = store.get_draft(valid_uuid(arguments.get("draft_id")))
    expected = arguments.get("expected_digest", "")
    checked = validate_content(draft, settings["email"])
    if draft["from"] != settings["email"] or checked != {k: draft[k] for k in CONTENT_KEYS}:
        raise ConnectorError("Draft no longer matches the configured project sender.")
    if draft["message_id"] != f"<{draft['draft_id']}@{draft['from'].split('@')[1]}>":
        raise ConnectorError("Draft Message-ID does not match its immutable draft identity.")
    if not isinstance(expected, str) or not hmac.compare_digest(digest(draft), expected) or draft["digest"] != expected:
        raise ConnectorError("Draft digest changed. Review the exact current draft before sending.")
    if draft["state"] != "draft":
        raise ConnectorError("This draft has already been attempted. Check its receipt and Proton Sent; automatic retries are blocked.")
    send_window = store.send_window(time.time())
    if not send_window["ready"]:
        raise ConnectorError(f"Sending is temporarily unavailable. Wait {send_window['retry_after_seconds']} seconds before trying again.")
    return draft, expected


def send_draft(store: Store, settings: dict, arguments: dict, confirm=None) -> dict:
    try:
        draft, expected = _preflight_send(store, settings, arguments)
    except ConnectorError as error:
        # This marker is intentionally restricted to failures before the human
        # window. It must never describe an atomic-claim or SMTP outcome.
        raise SendPreflightError(str(error)) from error
    if confirm is None:
        from desktop import confirm_send
        confirm = confirm_send
    if not confirm(draft):
        return {"approved": False, "messages_sent": 0, "draft_id": draft["draft_id"], "state": "draft"}
    # Re-check enrollment/send policy after the user dialog, before claiming or authenticating.
    if validate_settings(store.settings()) != settings:
        raise ConnectorError("Connector settings changed during approval. Review again.")
    wire = build_message(draft)
    store.claim_send(draft["draft_id"], expected, time.time())
    data_started = False
    try:
        with bridge.smtp_connection(settings) as smtp:
            code, _ = smtp.mail(settings["email"])
            if code != 250:
                raise ConnectorError("Bridge refused the sender before message submission.")
            for recipient in draft["to"] + draft["cc"]:
                code, _ = smtp.rcpt(recipient)
                if code not in (250, 251):
                    smtp.rset()
                    raise ConnectorError("Bridge refused a recipient; no message data was submitted.")
            # Never retry after entering DATA, even on a timeout or explicit error.
            data_started = True
            code, _ = smtp.data(wire)
            if code != 250:
                raise ConnectorError("Bridge did not confirm message acceptance.")
        receipt = {"message_id": draft["message_id"], "accepted_at": datetime.now(timezone.utc).isoformat(),
                   "meaning": "Accepted by local Proton Bridge; recipient delivery is not verified."}
        store.finish_send(draft["draft_id"], "accepted", receipt)
        return {"draft_id": draft["draft_id"], "state": "accepted", "receipt": receipt}
    except Exception:
        state = "uncertain" if data_started else "failed_before_data"
        receipt = {"meaning": "Check Proton Sent and recipient state before any manual retry. No automatic retry is available.",
                   "data_submission_started": data_started, "message_id": draft["message_id"]}
        try:
            store.finish_send(draft["draft_id"], state, receipt)
        except Exception:
            return {"draft_id": draft["draft_id"], "state": "receipt_persistence_uncertain", "ok": False,
                    "receipt": {"message_id": draft["message_id"],
                                "meaning": "Could not persist a receipt. Reconcile manually in Proton Sent; never automatically retry."}}
        return {"draft_id": draft["draft_id"], "state": state, "receipt": receipt, "ok": False}


def valid_uuid(value) -> str:
    if not isinstance(value, str):
        raise ConnectorError("A valid draft ID is required.")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ConnectorError("A valid draft ID is required.") from None
    if str(parsed) != value or parsed.version != 4:
        raise ConnectorError("A valid draft ID is required.")
    return value


ARGUMENTS = {
    "proton_status": set(), "proton_check_connection": set(),
    "proton_list_messages": {"folder", "limit", "before_uid"},
    "proton_read_message": {"folder", "uid", "uid_validity"},
    "proton_prepare_draft": {"to", "cc", "subject", "body", "in_reply_to", "references"},
    "proton_list_drafts": {"limit"}, "proton_get_draft": {"draft_id"},
    "proton_send_draft": {"draft_id", "expected_digest", "confirmation"},
}


def dispatch(name: str, arguments: dict, store: Store | None = None) -> dict:
    if name not in ARGUMENTS or not isinstance(arguments, dict) or set(arguments) - ARGUMENTS[name]:
        raise ConnectorError("Unknown operation or unexpected arguments.")
    store = store or Store()
    if name == "proton_status":
        store.guard_paths()
        configured = (store.root / "settings.dpapi").exists()
        result = {"version": VERSION, "configured": configured, "private_storage": str(store.root),
                  "local_only": True, "network_accessed": False}
        if configured:
            settings = validate_settings(store.settings())
            result.update(email=settings["email"], sending_enabled=settings["sending_enabled"],
                          imap_port=settings["imap_port"], smtp_port=settings["smtp_port"],
                          mailbox_isolation="User-attested separate account or split-address mode; not independently verified by IMAP.",
                          confirmation="Every send requires a local human approval window.")
            result["send_window"] = store.send_window(time.time())
        return result
    settings = validate_settings(store.settings())
    if name == "proton_check_connection":
        return bridge.check(settings)
    if name in ("proton_list_messages", "proton_read_message"):
        folder = arguments.get("folder", "INBOX")
        if folder not in FOLDERS:
            raise ConnectorError("Only the project INBOX and Sent folders are available.")
        if name == "proton_list_messages":
            before = arguments.get("before_uid")
            if before is not None:
                integer(before, 1, 4294967295)
            return bridge.list_messages(settings, folder, integer(arguments.get("limit", 10), 1, 20), before)
        return bridge.read_message(settings, folder, integer(arguments.get("uid"), 1, 4294967295),
                                   integer(arguments.get("uid_validity"), 1, 4294967295))
    if name == "proton_prepare_draft":
        content = validate_content(arguments, settings["email"])
        draft_id = str(uuid.uuid4())
        payload = {**content, "draft_id": draft_id, "digest": digest(content),
                   "message_id": f"<{draft_id}@{settings['email'].split('@')[1]}>",
                   "created_at": datetime.now(timezone.utc).isoformat()}
        return {"draft": store.insert_draft(payload), "location": "encrypted_local_store_not_Proton_Drafts",
                "messages_sent": 0}
    if name == "proton_list_drafts":
        return {"drafts": store.list_drafts(integer(arguments.get("limit", 10), 1, 20))}
    if name == "proton_get_draft":
        return {"draft": store.get_draft(valid_uuid(arguments.get("draft_id")))}
    if name == "proton_send_draft":
        return send_draft(store, settings, arguments)
    raise ConnectorError("Operation unavailable.")


def safe_dispatch(name: str, arguments: dict, store: Store | None = None) -> dict:
    try:
        result = dispatch(name, arguments, store)
        return {"ok": result.get("ok", True), "result": result}
    except SendPreflightError as error:
        return {"ok": False, "error": str(error), "send_not_started": True}
    except ConnectorError as error:
        return {"ok": False, "error": str(error)}
    except Exception:
        # Never print upstream IMAP/SMTP, OS, or crypto exception strings: they
        # could contain credentials, message bodies, server banners, or raw data.
        return {"ok": False, "error": "Connector operation failed. Check Bridge is running and credentials are current using local setup. No raw error data was logged."}
