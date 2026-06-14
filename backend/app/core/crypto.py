"""Simple Fernet encryption for user API keys."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import settings


class _Crypto:
    """Singleton Fernet instance keyed from SECRET_KEY."""

    def __init__(self) -> None:
        # Derive a 32-byte URL-safe base64 key from SECRET_KEY
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def encrypt_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Encrypt the 'key' field inside each provider entry."""
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
        """Decrypt the 'key' field inside each provider entry."""
        result: dict[str, Any] = {}
        for provider, cfg in data.items():
            if isinstance(cfg, dict) and "key" in cfg and cfg["key"]:
                try:
                    result[provider] = {
                        **cfg,
                        "key": self.decrypt(cfg["key"]),
                    }
                except Exception:
                    # If decryption fails, treat as plaintext (migration path)
                    result[provider] = cfg
            else:
                result[provider] = cfg
        return result


crypto = _Crypto()
