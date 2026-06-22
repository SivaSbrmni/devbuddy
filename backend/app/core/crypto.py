"""Authenticated encryption for user API keys.

Uses AES-256-GCM (via the ``cryptography`` package that ships as a transitive
dependency of ``python-jose[cryptography]``).  The master key is derived from
``SECRET_KEY`` using SHA-256 so no additional key-management infra is needed.

Migration / backward-compatibility
-----------------------------------
Existing values in the database were encrypted with the previous XOR cipher.
``decrypt`` transparently tries AES-GCM first; if that fails it falls back to
XOR so that **no data migration script is required**.  New writes always use
AES-GCM, so the proportion of XOR-encrypted values shrinks naturally over time
as users save updated provider settings.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from itertools import cycle
from typing import Any

from app.core.config import settings


class _Crypto:
    """AES-256-GCM encryption keyed from SECRET_KEY.

    Falls back to the legacy XOR cipher only when *decrypting* values that
    were written by the old code, ensuring zero-downtime migration.
    """

    def __init__(self) -> None:
        # Derive a fixed 32-byte key from SECRET_KEY using SHA-256.
        self._key32 = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        # Keep the raw key bytes for the XOR fallback path.
        self._xor_key = settings.SECRET_KEY.encode()

    # ── AES-256-GCM (primary) ────────────────────────────────────────────

    def _aesgcm_encrypt(self, plaintext: str) -> str:
        """Encrypt with AES-256-GCM. Returns base64(nonce‖ciphertext‖tag)."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = secrets.token_bytes(12)  # 96-bit random nonce for GCM
        aesgcm = AESGCM(self._key32)
        # AESGCM.encrypt appends the 16-byte authentication tag to ciphertext
        ciphertext_tag = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext_tag).decode()

    def _aesgcm_decrypt(self, ciphertext: str) -> str:
        """Decrypt AES-256-GCM ciphertext. Raises on auth failure."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        combined = base64.b64decode(ciphertext)
        if len(combined) < 29:  # 12 nonce + 1 plaintext + 16 tag minimum
            raise ValueError("Ciphertext too short for AES-GCM")
        nonce = combined[:12]
        ciphertext_tag = combined[12:]
        aesgcm = AESGCM(self._key32)
        plaintext = aesgcm.decrypt(nonce, ciphertext_tag, None)
        return plaintext.decode()

    # ── Legacy XOR (decryption fallback only) ────────────────────────────

    def _xor(self, data: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, cycle(self._xor_key)))

    def _xor_decrypt(self, ciphertext: str) -> str:
        return self._xor(base64.b64decode(ciphertext.encode())).decode()

    # ── Public interface ─────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> str:
        """Encrypt with AES-256-GCM."""
        return self._aesgcm_encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt, trying AES-GCM first then XOR for backward compatibility."""
        if not ciphertext:
            return ""
        try:
            return self._aesgcm_decrypt(ciphertext)
        except Exception:
            # Fallback: legacy XOR-encrypted values from pre-migration data.
            try:
                return self._xor_decrypt(ciphertext)
            except Exception:
                # Already plaintext — return as-is (migration safety net).
                return ciphertext

    def encrypt_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Encrypt the 'key' field inside each provider config entry."""
        result: dict[str, Any] = {}
        for provider, cfg in data.items():
            if isinstance(cfg, dict) and "key" in cfg and cfg["key"]:
                result[provider] = {
                    **cfg,
                    "key": self.encrypt(cfg["key"]),
                }
            else:
                result[provider] = cfg
        return result

    def decrypt_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Decrypt the 'key' field inside each provider config entry."""
        result: dict[str, Any] = {}
        for provider, cfg in data.items():
            if isinstance(cfg, dict) and "key" in cfg and cfg["key"]:
                result[provider] = {
                    **cfg,
                    "key": self.decrypt(cfg["key"]),
                }
            else:
                result[provider] = cfg
        return result


crypto = _Crypto()


# Convenience functions for encrypting/decrypting single values
def encrypt_value(plaintext: str) -> str:
    """Encrypt a single string value with AES-256-GCM."""
    return crypto.encrypt(plaintext)


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a single string value (AES-GCM with XOR fallback)."""
    if not ciphertext:
        return ""
    return crypto.decrypt(ciphertext)
