#!/usr/bin/env python3
"""
Email index for persistent storage and querying of classified emails.
Provides SQLite schema, upsert, and query helpers for the intelligent email dashboard.
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import contextmanager


class EmailIndex:
    """Persistent index of classified emails for dashboard and search."""

    def __init__(self, db_path: str = "./data/emails.db"):
        self.db_path = db_path
        self._ensure_database()

    @contextmanager
    def get_db(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_database(self):
        """Create database tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gmail_id VARCHAR(64) UNIQUE NOT NULL,
                    thread_id VARCHAR(64) NOT NULL,
                    sender TEXT NOT NULL,
                    sender_domain VARCHAR(255),
                    subject TEXT NOT NULL,
                    snippet TEXT,
                    body_text TEXT,
                    received_at TIMESTAMP,
                    labels TEXT,
                    priority VARCHAR(20) DEFAULT 'medium',
                    urgency VARCHAR(20) DEFAULT 'low',
                    relevance FLOAT,
                    categories TEXT,
                    summary TEXT,
                    classification VARCHAR(50),
                    confidence FLOAT,
                    reason TEXT,
                    embedding_id INTEGER,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_emails_gmail_id ON emails(gmail_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_priority ON emails(priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender_domain ON emails(sender_domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_classification ON emails(classification)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER NOT NULL,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails(id)
                )
            """)

    def _extract_domain(self, sender: str) -> str:
        """Extract domain from email address."""
        if not sender:
            return ""
        match = re.search(r"@([\w.-]+)", sender)
        return match.group(1).lower() if match else ""

    def upsert(
        self,
        gmail_id: str,
        thread_id: str,
        sender: str,
        subject: str,
        snippet: str = "",
        body_text: str = "",
        received_at: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: str = "medium",
        urgency: str = "low",
        relevance: float = 0.5,
        categories: Optional[List[str]] = None,
        summary: Optional[str] = None,
        classification: Optional[str] = None,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> int:
        """
        Insert or update an email record. Returns the row id.
        """
        sender_domain = self._extract_domain(sender)
        labels_json = json.dumps(labels) if labels else None
        categories_json = json.dumps(categories) if categories else None

        with self.get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO emails (
                    gmail_id, thread_id, sender, sender_domain, subject, snippet, body_text,
                    received_at, labels, priority, urgency, relevance, categories,
                    summary, classification, confidence, reason, processed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gmail_id) DO UPDATE SET
                    thread_id = excluded.thread_id,
                    sender = excluded.sender,
                    sender_domain = excluded.sender_domain,
                    subject = excluded.subject,
                    snippet = excluded.snippet,
                    body_text = excluded.body_text,
                    received_at = excluded.received_at,
                    labels = excluded.labels,
                    priority = excluded.priority,
                    urgency = excluded.urgency,
                    relevance = excluded.relevance,
                    categories = excluded.categories,
                    summary = excluded.summary,
                    classification = excluded.classification,
                    confidence = excluded.confidence,
                    reason = excluded.reason,
                    processed_at = excluded.processed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    gmail_id,
                    thread_id,
                    sender,
                    sender_domain,
                    subject,
                    snippet,
                    body_text,
                    received_at,
                    labels_json,
                    priority,
                    urgency,
                    relevance,
                    categories_json,
                    summary,
                    classification,
                    confidence,
                    reason,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )
            row_id = cursor.lastrowid
            if row_id is None:
                cursor = conn.execute("SELECT id FROM emails WHERE gmail_id = ?", (gmail_id,))
                row_id = cursor.fetchone()["id"]
        return row_id

    def get_by_gmail_id(self, gmail_id: str) -> Optional[Dict[str, Any]]:
        """Get a single email by Gmail message ID."""
        with self.get_db() as conn:
            cursor = conn.execute("SELECT * FROM emails WHERE gmail_id = ?", (gmail_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def get_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        sender_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent emails with optional filters.
        category can match classifications or categories JSON array.
        """
        query = "SELECT * FROM emails WHERE 1=1"
        params: List[Any] = []

        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if category:
            query += " AND (classification = ? OR categories LIKE ?)"
            params.extend([category, f"%{category}%"])
        if sender_domain:
            query += " AND sender_domain = ?"
            params.append(sender_domain)

        query += " ORDER BY received_at DESC, processed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_db() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_grouped_by_sender(
        self,
        limit: int = 20,
        min_count: int = 1,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get senders grouped by email count, optionally filtered by priority.
        Returns list of {sender, sender_domain, count, latest_subject, latest_received_at}.
        """
        query = """
            SELECT sender, sender_domain, COUNT(*) as count,
                   MAX(subject) as latest_subject,
                   MAX(received_at) as latest_received_at
            FROM emails
            WHERE 1=1
        """
        params: List[Any] = []

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        query += """
            GROUP BY sender, sender_domain
            HAVING count >= ?
            ORDER BY count DESC, latest_received_at DESC
            LIMIT ?
        """
        params.extend([min_count, limit])

        with self.get_db() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get counts for dashboard overview."""
        with self.get_db() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM emails").fetchone()["c"]

            high = conn.execute(
                "SELECT COUNT(*) as c FROM emails WHERE priority = 'high'"
            ).fetchone()["c"]
            medium = conn.execute(
                "SELECT COUNT(*) as c FROM emails WHERE priority = 'medium'"
            ).fetchone()["c"]
            low = conn.execute(
                "SELECT COUNT(*) as c FROM emails WHERE priority = 'low'"
            ).fetchone()["c"]

            cursor = conn.execute(
                """
                SELECT classification, COUNT(*) as count
                FROM emails
                WHERE classification IS NOT NULL
                GROUP BY classification
                """
            )
            by_classification = {row["classification"]: row["count"] for row in cursor}

            return {
                "total": total,
                "by_priority": {"high": high, "medium": medium, "low": low},
                "by_classification": by_classification,
            }

    def search(
        self,
        q: str,
        limit: int = 20,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Simple text search over subject, sender, snippet.
        For Phase 3, this can be enhanced with vector search.
        """
        pattern = f"%{q.replace('%', '%%')}%"
        query = """
            SELECT * FROM emails
            WHERE subject LIKE ? OR sender LIKE ? OR snippet LIKE ?
        """
        params: List[Any] = [pattern, pattern, pattern]

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)

        with self.get_db() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite Row to dict, parsing JSON fields."""
        d = dict(row)
        if d.get("labels"):
            try:
                d["labels"] = json.loads(d["labels"])
            except (TypeError, json.JSONDecodeError):
                pass
        if d.get("categories"):
            try:
                d["categories"] = json.loads(d["categories"])
            except (TypeError, json.JSONDecodeError):
                pass
        return d


def main():
    """Quick test of EmailIndex."""
    index = EmailIndex("./data/emails.db")
    rid = index.upsert(
        gmail_id="msg123",
        thread_id="thr456",
        sender="test@example.com",
        subject="Test email",
        snippet="A test snippet",
        priority="high",
        classification="ecommerce",
        confidence=0.9,
    )
    print(f"Upserted row id: {rid}")
    row = index.get_by_gmail_id("msg123")
    print(f"Retrieved: {row}")
    summary = index.get_dashboard_summary()
    print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
