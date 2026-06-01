"""Vectorise aep_memory_entries.embedding — Phase 4

Revision ID: 005
Revises: 004
Create Date: 2026-06-01 06:01:00.000000

Alters the ``embedding`` column from ``TEXT`` (JSON-serialised float
array) to ``vector(768)`` to enable KNN similarity search.

Dimension 768 matches the default AEP embedding model
(``nomic-embed-text``). If you switch to a model with a different
dimension (e.g. 1536 for text-embedding-ada-002), update this
migration and re-run.

Upgrade:
    1. Add a temporary ``embedding_vec`` column of type ``vector(768)``.
    2. Cast existing TEXT rows (JSON float arrays) into the vector column.
    3. Drop the old TEXT column.
    4. Rename ``embedding_vec`` → ``embedding``.
    5. Create an IVFFlat index for fast KNN.

Downgrade:
    Reverts to TEXT column with JSON serialisation.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # Step 1: add temporary vector column
    op.execute(
        f"ALTER TABLE aep_memory_entries "
        f"ADD COLUMN embedding_vec vector({EMBEDDING_DIM});"
    )

    # Step 2: migrate existing TEXT embeddings (JSON float arrays) to vector
    # Rows with NULL embedding stay NULL.
    op.execute(
        "UPDATE aep_memory_entries "
        "SET embedding_vec = embedding::vector "
        "WHERE embedding IS NOT NULL;"
    )

    # Step 3: drop old TEXT column
    op.drop_column("aep_memory_entries", "embedding")

    # Step 4: rename
    op.alter_column(
        "aep_memory_entries",
        "embedding_vec",
        new_column_name="embedding",
    )

    # Step 5: create IVFFlat index for cosine similarity KNN
    # lists=100 is a reasonable default for small-to-medium datasets.
    # For large datasets (>1M rows), increase lists to sqrt(n).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_aep_memory_entries_embedding "
        "ON aep_memory_entries "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def downgrade() -> None:
    # Drop the vector index
    op.execute("DROP INDEX IF EXISTS ix_aep_memory_entries_embedding;")

    # Add temporary TEXT column
    op.execute(
        "ALTER TABLE aep_memory_entries "
        "ADD COLUMN embedding_text TEXT;"
    )

    # Migrate vector → TEXT (JSON array)
    op.execute(
        "UPDATE aep_memory_entries "
        "SET embedding_text = embedding::text "
        "WHERE embedding IS NOT NULL;"
    )

    # Drop vector column, rename TEXT back
    op.drop_column("aep_memory_entries", "embedding")
    op.alter_column(
        "aep_memory_entries",
        "embedding_text",
        new_column_name="embedding",
    )
