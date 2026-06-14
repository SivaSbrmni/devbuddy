"""Simple XOR encryption for user API keys — no external dependencies."""

from __future__ import annotations

import base64
from itertools import cycle
from typing import Any

from app.core.config import settings


class _Crypto:
    """Simple XOR cipher keyed from SECRET_KEY. Obfuscates keys at rest."""

    def __init__(self) -> None:
        self._key = settings.SECRET_KEY.encode()

    def _xor(self, data: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, cycle(self._key)))

    def encrypt(self, plaintext: str) -> str:
        return base64.b64encode(self._xor(plaintext.encode())).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._xor(base64.b64decode(ciphertext.encode())).decode()

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
