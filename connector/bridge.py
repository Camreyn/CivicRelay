"""Bounded, loopback-only Proton Bridge access. TLS pins are checked before auth."""
from __future__ import annotations

from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
import hashlib
import hmac
from html.parser import HTMLParser
import imaplib
import re
import smtplib
import ssl

from secure_store import ConnectorError

HOST = "127.0.0.1"
TIMEOUT = 15
MAX_MESSAGE = 2 * 1024 * 1024
BIDI = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f")


def display(value: str, limit: int = 1000) -> str:
    return "".join(c for c in str(value) if (ord(c) >= 32 or c in "\n\t") and ord(c) != 127 and c not in BIDI)[:limit]


def pin_context() -> ssl.SSLContext:
    # Bridge supplies a self-signed cert. Authentication is strictly forbidden
    # until its DER SHA-256 matches the separately enrolled local fingerprint.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def fingerprint(sock) -> str:
    cert = sock.getpeercert(binary_form=True)
    if not cert:
        raise ConnectorError("Bridge did not provide a TLS certificate.")
    return hashlib.sha256(cert).hexdigest()


def verify_pin(sock, expected: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not hmac.compare_digest(fingerprint(sock), expected):
        raise ConnectorError("Bridge certificate changed. Re-enroll it in the local setup window; no credentials were sent.")


@contextmanager
def imap_connection(settings: dict, authenticate: bool = True):
    connection = imaplib.IMAP4(HOST, settings["imap_port"], timeout=TIMEOUT)
    try:
        connection.starttls(ssl_context=pin_context())
        if authenticate:
            verify_pin(connection.sock, settings["imap_pin"])
            connection.login(settings["email"], settings["password"])
        yield connection
    finally:
        # No CLOSE/EXPUNGE and no cleanup exception after an otherwise successful read.
        try:
            connection.logout()
        except Exception:
            try:
                connection.shutdown()
            except Exception:
                pass


@contextmanager
def smtp_connection(settings: dict, authenticate: bool = True):
    connection = smtplib.SMTP(HOST, settings["smtp_port"], local_hostname="localhost", timeout=TIMEOUT)
    try:
        connection.ehlo()
        connection.starttls(context=pin_context())
        if authenticate:
            verify_pin(connection.sock, settings["smtp_pin"])
            connection.ehlo()
            connection.login(settings["email"], settings["password"])
        yield connection
    finally:
        # A QUIT failure must not change an accepted send into a retryable error.
        try:
            connection.quit()
        except Exception:
            connection.close()


def probe(imap_port: int, smtp_port: int) -> dict:
    settings = {"imap_port": imap_port, "smtp_port": smtp_port}
    with imap_connection(settings, authenticate=False) as connection:
        imap_pin = fingerprint(connection.sock)
    with smtp_connection(settings, authenticate=False) as connection:
        smtp_pin = fingerprint(connection.sock)
    return {"imap_pin": imap_pin, "smtp_pin": smtp_pin}


def check(settings: dict) -> dict:
    with imap_connection(settings) as connection:
        connection.noop()
    with smtp_connection(settings) as connection:
        connection.noop()
    return {"imap_authenticated": True, "smtp_authenticated": True,
            "message_bodies_read": 0, "messages_sent": 0}


def select_readonly(connection, folder: str) -> int:
    status, _ = connection.select(folder, readonly=True)
    if status != "OK":
        raise ConnectorError("Requested project folder is unavailable in Bridge.")
    _, values = connection.response("UIDVALIDITY")
    if not values or not values[0] or not re.fullmatch(rb"[0-9]+", values[0]):
        raise ConnectorError("Bridge did not supply a stable mailbox identity.")
    return int(values[0])


def literal(data, limit: int) -> bytes:
    chunks = [part[1] for part in data if isinstance(part, tuple) and isinstance(part[1], bytes)]
    if len(chunks) != 1 or len(chunks[0]) > limit:
        raise ConnectorError("Bridge response is missing, oversized, or ambiguous.")
    return chunks[0]


def verify_uid(data, expected: int) -> None:
    metadata = b" ".join(part[0] if isinstance(part, tuple) else part for part in data
                         if isinstance(part, (tuple, bytes)))
    identifiers = re.findall(rb"\bUID ([0-9]+)\b", metadata)
    if not identifiers or any(int(value) != expected for value in identifiers):
        raise ConnectorError("Bridge returned a different or missing message UID. Refresh the message list.")


def headers(message) -> dict:
    return {name.replace("-", "_").lower(): display(str(message.get(name, ""))) for name in
            ("From", "To", "Cc", "Subject", "Date", "Message-ID", "In-Reply-To")}


def list_messages(settings: dict, folder: str, limit: int, before_uid: int | None) -> dict:
    with imap_connection(settings) as connection:
        validity = select_readonly(connection, folder)
        if before_uid == 1:
            ids = []
        else:
            criteria = ("UID", f"1:{before_uid - 1}") if before_uid else ("ALL",)
            status, data = connection.uid("search", None, *criteria)
            if status != "OK" or not data or len(data[0]) > MAX_MESSAGE:
                raise ConnectorError("Bridge search failed or exceeded the result limit.")
            ids = data[0].split()
            if any(not re.fullmatch(rb"[0-9]+", uid) for uid in ids):
                raise ConnectorError("Bridge returned invalid message identifiers.")
            ids = sorted(set(int(uid) for uid in ids))
            if before_uid:
                ids = [uid for uid in ids if uid < before_uid]
        selected = list(reversed(ids[-limit:]))
        messages = []
        for uid in selected:
            status, data = connection.uid("fetch", str(uid),
                "(UID BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID IN-REPLY-TO)]<0.16384>)")
            if status != "OK":
                raise ConnectorError("A message changed during inspection. Refresh the list.")
            raw = literal(data, 16384)
            verify_uid(data, uid)
            item = headers(BytesParser(policy=policy.default).parsebytes(raw))
            item.update(uid=uid, headers_may_be_truncated=len(raw) == 16384)
            messages.append(item)
        return {"untrusted_email_content": True, "folder": folder, "uid_validity": validity,
                "messages": messages, "next_before_uid": min(selected) if len(ids) > limit else None,
                "read_only": True}


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_message(raw: bytes) -> dict:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    attachments = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment" or part.get_filename():
            attachments.append({"filename": display(part.get_filename() or "unnamed", 200),
                                "content_type": display(part.get_content_type(), 100)})
    # get_body excludes attached messages/text instead of walking their content.
    body = ""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is not None:
        content = part.get_content()
        if isinstance(content, str) and part.get_content_type() == "text/plain":
            body = content
        elif isinstance(content, str) and part.get_content_type() == "text/html":
            parser = PlainHTML()
            parser.feed(content)
            body = "".join(parser.parts)
    return {**headers(message), "body": display(body, 20000), "body_truncated": len(body) > 20000,
            "attachments": attachments[:30], "attachments_truncated": len(attachments) > 30,
            "untrusted_email_content": True, "remote_content_loaded": False,
            "attachments_saved": False, "attachments_executed": False,
            "attachment_bytes_may_be_in_raw_message": True}


def read_message(settings: dict, folder: str, uid: int, uid_validity: int) -> dict:
    with imap_connection(settings) as connection:
        if select_readonly(connection, folder) != uid_validity:
            raise ConnectorError("Mailbox identity changed. List messages again before reading.")
        status, data = connection.uid("fetch", str(uid), "(UID RFC822.SIZE)")
        sizes = re.findall(rb"RFC822\.SIZE ([0-9]+)", b" ".join(x for x in data if isinstance(x, bytes)))
        if status != "OK" or len(sizes) != 1:
            raise ConnectorError("Message no longer exists or its size is unavailable.")
        verify_uid(data, uid)
        if int(sizes[0]) > MAX_MESSAGE:
            raise ConnectorError("Message exceeds the 2 MiB safety limit. Open it directly in Proton Mail.")
        status, data = connection.uid("fetch", str(uid), f"(UID BODY.PEEK[]<0.{MAX_MESSAGE + 1}>)")
        if status != "OK":
            raise ConnectorError("Could not read the selected message.")
        raw = literal(data, MAX_MESSAGE)
        verify_uid(data, uid)
        if len(raw) != int(sizes[0]):
            raise ConnectorError("Message was truncated or changed during retrieval.")
        return {**parse_message(raw), "uid": uid, "uid_validity": uid_validity,
                "folder": folder, "read_only": True}
