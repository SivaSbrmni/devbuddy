"""Knowledge storage using SQLite."""

import json
import sqlite3
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.knowledge import KnowledgeEntry, KnowledgeCreate


class KnowledgeStore:
    """SQLite-based knowledge storage."""

    def __init__(self, db_path: str = "knowledge.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keywords ON knowledge(keywords)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation ON knowledge(conversation_id)
        """)
        conn.commit()
        conn.close()

    def create(self, entry: KnowledgeCreate) -> KnowledgeEntry:
        """Create a new knowledge entry."""
        from uuid import uuid4
        id = str(uuid4())
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge (id, conversation_id, title, content, keywords, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id, entry.conversation_id, entry.title, entry.content, json.dumps(entry.keywords), entry.category, now, now)
        )
        conn.commit()
        conn.close()

        return KnowledgeEntry(
            id=UUID(id),
            conversation_id=entry.conversation_id,
            title=entry.title,
            content=entry.content,
            keywords=entry.keywords,
            category=entry.category,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now)
        )

    def get_by_id(self, id: str) -> Optional[KnowledgeEntry]:
        """Get knowledge entry by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_entry(row)

    def search(self, query: str, category: Optional[str] = None, limit: int = 10) -> list[KnowledgeEntry]:
        """Search knowledge by query."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple keyword matching - in production, use vector embeddings
        query_lower = query.lower()

        if category:
            cursor.execute(
                """
                SELECT * FROM knowledge
                WHERE category = ?
                AND (LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR keywords LIKE ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (category, f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%", limit)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM knowledge
                WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR keywords LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%", limit)
            )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def get_by_conversation(self, conversation_id: str) -> list[KnowledgeEntry]:
        """Get all knowledge entries for a conversation."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge WHERE conversation_id = ? ORDER BY created_at DESC", (conversation_id,))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: tuple) -> KnowledgeEntry:
        """Convert database row to KnowledgeEntry."""
        return KnowledgeEntry(
            id=UUID(row[0]),
            conversation_id=row[1],
            title=row[2],
            content=row[3],
            keywords=json.loads(row[4]),
            category=row[5],
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7])
        )


# Global instance
knowledge_store = KnowledgeStore()
