"""Symmetric encryption for secret settings stored in ``app_settings``.

Secrets are encrypted at rest so a database dump (or the raw JSON value in the
``app_settings`` table) never contains the plaintext. The Fernet key is derived
from ``AUTH_SESSION_SECRET`` via HKDF-SHA256, so no extra secret to manage; key
rotation therefore also invalidates stored secrets (they must be re-entered).
"""

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.auth.config import get_auth_settings

ENC_PREFIX = "enc:v1:"
HKDF_INFO = b"tuban-settings-encryption"


@lru_cache
def _fernet() -> Fernet:
    secret = get_auth_settings().SESSION_SECRET.encode("utf-8")
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO).derive(secret)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(value: str) -> str:
    """Return ``enc:v1:<token>`` for a non-empty value, or ``""``."""
    if not value:
        return ""
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENC_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Decrypt an ``enc:v1:`` value.

    Empty input returns ``""``. A legacy plaintext value (saved before encryption
    was introduced) is returned unchanged so it keeps working until re-saved. A
    token that fails to decrypt (e.g. after key rotation) returns ``""``.
    """
    if not value:
        return ""
    if not value.startswith(ENC_PREFIX):
        return value
    token = value[len(ENC_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
