"""Private per-Windows-user storage. Never store mail or credentials in the repo."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import math
from typing import Any, Iterator


class ConnectorError(Exception):
    """Only fixed, non-secret messages from this exception may reach the host."""


class SendPreflightError(ConnectorError):
    """A send was rejected before the local human approval window was opened."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class WindowsProtector:
    """DPAPI CurrentUser, with no password in arguments, environment, or logs."""

    @staticmethod
    def _crypt(data: bytes, decrypt: bool) -> bytes:
        if os.name != "nt":
            raise ConnectorError("Private storage requires Windows DPAPI.")

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        buffer = ctypes.create_string_buffer(data)
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        output = Blob()
        if decrypt:
            call = crypt32.CryptUnprotectData
            second = None
        else:
            call = crypt32.CryptProtectData
            second = "CivicResultMaps Proton connector"
        call.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p if decrypt else wintypes.LPCWSTR,
                         ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(Blob)]
        call.restype = wintypes.BOOL
        try:
            if not call(ctypes.byref(source), second, None, None, None, 1, ctypes.byref(output)):
                raise ConnectorError("Windows could not unlock private connector data for this user.")
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            ctypes.memset(buffer, 0, len(data))
            if output.pbData:
                ctypes.memset(output.pbData, 0, output.cbData)
                kernel32.LocalFree(output.pbData)

    def protect(self, value: Any) -> bytes:
        return self._crypt(canonical(value), False)

    def unprotect(self, data: bytes) -> Any:
        return json.loads(self._crypt(data, True).decode("utf-8"))


def guard_repository_location(root: Path, repo: Path) -> None:
    """Added 2026-09-10: never place private storage in this or another Git checkout."""
    resolved, repository = root.resolve(), repo.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ConnectorError("Private storage must be outside the application repository.")
    # A .git directory or worktree pointer file both identify a working tree.
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ConnectorError("Private storage must be outside every Git working tree.")


def private_root() -> Path:
    # Modified 2026-09-10: standalone repository guard; legacy data path retained.
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise ConnectorError("A normal Windows user session is required.")
    local = Path(os.environ["LOCALAPPDATA"])
    if not local.is_absolute() or len(local.drive) != 2 or local.drive[1] != ":":
        raise ConnectorError("Private storage requires an absolute local Windows drive path.")
    root = local / "CivicResultMaps" / "ProtonConnector"
    # Modified for connector/ layout; the legacy private store stays unchanged.
    repo = Path(__file__).resolve().parents[1]
    guard_repository_location(root, repo)
    return root


