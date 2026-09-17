"""Local credential enrollment. Operational sends do not open desktop dialogs."""
from __future__ import annotations

import sys
import threading
import uuid
import tkinter as tk
from tkinter import messagebox, ttk

import bridge
from connector import address, display_name, integer, validate_settings
from secure_store import ConnectorError, Store


def setup() -> None:
    store = Store()
    root = tk.Tk()
    root.title("CivicRelay - Proton Bridge connector setup")
    root.geometry("820x660")
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Enroll one dedicated CivicRelay mailbox", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Choose a dedicated Proton Bridge address and a display name. Paste the NEW Bridge-generated password below, not your Proton account password.\n"
              "Credentials stay on this PC, encrypted for your Windows user. Nothing is sent by setup.\n"
              "Mail later provided to the assistant is processed outside Proton by OpenAI.", wraplength=750).pack(anchor="w", pady=(12, 16))
    fields = {}
    for label, key, default in (("Dedicated email / Bridge username", "email", ""),
                                ("Sender display name", "display_name", ""),
                                ("Bridge-generated password", "password", ""),
                                ("Local IMAP port", "imap_port", "1143"),
                                ("Local SMTP port", "smtp_port", "1025")):
        ttk.Label(frame, text=label).pack(anchor="w", pady=(6, 2))
        value = tk.StringVar(value=default)
        entry = ttk.Entry(frame, textvariable=value, show="*" if key == "password" else "")
        entry.pack(fill="x")
        fields[key] = value
        if key == "password":
            password_entry = entry
    isolated = tk.BooleanVar(value=False)
    sending = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, variable=isolated, text="I confirm this Bridge login is isolated to this dedicated mailbox (separate account or split-address mode).").pack(anchor="w", pady=(18, 8))
    ttk.Checkbutton(frame, variable=sending, text="Enable sending. Requested sends proceed without a separate CivicRelay confirmation dialog.").pack(anchor="w", pady=4)
    ttk.Label(frame, text="Mailbox isolation is your confirmation; IMAP cannot independently prove it.\n"
              "Host is fixed to 127.0.0.1. STARTTLS is mandatory.\n"
              "You will confirm the local TLS fingerprints before the password is used.\n"
              "Existing mailbox history locks its identity: setup cannot switch it to another account.\n"
              "Re-running setup requires entering the Bridge password again.", wraplength=750).pack(anchor="w", pady=12)
    status = tk.StringVar(value="Ready. Passwords are never printed or written as plaintext.")
    ttk.Label(frame, textvariable=status, wraplength=740).pack(anchor="w", pady=8)
    pending = {"settings": None}

    def failed():
        pending["settings"] = None
        status.set("Connection failed. Check Bridge is running, ports, split-address mode, and the current Bridge password. No raw error or credential was logged.")
        button.state(["!disabled"])

    def authenticate(settings):
        try:
            bridge.check(settings)
            validate_settings(settings)
            store.save_settings(settings)
            root.after(0, success)
        except Exception:
            root.after(0, failed)

    def success():
        pending["settings"] = None
        fields["password"].set("")
        status.set("Saved securely. IMAP and SMTP authenticated. No messages read or sent. You can close this window.")
        button.state(["!disabled"])
        messagebox.showinfo("Connector configured", "The Bridge connection works and credentials were saved with Windows DPAPI.\n\nNo messages were read or sent. Restart the MCP connection in Codex to activate the new tools.", parent=root)

    def trust(settings):
        text = ("Trust these local Bridge TLS certificates?\n\n"
                "This is explicit trust-on-first-use for the Bridge app you installed on this PC.\n"
                "Only proceed if you recognize this local Bridge setup.\n\n"
                f"IMAP SHA-256:\n{settings['imap_pin']}\n\nSMTP SHA-256:\n{settings['smtp_pin']}\n\n"
                "Later certificate changes will block login until you re-enroll here.\n"
                "Confirming will test authentication only, then save encrypted settings.")
        if not messagebox.askyesno("Trust local Proton Bridge", text, parent=root, default="no"):
            pending["settings"] = None
            status.set("Cancelled. No password was sent or saved.")
            button.state(["!disabled"])
            return
        status.set("Authenticating to pinned local Bridge endpoints; no mail is being read or sent...")
        threading.Thread(target=authenticate, args=(settings,), daemon=True).start()

    def discover(settings):
        try:
            settings.update(bridge.probe(settings["imap_port"], settings["smtp_port"]))
            root.after(0, lambda: trust(settings))
        except Exception:
            root.after(0, failed)

    def connect():
        if not isolated.get():
            messagebox.showwarning("Dedicated mailbox required", "Confirm mailbox isolation before connecting. Do not enroll a combined personal inbox.", parent=root)
            return
        try:
            email = address(fields["email"].get().strip())
            name = display_name(fields["display_name"].get().strip())
            legacy = store.retained_legacy_identity(email, name)
            settings = {"version": 1 if legacy else 2, "email": email,
                        "password": fields["password"].get(),
                        "imap_port": integer(int(fields["imap_port"].get()), 1024, 65535),
                        "smtp_port": integer(int(fields["smtp_port"].get()), 1024, 65535),
                        "project_mailbox_confirmed": True, "sending_enabled": sending.get()}
            if not legacy:
                settings.update(display_name=name, profile_id=store.retained_profile_id(email, name) or str(uuid.uuid4()))
            if not 1 <= len(settings["password"]) <= 512:
                raise ConnectorError("Enter the current Bridge-generated password.")
        except (ConnectorError, ValueError):
            messagebox.showwarning("Check settings", "Enter a plain dedicated email, display name, current Bridge-generated password, and valid local ports (1024-65535).", parent=root)
            return
        pending["settings"] = settings
        button.state(["disabled"])
        status.set("Checking local STARTTLS certificates. No password is sent until you approve the fingerprints...")
        threading.Thread(target=discover, args=(settings,), daemon=True).start()

    button = ttk.Button(frame, text="Verify local Bridge and save securely", command=connect)
    button.pack(anchor="w", pady=8)
    password_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    if sys.argv[1:] != ["setup"]:
        raise SystemExit("Use: pythonw desktop.py setup")
    setup()
