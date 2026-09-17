"""Narrow mail operations. No scheduling, arbitrary files, URLs, or shell commands."""
from __future__ import annotations

from datetime import datetime, timezone
from email.headerregistry import Address
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

VERSION = "0.3.0"
PROJECT_EMAIL = "CivicResultMaps@proton.me"
LEGACY_DISPLAY_NAME = "CivicResultMaps"
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


def display_name(value) -> str:
    return clean_text(value, 120)


def profile_id(value) -> str:
    if not isinstance(value, str):
        raise ConnectorError("Profile identity is missing. Run local setup.")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ConnectorError("Profile identity is invalid. Run local setup.") from None
    if str(parsed) != value or parsed.version != 4:
        raise ConnectorError("Profile identity is invalid. Run local setup.")
    return value


def is_legacy_settings(settings: dict) -> bool:
    return isinstance(settings, dict) and settings.get("version") == 1


def validate_settings(settings: dict) -> dict:
    if not isinstance(settings, dict) or type(settings.get("version")) is not int or settings.get("version") not in (1, 2):
        raise ConnectorError("Unknown connector settings version. Run local setup.")
    email = address(settings.get("email"))
    if settings["version"] == 1 and email.casefold() != PROJECT_EMAIL.casefold():
        raise ConnectorError("Only the reviewed CivicResultMaps project email can be enrolled in this connector.")
    if settings["version"] == 2:
        display_name(settings.get("display_name"))
        profile_id(settings.get("profile_id"))
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


def account_summary(store: Store) -> dict:
    """Credential-free identity/status contract for the local dashboard."""
    store.guard_paths()
    configured = (store.root / "settings.dpapi").exists()
    result = {"configured": configured, "email": None, "display_name": None,
              "profile_id": None, "legacy_storage": "CivicResultMaps" in store.root.parts,
              "private_storage": str(store.root), "local_only": True}
    if not configured:
        return result
    settings = validate_settings(store.settings())
    if is_legacy_settings(settings):
        result.update(email=settings["email"], display_name=LEGACY_DISPLAY_NAME, profile_id=None,
                      legacy_settings=True)
    else:
        result.update(email=settings["email"], display_name=settings["display_name"],
                      profile_id=settings["profile_id"], legacy_settings=False)
    return result


def digest(payload: dict) -> str:
    """v1 is byte-preserved; v2 binds the reviewed profile to its content."""
    content = {key: payload[key] for key in CONTENT_KEYS}
    if payload.get("draft_version") == 2:
        content.update(draft_version=2, display_name=payload["display_name"], profile_id=payload["profile_id"])
    return hashlib.sha256(canonical(content)).hexdigest()


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
    draft_version = draft.get("draft_version")
    if draft_version is not None and (type(draft_version) is not int or draft_version != 2):
        raise ConnectorError("Draft version is invalid. No message was created.")
    if draft_version == 2:
        # Headerregistry quotes/encodes display names so commas or angle brackets
        # cannot become extra mailboxes or change the bound addr-spec.
        message["From"] = Address(display_name=draft["display_name"], addr_spec=draft["from"])
    else:
        # v1 bytes are part of the legacy reviewed-draft contract.
        message["From"] = f"{LEGACY_DISPLAY_NAME} <{draft['from']}>"
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
    """Validate the exact draft and current sending eligibility before dispatch."""
    if not settings["sending_enabled"]:
        raise ConnectorError("Sending is disabled. Enable it yourself in the local setup window only when ready.")
    draft = store.get_draft(valid_uuid(arguments.get("draft_id")))
    expected = arguments.get("expected_digest", "")
    checked = validate_content(draft, settings["email"])
    if draft["from"] != settings["email"] or checked != {k: draft[k] for k in CONTENT_KEYS}:
        raise ConnectorError("Draft no longer matches the configured project sender.")
    if draft.get("draft_version") == 2:
        if is_legacy_settings(settings) or draft.get("display_name") != settings["display_name"] or draft.get("profile_id") != settings["profile_id"]:
            raise ConnectorError("Draft no longer matches the configured mailbox profile.")
    elif not is_legacy_settings(settings):
        # A legacy draft can only be sent by the legacy identity it was bound to.
        raise ConnectorError("Legacy drafts require the retained legacy mailbox settings.")
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


def send_draft(store: Store, settings: dict, arguments: dict) -> dict:
    try:
        draft, expected = _preflight_send(store, settings, arguments)
    except ConnectorError as error:
        # Only known preflight failures receive this marker. It must never
        # describe an atomic-claim or SMTP outcome.
        raise SendPreflightError(str(error)) from error
    # Enrollment can change concurrently. Recheck before claiming/authenticating.
    if validate_settings(store.settings()) != settings:
        raise ConnectorError("Connector settings changed during preflight. Review again.")
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
    "proton_send_draft": {"draft_id", "expected_digest"},
}


def dispatch(name: str, arguments: dict, store: Store | None = None) -> dict:
    if name not in ARGUMENTS or not isinstance(arguments, dict) or set(arguments) - ARGUMENTS[name]:
        raise ConnectorError("Unknown operation or unexpected arguments.")
    store = store or Store()
    if name == "proton_status":
        store.guard_paths()
        summary = account_summary(store)
        configured = summary["configured"]
        result = {"version": VERSION, **summary, "network_accessed": False}
        if configured:
            settings = validate_settings(store.settings())
            result.update(sending_enabled=settings["sending_enabled"],
                          imap_port=settings["imap_port"], smtp_port=settings["smtp_port"],
                          mailbox_isolation="User-attested separate account or split-address mode; not independently verified by IMAP.",
                          confirmation="No CivicRelay per-action approval dialog.",
                          requires_desktop_confirmation=False)
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
        if is_legacy_settings(settings):
            identity = {}
        else:
            identity = {"draft_version": 2, "display_name": settings["display_name"], "profile_id": settings["profile_id"]}
        payload = {**content, **identity, "draft_id": draft_id,
                   "message_id": f"<{draft_id}@{settings['email'].split('@')[1]}>",
                   "created_at": datetime.now(timezone.utc).isoformat()}
        payload["digest"] = digest(payload)
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