class Store:
    MAX_SEND_ATTEMPTS = 10
    SEND_WINDOW_SECONDS = 86400
    MINIMUM_SEND_INTERVAL_SECONDS = 60
    def __init__(self, root: Path | None = None, protector: Any = None):
        # Explicit overrides are for in-process tests, never exposed by CLI/MCP.
        self.root = private_root() if root is None else root
        self.protector = protector or WindowsProtector()

    def guard_paths(self) -> None:
        guard_repository_location(self.root, Path(__file__).resolve().parents[1])
        # Refuse redirected private storage, including Windows junctions. A local
        # adversary with this user's privileges is still outside the DPAPI threat model.
        for path in (self.root, *self.root.parents):
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                    raise ConnectorError("Private storage cannot use symbolic links or junctions.")
        for name in ("settings.dpapi", "drafts.sqlite3", "drafts.sqlite3-journal", "drafts.sqlite3-wal", "drafts.sqlite3-shm"):
            path = self.root / name
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if path.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or info.st_nlink > 1:
                    raise ConnectorError("Private files cannot use symbolic links, junctions, or hard links.")

    def settings(self) -> dict:
        self.guard_paths()
        path = self.root / "settings.dpapi"
        if not path.exists():
            raise ConnectorError("Not configured. Run the local connector setup window first.")
        return self.protector.unprotect(path.read_bytes())

    def save_settings(self, settings: dict) -> None:
        self.guard_paths()
        self.root.mkdir(parents=True, exist_ok=True)
        protected = self.protector.protect(settings)
        fd, name = tempfile.mkstemp(prefix="settings-", suffix=".dpapi", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(protected)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.root / "settings.dpapi")
        finally:
            Path(name).unlink(missing_ok=True)

    @contextmanager
    def database(self, readonly: bool = False) -> Iterator[sqlite3.Connection]:
        self.guard_paths()
        if readonly:
            path = self.root / "drafts.sqlite3"
            if not path.exists():
                raise ConnectorError("Draft not found.")
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.root / "drafts.sqlite3", timeout=10)
        try:
            db.row_factory = sqlite3.Row
            if not readonly:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("""CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, state TEXT NOT NULL,
                    payload BLOB NOT NULL, attempted_at REAL)""")
            with db:
                yield db
        finally:
            db.close()

    def insert_draft(self, payload: dict) -> dict:
        payload = {**payload, "state": "draft", "attempted_at": None, "receipt": None}
        with self.database() as db:
            if db.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] >= 5000:
                raise ConnectorError("Local draft limit reached. Review the private store before adding more.")
            db.execute("INSERT OR IGNORE INTO drafts (id,digest,state,payload) VALUES (?,?,?,?)",
                       (payload["draft_id"], payload["digest"], "draft",
                        self.protector.protect(payload)))
            row = db.execute("SELECT * FROM drafts WHERE digest=?", (payload["digest"],)).fetchone()
            return self.decode(row)

    def decode(self, row: sqlite3.Row | None) -> dict:
        if row is None:
            raise ConnectorError("Draft not found.")
        payload = self.protector.unprotect(row["payload"])
        for key, column in (("draft_id", "id"), ("digest", "digest"), ("state", "state"), ("attempted_at", "attempted_at")):
            if payload.get(key) != row[column]:
                raise ConnectorError("Private draft record failed its integrity check. No action was taken.")
        content = {key: payload[key] for key in ("from", "to", "cc", "subject", "body", "in_reply_to", "references")}
        if hashlib.sha256(canonical(content)).hexdigest() != payload["digest"]:
            raise ConnectorError("Private draft content failed its integrity check. No action was taken.")
        return payload

    def get_draft(self, draft_id: str) -> dict:
        with self.database(readonly=True) as db:
            return self.decode(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())

    def list_drafts(self, limit: int) -> list[dict]:
        if not (self.root / "drafts.sqlite3").exists():
            return []
        with self.database(readonly=True) as db:
            rows = db.execute("SELECT * FROM drafts ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
            result = []
            for row in rows:
                payload = self.decode(row)
                result.append({key: payload[key] for key in
                               ("draft_id", "digest", "state", "to", "cc", "subject", "created_at")})
            return result

    @staticmethod
    def _timestamp(value: Any) -> float:
        # The encrypted envelope and its unencrypted index must both be sane.
        # Do not let a malformed timestamp turn a safety check into an exception
        # or a permissive result.
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ConnectorError("Private draft record failed its integrity check. No action was taken.")
        return float(value)

    def _decoded_records(self, db: sqlite3.Connection) -> list[dict]:
        try:
            rows = db.execute("SELECT * FROM drafts").fetchall()
        except sqlite3.Error as error:
            raise ConnectorError("Private draft record failed its integrity check. No action was taken.") from error
        records = [self.decode(row) for row in rows]
        for record in records:
            attempted_at = record["attempted_at"]
            if attempted_at is not None:
                self._timestamp(attempted_at)
        return records

    @classmethod
    def _send_window_for_records(cls, records: list[dict], now: float) -> dict:
        now = cls._timestamp(now)
        timestamps = sorted(cls._timestamp(record["attempted_at"])
                            for record in records if record["attempted_at"] is not None)
        active = [timestamp for timestamp in timestamps if timestamp > now - cls.SEND_WINDOW_SECONDS]
        latest = max(timestamps) if timestamps else None
        cooldown_at = latest + cls.MINIMUM_SEND_INTERVAL_SECONDS if latest is not None else now
        quota_at = now
        if len(active) >= cls.MAX_SEND_ATTEMPTS:
            # More than ten recent records can exist after a clock adjustment or
            # an older implementation. Expire enough of the oldest records to
            # leave space for this one prospective attempt.
            quota_at = active[len(active) - cls.MAX_SEND_ATTEMPTS] + cls.SEND_WINDOW_SECONDS
        next_attempt_at = max(now, cooldown_at, quota_at)
        ready = next_attempt_at <= now
        if ready:
            reason = "ready"
        elif quota_at >= cooldown_at and quota_at > now:
            reason = "daily_limit"
        else:
            reason = "cooldown"
        retry_after = max(0, math.ceil(next_attempt_at - now))
        messages = {
            "ready": "A new send attempt may be approved.",
            "cooldown": "Wait for the minimum interval before another send attempt.",
            "daily_limit": "Wait for an earlier send attempt to leave the rolling daily window.",
        }
        return {"ready": ready, "checked_at": now, "next_attempt_at": next_attempt_at,
                "retry_after_seconds": retry_after, "attempts_remaining": max(0, cls.MAX_SEND_ATTEMPTS - len(active)),
                "attempts_used": len(active), "max_attempts": cls.MAX_SEND_ATTEMPTS,
                "window_seconds": cls.SEND_WINDOW_SECONDS,
                "minimum_interval_seconds": cls.MINIMUM_SEND_INTERVAL_SECONDS,
                "reason": reason, "message": messages[reason]}

    def send_window(self, now: float) -> dict:
        """Read the rate-limit state without creating private files or reserving a send."""
        now = self._timestamp(now)
        self.guard_paths()
        if not (self.root / "drafts.sqlite3").exists():
            return self._send_window_for_records([], now)
        with self.database(readonly=True) as db:
            return self._send_window_for_records(self._decoded_records(db), now)

    def claim_send(self, draft_id: str, digest: str, now: float) -> None:
        with self.database() as db:
            db.execute("BEGIN IMMEDIATE")
            # Index columns are not trusted independently of the DPAPI envelope.
            records = self._decoded_records(db)
            if not self._send_window_for_records(records, now)["ready"]:
                raise ConnectorError("Pilot limit reached: at most 10 send attempts per 24 hours, at least 60 seconds apart.")
            record = next((record for record in records if record["draft_id"] == draft_id), None)
            if not record or record["state"] != "draft" or record["digest"] != digest:
                raise ConnectorError("Draft is not eligible for a new send attempt.")
            record.update(state="sending", attempted_at=now)
            cursor = db.execute("UPDATE drafts SET state='sending', attempted_at=?, payload=? WHERE id=? AND digest=? AND state='draft'",
                                (now, self.protector.protect(record), draft_id, digest))
            if cursor.rowcount != 1:
                raise ConnectorError("Draft is no longer sendable. Inspect its receipt; never automatically retry an uncertain send.")

    def finish_send(self, draft_id: str, state: str, receipt: dict) -> None:
        if state not in ("accepted", "uncertain", "failed_before_data"):
            raise ConnectorError("Invalid send receipt state.")
        with self.database() as db:
            db.execute("BEGIN IMMEDIATE")
            record = self.decode(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())
            if record["state"] != "sending":
                raise ConnectorError("Could not durably record the send receipt. Reconcile manually; do not retry.")
            record.update(state=state, receipt=receipt)
            cursor = db.execute("UPDATE drafts SET state=?, payload=? WHERE id=? AND state='sending'",
                                (state, self.protector.protect(record), draft_id))
            if cursor.rowcount != 1:
                raise ConnectorError("Could not durably record the send receipt. Reconcile manually; do not retry.")
