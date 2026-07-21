"""Credential protection for values stored in config.json.

The LoTW password is an *outbound* credential - the app must present the real
value to lotw.arrl.org, so a one-way hash is impossible. Instead it is
encrypted at rest with Windows DPAPI (CryptProtectData), bound to the current
Windows user account: config.json never contains the plaintext, and the blob
is useless on another machine or account (relevant when the folder syncs to
OneDrive). On non-Windows platforms the value falls back to plaintext with a
marker-free store (documented limitation).
"""
from __future__ import annotations

import base64

PREFIX = "dpapi:"
_DESCRIPTION = "DX Command LoTW credential"


class SecretError(Exception):
    pass


def protect(plain: str) -> str:
    """Encrypt a secret for storage. Idempotent; empty stays empty."""
    if not plain or plain.startswith(PREFIX):
        return plain
    try:
        import win32crypt
        blob = win32crypt.CryptProtectData(
            plain.encode("utf-8"), _DESCRIPTION, None, None, None, 0)
        return PREFIX + base64.b64encode(blob).decode("ascii")
    except ImportError:
        return plain    # non-Windows: no DPAPI available


def reveal(stored: str) -> str:
    """Decrypt a stored secret for use. Raises SecretError if the blob was
    created by a different Windows user/machine."""
    if not stored or not stored.startswith(PREFIX):
        return stored
    try:
        import win32crypt
        _desc, plain = win32crypt.CryptUnprotectData(
            base64.b64decode(stored[len(PREFIX):]), None, None, None, 0)
        return plain.decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - pywintypes.error, binascii...
        raise SecretError(
            "stored password cannot be decrypted on this machine/account - "
            "re-enter it in SETUP") from exc


def is_protected(stored: str) -> bool:
    return bool(stored) and stored.startswith(PREFIX)


def merge_secret(old_stored: str, new_value: str | None) -> str:
    """Settings-save semantics: None/blank keeps the stored secret;
    a new plaintext value replaces it (protected)."""
    if new_value is None or new_value == "":
        return old_stored or ""
    return protect(new_value)
