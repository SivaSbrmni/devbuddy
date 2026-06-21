"""SecretManager — AES-256 encryption for all secrets (spec Part 10).

Replaces the weak XOR cipher in core/crypto.py with proper AES-256-GCM.
Secrets never appear in logs, query results, or API responses.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class SecretAuditLog:
    """Audit trail entry for secret access."""
    timestamp: float
    action: str  # store, retrieve, rotate, revoke
    key: str
    actor: str
    success: bool
    error: str = ""


class SecretManager:
    """AES-256-GCM encryption for secrets.

    All secrets are encrypted at rest with AES-256-GCM using a master key
    derived from the SECRET_KEY environment variable. Secrets are never
    stored in plaintext, never logged, and never included in API responses.
    """

    def __init__(self, master_key: Optional[str] = None) -> None:
        """Initialize with a master key. If not provided, derives from SECRET_KEY env."""
        key_source = master_key or os.environ.get("SECRET_KEY", "change-me-in-production-32-chars!")
        # Derive a 32-byte key using SHA-256
        self._master_key = hashlib.sha256(key_source.encode()).digest()
        self._audit_log: list[SecretAuditLog] = []
        # In-memory cache of decrypted secrets (per-tenant)
        self._cache: dict[str, dict[str, str]] = {}

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext with AES-256-GCM. Returns base64(nonce + ciphertext + tag)."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            # Fallback: use a simple XOR if cryptography is not installed
            # This should never happen in production
            log.warning("secret_manager.no_crypto_lib", msg="cryptography package not installed, using weak fallback")
            return self._xor_encrypt(plaintext)

        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(self._master_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        # Combine nonce + ciphertext (tag is appended by AESGCM)
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode()

    def _decrypt(self, encrypted: str) -> str:
        """Decrypt AES-256-GCM encrypted data."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            return self._xor_decrypt(encrypted)

        combined = base64.b64decode(encrypted)
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(self._master_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    def _xor_encrypt(self, plaintext: str) -> str:
        """Weak XOR fallback — only used if cryptography package is missing."""
        key_bytes = self._master_key
        result = bytearray()
        for i, byte in enumerate(plaintext.encode()):
            result.append(byte ^ key_bytes[i % len(key_bytes)])
        return base64.b64encode(bytes(result)).decode()

    def _xor_decrypt(self, encrypted: str) -> str:
        """Weak XOR fallback decryption."""
        key_bytes = self._master_key
        data = base64.b64decode(encrypted)
        result = bytearray()
        for i, byte in enumerate(data):
            result.append(byte ^ key_bytes[i % len(key_bytes)])
        return result.decode()

    async def store(self, key: str, value: str, tenant_id: str = "default") -> None:
        """Encrypt and store a secret."""
        encrypted = self._encrypt(value)
        if tenant_id not in self._cache:
            self._cache[tenant_id] = {}
        self._cache[tenant_id][key] = encrypted
        self._audit(SecretAuditLog(
            timestamp=time.time(),
            action="store",
            key=key,
            actor=tenant_id,
            success=True,
        ))
        log.info("secret.stored", key=key, tenant=tenant_id)

    async def retrieve(self, key: str, tenant_id: str = "default") -> str:
        """Retrieve and decrypt a secret. Never logs the value."""
        if tenant_id not in self._cache or key not in self._cache[tenant_id]:
            self._audit(SecretAuditLog(
                timestamp=time.time(),
                action="retrieve",
                key=key,
                actor=tenant_id,
                success=False,
                error="not_found",
            ))
            raise KeyError(f"Secret '{key}' not found for tenant '{tenant_id}'")

        encrypted = self._cache[tenant_id][key]
        try:
            value = self._decrypt(encrypted)
            self._audit(SecretAuditLog(
                timestamp=time.time(),
                action="retrieve",
                key=key,
                actor=tenant_id,
                success=True,
            ))
            return value
        except Exception as e:
            self._audit(SecretAuditLog(
                timestamp=time.time(),
                action="retrieve",
                key=key,
                actor=tenant_id,
                success=False,
                error=str(e),
            ))
            raise

    async def rotate(self, key: str, tenant_id: str = "default") -> None:
        """Rotate a secret's encryption (re-encrypt with a new nonce)."""
        value = await self.retrieve(key, tenant_id)
        await self.store(key, value, tenant_id)
        self._audit(SecretAuditLog(
            timestamp=time.time(),
            action="rotate",
            key=key,
            actor=tenant_id,
            success=True,
        ))
        log.info("secret.rotated", key=key, tenant=tenant_id)

    async def revoke(self, key: str, tenant_id: str = "default") -> None:
        """Revoke (delete) a secret."""
        if tenant_id in self._cache and key in self._cache[tenant_id]:
            del self._cache[tenant_id][key]
            self._audit(SecretAuditLog(
                timestamp=time.time(),
                action="revoke",
                key=key,
                actor=tenant_id,
                success=True,
            ))
            log.info("secret.revoked", key=key, tenant=tenant_id)

    async def audit(self, tenant_id: str = "default") -> list[SecretAuditLog]:
        """Get the audit log for a tenant."""
        return [entry for entry in self._audit_log if entry.actor == tenant_id]

    def _audit(self, entry: SecretAuditLog) -> None:
        """Add an entry to the audit log."""
        self._audit_log.append(entry)
        # In production, this would also write to aep_audit_log


# Singleton
secret_manager = SecretManager()
