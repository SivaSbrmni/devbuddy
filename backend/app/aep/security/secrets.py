"""SecretManager — Phase 6.

AES-256-GCM encryption at rest for secrets. Never logs plaintext.
Metadata stored in ``aep_secrets_metadata``; ciphertext in an opaque
blob column. Integration with GitHub Secrets for workflow injection.

Spec reference: AGENTS.md Phase 6 — SecretManager, spec §10.1.
"""
from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.aep.observability import aep_logger

_logger = aep_logger("aep.security.secrets")

_NONCE_SIZE = 12  # 96-bit nonce for AES-GCM
_KEY_ENV = "AEP_SECRET_ENCRYPTION_KEY"


class SecretManagerError(Exception):
    """Base exception for SecretManager operations."""


class EncryptionKeyMissing(SecretManagerError):
    """Raised when the encryption key is not configured."""


class SecretNotFound(SecretManagerError):
    """Raised when a secret does not exist."""


class SecretManager:
    """Manages encrypted secrets with AES-256-GCM.

    The encryption key is derived from the ``AEP_SECRET_ENCRYPTION_KEY``
    environment variable using SHA-256 to produce a 32-byte key.

    Secrets are stored as:
        nonce (12 bytes) || ciphertext || tag (16 bytes)
    Base64-encoded for storage in the database.
    """

    def __init__(self, *, encryption_key: Optional[str] = None) -> None:
        key_material = encryption_key or os.environ.get(_KEY_ENV, "")
        if not key_material:
            self._aesgcm: Optional[AESGCM] = None
            _logger.warning("secret_manager_no_key", env_var=_KEY_ENV)
        else:
            derived = hashlib.sha256(key_material.encode()).digest()
            self._aesgcm = AESGCM(derived)

    def _ensure_key(self) -> AESGCM:
        if self._aesgcm is None:
            raise EncryptionKeyMissing(
                f"Encryption key not configured. Set {_KEY_ENV} env var."
            )
        return self._aesgcm

    def encrypt(self, plaintext: str, *, associated_data: Optional[bytes] = None) -> str:
        """Encrypt plaintext and return base64-encoded ciphertext."""
        aesgcm = self._ensure_key()
        nonce = os.urandom(_NONCE_SIZE)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), associated_data)
        blob = nonce + ct
        return base64.b64encode(blob).decode()

    def decrypt(self, ciphertext_b64: str, *, associated_data: Optional[bytes] = None) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        aesgcm = self._ensure_key()
        blob = base64.b64decode(ciphertext_b64)
        nonce = blob[:_NONCE_SIZE]
        ct = blob[_NONCE_SIZE:]
        plaintext = aesgcm.decrypt(nonce, ct, associated_data)
        return plaintext.decode()

    async def store_secret(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        value: str,
        secret_type: str = "generic",
        db: Any,
    ) -> dict[str, Any]:
        """Encrypt and store a secret. Metadata goes to aep_secrets_metadata."""
        from sqlalchemy import text

        encrypted = self.encrypt(value, associated_data=str(tenant_id).encode())
        secret_id = uuid.uuid4()

        await db.execute(
            text(
                """
                INSERT INTO aep_secrets_metadata
                    (id, tenant_id, name, secret_type, encrypted_value,
                     created_at, updated_at, rotated_at)
                VALUES
                    (:id, :tenant_id, :name, :secret_type, :encrypted_value,
                     :created_at, :updated_at, NULL)
                ON CONFLICT (tenant_id, name) DO UPDATE SET
                    encrypted_value = EXCLUDED.encrypted_value,
                    secret_type = EXCLUDED.secret_type,
                    updated_at = EXCLUDED.updated_at,
                    rotated_at = NOW()
                """
            ),
            {
                "id": str(secret_id),
                "tenant_id": str(tenant_id),
                "name": name,
                "secret_type": secret_type,
                "encrypted_value": encrypted,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await db.commit()

        _logger.info(
            "secret_stored",
            tenant_id=str(tenant_id),
            name=name,
            secret_type=secret_type,
        )
        return {"id": str(secret_id), "name": name, "status": "stored"}

    async def get_secret(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        db: Any,
    ) -> str:
        """Retrieve and decrypt a secret by name."""
        from sqlalchemy import text

        result = await db.execute(
            text(
                """
                SELECT encrypted_value FROM aep_secrets_metadata
                WHERE tenant_id = :tenant_id AND name = :name
                """
            ),
            {"tenant_id": str(tenant_id), "name": name},
        )
        row = result.fetchone()
        if row is None:
            raise SecretNotFound(f"Secret '{name}' not found for tenant {tenant_id}")

        return self.decrypt(row[0], associated_data=str(tenant_id).encode())

    async def delete_secret(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        db: Any,
    ) -> bool:
        """Delete a secret by name."""
        from sqlalchemy import text

        result = await db.execute(
            text(
                """
                DELETE FROM aep_secrets_metadata
                WHERE tenant_id = :tenant_id AND name = :name
                """
            ),
            {"tenant_id": str(tenant_id), "name": name},
        )
        await db.commit()
        deleted = result.rowcount > 0

        if deleted:
            _logger.info("secret_deleted", tenant_id=str(tenant_id), name=name)
        return deleted

    async def rotate_secret(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        new_value: str,
        db: Any,
    ) -> dict[str, Any]:
        """Rotate a secret (re-encrypt with new value)."""
        return await self.store_secret(
            tenant_id=tenant_id,
            name=name,
            value=new_value,
            db=db,
        )

    async def list_secrets(
        self,
        *,
        tenant_id: uuid.UUID,
        db: Any,
    ) -> list[dict[str, Any]]:
        """List secret metadata (never plaintext values)."""
        from sqlalchemy import text

        result = await db.execute(
            text(
                """
                SELECT id, name, secret_type, created_at, updated_at, rotated_at
                FROM aep_secrets_metadata
                WHERE tenant_id = :tenant_id
                ORDER BY name
                """
            ),
            {"tenant_id": str(tenant_id)},
        )
        rows = result.fetchall()
        return [
            {
                "id": str(row[0]),
                "name": row[1],
                "secret_type": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
                "rotated_at": row[5].isoformat() if row[5] else None,
            }
            for row in rows
        ]


_singleton: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    global _singleton
    if _singleton is None:
        _singleton = SecretManager()
    return _singleton
