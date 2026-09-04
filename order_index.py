#!/usr/bin/env python3
"""
Persistent shipment/order index for package tracking dashboard.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

STATUS_ORDER = {
    "unknown": 0,
    "ordered": 1,
    "confirmed": 2,
    "shipped": 3,
    "in_transit": 4,
    "out_for_delivery": 5,
    "delivered": 6,
}


class OrderIndex:
    """SQLite store for shipments linked to indexed emails."""

    def __init__(self, db_path: str = "./data/emails.db"):
        self.db_path = db_path
        self._ensure_database()

    @contextmanager
    def get_db(self):
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
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER,
                    gmail_id VARCHAR(64),
                    thread_id VARCHAR(64),
                    merchant TEXT NOT NULL DEFAULT '',
                    order_number TEXT,
                    tracking_number TEXT,
                    carrier TEXT,
                    status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    amount TEXT,
                    currency TEXT,
                    estimated_delivery TEXT,
                    tracking_url TEXT,
                    item_summary TEXT,
                    last_email_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_tracking ON shipments(tracking_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_merchant_order "
                "ON shipments(merchant, order_number)"
            )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS shipment_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER NOT NULL,
                    email_id INTEGER,
                    gmail_id VARCHAR(64),
                    subject TEXT,
                    received_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shipment_id) REFERENCES shipments(id),
                    UNIQUE(shipment_id, gmail_id)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipment_emails_shipment "
                "ON shipment_emails(shipment_id)"
            )

    @staticmethod
    def _status_rank(status: str) -> int:
        return STATUS_ORDER.get((status or "unknown").lower(), 0)

    @staticmethod
    def _merge_status(current: str, incoming: str) -> str:
        current_rank = OrderIndex._status_rank(current)
        incoming_rank = OrderIndex._status_rank(incoming)
        if incoming_rank >= current_rank:
            return (incoming or "unknown").lower()
        return (current or "unknown").lower()

    @staticmethod
    def _pick_newer_value(current: Optional[str], incoming: Optional[str]) -> Optional[str]:
        if incoming and str(incoming).strip():
            return str(incoming).strip()
        return current

    def _find_existing(
        self,
        conn: sqlite3.Connection,
        tracking_number: Optional[str],
        merchant: Optional[str],
        order_number: Optional[str],
    ) -> Optional[sqlite3.Row]:
        tracking = (tracking_number or "").strip()
        if tracking:
            row = conn.execute(
                "SELECT * FROM shipments WHERE tracking_number = ?",
                (tracking,),
            ).fetchone()
            if row:
                return row

        merchant_norm = (merchant or "").strip().lower()
        order_norm = (order_number or "").strip()
        if merchant_norm and order_norm:
            row = conn.execute(
                """
                SELECT * FROM shipments
                WHERE LOWER(merchant) = ? AND order_number = ?
                """,
                (merchant_norm, order_norm),
            ).fetchone()
            if row:
                return row
        return None

    def upsert_shipment(
        self,
        *,
        email_id: Optional[int],
        gmail_id: str,
        thread_id: str,
        merchant: str = "",
        order_number: str = "",
        tracking_number: str = "",
        carrier: str = "",
        status: str = "unknown",
        amount: str = "",
        currency: str = "",
        estimated_delivery: str = "",
        tracking_url: str = "",
        item_summary: str = "",
        received_at: Optional[str] = None,
        subject: str = "",
    ) -> int:
        """Insert or update a shipment and link the source email."""
        now = datetime.utcnow().isoformat()
        with self.get_db() as conn:
            existing = self._find_existing(conn, tracking_number, merchant, order_number)

            if existing:
                shipment_id = existing["id"]
                merged_status = self._merge_status(existing["status"], status)
                conn.execute(
                    """
                    UPDATE shipments SET
                        email_id = COALESCE(?, email_id),
                        gmail_id = COALESCE(?, gmail_id),
                        thread_id = COALESCE(?, thread_id),
                        merchant = CASE WHEN ? != '' THEN ? ELSE merchant END,
                        order_number = CASE WHEN ? != '' THEN ? ELSE order_number END,
                        tracking_number = CASE WHEN ? != '' THEN ? ELSE tracking_number END,
                        carrier = CASE WHEN ? != '' THEN ? ELSE carrier END,
                        status = ?,
                        amount = CASE WHEN ? != '' THEN ? ELSE amount END,
                        currency = CASE WHEN ? != '' THEN ? ELSE currency END,
                        estimated_delivery = CASE WHEN ? != '' THEN ? ELSE estimated_delivery END,
                        tracking_url = CASE WHEN ? != '' THEN ? ELSE tracking_url END,
                        item_summary = CASE WHEN ? != '' THEN ? ELSE item_summary END,
                        last_email_at = COALESCE(?, last_email_at),
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        email_id,
                        gmail_id or None,
                        thread_id or None,
                        merchant, merchant,
                        order_number, order_number,
                        tracking_number, tracking_number,
                        carrier, carrier,
                        merged_status,
                        amount, amount,
                        currency, currency,
                        estimated_delivery, estimated_delivery,
                        tracking_url, tracking_url,
                        item_summary, item_summary,
                        received_at or now,
                        now,
                        shipment_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO shipments (
                        email_id, gmail_id, thread_id, merchant, order_number,
                        tracking_number, carrier, status, amount, currency,
                        estimated_delivery, tracking_url, item_summary,
                        last_email_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        email_id,
                        gmail_id,
                        thread_id,
                        merchant or "",
                        order_number or None,
                        tracking_number or None,
                        carrier or None,
                        (status or "unknown").lower(),
                        amount or None,
                        currency or None,
                        estimated_delivery or None,
                        tracking_url or None,
                        item_summary or None,
                        received_at or now,
                        now,
                        now,
                    ),
                )
                shipment_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO shipment_emails (shipment_id, email_id, gmail_id, subject, received_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(shipment_id, gmail_id) DO UPDATE SET
                    subject = excluded.subject,
                    received_at = excluded.received_at
                """,
                (shipment_id, email_id, gmail_id, subject, received_at or now),
            )
            return shipment_id

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row) if row else {}

    def _attach_linked_emails(
        self, conn: sqlite3.Connection, shipment: Dict[str, Any]
    ) -> Dict[str, Any]:
        rows = conn.execute(
            """
            SELECT gmail_id, subject, received_at
            FROM shipment_emails
            WHERE shipment_id = ?
            ORDER BY received_at DESC
            """,
            (shipment["id"],),
        ).fetchall()
        shipment["linked_emails"] = [dict(r) for r in rows]
        return shipment

    def get_by_id(self, shipment_id: int) -> Optional[Dict[str, Any]]:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
            if not row:
                return None
            return self._attach_linked_emails(conn, self._row_to_dict(row))

    def list_shipments(
        self,
        *,
        status: Optional[str] = None,
        active: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM shipments WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.lower())
        if active:
            query += (
                " AND status NOT IN ('delivered') "
                "AND (tracking_number IS NOT NULL AND tracking_number != '')"
            )

        query += " ORDER BY last_email_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def list_recent_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Orders confirmed but not yet shipped (no tracking number)."""
        with self.get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM shipments
                WHERE status IN ('ordered', 'confirmed', 'unknown')
                  AND (tracking_number IS NULL OR tracking_number = '')
                ORDER BY last_email_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_summary(self) -> Dict[str, Any]:
        with self.get_db() as conn:
            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM shipments GROUP BY status"
            ):
                by_status[row["status"]] = row["count"]

            in_transit = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status IN ('shipped', 'in_transit')
                """
            ).fetchone()["c"]

            out_for_delivery = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status = 'out_for_delivery'
                """
            ).fetchone()["c"]

            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            arriving_this_week = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status NOT IN ('delivered')
                  AND estimated_delivery IS NOT NULL
                  AND estimated_delivery >= ?
                """,
                (cutoff,),
            ).fetchone()["c"]

            delivered_cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
            delivered_recent = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status = 'delivered'
                  AND last_email_at >= ?
                """,
                (delivered_cutoff,),
            ).fetchone()["c"]

            return {
                "by_status": by_status,
                "in_transit": in_transit,
                "out_for_delivery": out_for_delivery,
                "arriving_this_week": arriving_this_week,
                "delivered_recent": delivered_recent,
                "total": sum(by_status.values()),
            }
