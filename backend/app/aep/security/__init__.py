"""AEP Security — Phase 6.

Modules:
    - secrets: SecretManager with AES-256 encryption at rest.
    - command_validator: Blocklist enforcement for shell commands.
    - rbac: Role-based access control middleware.
    - tenant_isolation: SQLAlchemy event listener + RLS helpers.
"""
