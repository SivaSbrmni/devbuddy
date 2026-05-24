"""
Token encryption helper.

Wraps Fernet symmetric encryption so we can store secrets like GitHub PATs
and MCP API keys encrypted at rest.

Key derivation: SECRET_KEY (already in settings) is hashed to a 32-byte key.
Rotating SECRET_KEY will require re-encrypting existing rows.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("crypto")

_PREFIX = "enc::v1::"   # marker so we can detect already-encrypted values


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str | None) -> str | None:
    """Encrypt a secret string. Returns None if input is None/empty."""
    if not plain:
        return None
    if plain.startswith(_PREFIX):
        return plain  # already encrypted
    token = _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return _PREFIX + token


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a previously-encrypted value. Returns None if input is None/empty."""
    if not value:
        return None
    if not value.startswith(_PREFIX):
        # Backward-compat: legacy plaintext token. Treat as plain and warn.
        logger.warning("legacy_plaintext_secret_detected")
        return value
    cipher = value[len(_PREFIX):]
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("invalid_encrypted_secret_cannot_decrypt")
        return None
