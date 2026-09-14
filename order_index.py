#!/usr/bin/env python3
"""
Persistent Order and Shipment index for commerce tracking dashboard.

Orders: identified by (brand_domain, order_number)
Shipments: identified by tracking_number (dedupes brand + carrier emails)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

ORDER_STATUS_RANK = {
    "unknown": 0,
    "ordered": 1,
    "confirmed": 2,
    "cancelled": 99,
}

SHIPMENT_STATUS_RANK = {
    "unknown": 0,
    "shipped": 1,
    "in_transit": 2,
    "out_for_delivery": 3,
    "delivered": 4,
}


class OrderIndex:
    """SQLite store for orders and shipments linked to indexed emails."""

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

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def _ensure_database(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_number TEXT NOT NULL,
                    brand_domain TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    first_email_at TIMESTAMP,
                    last_email_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(brand_domain, order_number)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_brand ON orders(brand_domain)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
            )

            self._migrate_legacy_schema(conn)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_number TEXT NOT NULL UNIQUE,
                    carrier TEXT,
                    status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                    source_type VARCHAR(16) NOT NULL DEFAULT 'brand',
                    brand_domain TEXT,
                    order_id INTEGER,
                    estimated_delivery TEXT,
                    tracking_url TEXT,
                    last_notification_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            shipment_cols = self._table_columns(conn, "shipments")
            if "order_id" in shipment_cols:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id)"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status)"
            )
            if "brand_domain" in shipment_cols:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_shipments_brand ON shipments(brand_domain)"
                )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS order_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    email_id INTEGER,
                    gmail_id VARCHAR(64),
                    subject TEXT,
                    received_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    UNIQUE(order_id, gmail_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shipment_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shipment_id INTEGER NOT NULL,
                    email_id INTEGER,
                    gmail_id VARCHAR(64),
                    subject TEXT,
                    received_at TIMESTAMP,
                    source_type VARCHAR(16) NOT NULL DEFAULT 'brand',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (shipment_id) REFERENCES shipments(id),
                    UNIQUE(shipment_id, gmail_id)
                )
            """)

    def _migrate_legacy_schema(self, conn: sqlite3.Connection):
        """Migrate monolithic shipments table to orders + shipments split."""
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "shipments_legacy" in tables or "shipments" not in tables:
            return

        cols = self._table_columns(conn, "shipments")
        if "merchant" not in cols or "brand_domain" in cols:
            return

        conn.execute("ALTER TABLE shipments RENAME TO shipments_legacy")
        conn.execute("""
            CREATE TABLE shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT NOT NULL UNIQUE,
                carrier TEXT,
                status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                source_type VARCHAR(16) NOT NULL DEFAULT 'brand',
                brand_domain TEXT,
                order_id INTEGER,
                estimated_delivery TEXT,
                tracking_url TEXT,
                last_notification_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status)"
        )

        legacy_rows = conn.execute("SELECT * FROM shipments_legacy").fetchall()
        order_id_by_key: Dict[Tuple[str, str], int] = {}

        for row in legacy_rows:
            legacy = dict(row)
            tracking = (legacy.get("tracking_number") or "").strip()
            order_num = (legacy.get("order_number") or "").strip()
            merchant = (legacy.get("merchant") or "").strip().lower()
            brand_domain = merchant if "." in merchant else merchant
            if not brand_domain and legacy.get("email_id"):
                email_row = conn.execute(
                    "SELECT sender_domain, domain_key FROM emails WHERE id = ?",
                    (legacy["email_id"],),
                ).fetchone()
                if email_row:
                    brand_domain = email_row["domain_key"] or email_row["sender_domain"] or ""

            status = (legacy.get("status") or "unknown").lower()
            received = legacy.get("last_email_at")
            order_id = None

            if order_num and brand_domain:
                key = (brand_domain.lower(), order_num.upper())
                if key not in order_id_by_key:
                    order_status = status
                    if status in SHIPMENT_STATUS_RANK:
                        order_status = "confirmed"
                    cursor = conn.execute(
                        """
                        INSERT INTO orders (
                            order_number, brand_domain, status,
                            first_email_at, last_email_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            order_num.upper(),
                            brand_domain.lower(),
                            order_status,
                            received,
                            received,
                            legacy.get("created_at"),
                            legacy.get("updated_at"),
                        ),
                    )
                    order_id_by_key[key] = cursor.lastrowid
                order_id = order_id_by_key[key]

            shipment_id = None
            if tracking:
                ship_status = status
                if status in ORDER_STATUS_RANK and status not in SHIPMENT_STATUS_RANK:
                    ship_status = "shipped"
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO shipments (
                        tracking_number, carrier, status, source_type, brand_domain,
                        order_id, estimated_delivery, tracking_url,
                        last_notification_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tracking.upper(),
                        legacy.get("carrier"),
                        ship_status,
                        "brand",
                        brand_domain.lower() if brand_domain else None,
                        order_id,
                        legacy.get("estimated_delivery"),
                        legacy.get("tracking_url"),
                        received,
                        legacy.get("created_at"),
                        legacy.get("updated_at"),
                    ),
                )
                if cursor.lastrowid:
                    shipment_id = cursor.lastrowid
                else:
                    shipment_id = conn.execute(
                        "SELECT id FROM shipments WHERE tracking_number = ?",
                        (tracking.upper(),),
                    ).fetchone()["id"]

            if order_id and legacy.get("gmail_id"):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO order_emails
                    (order_id, email_id, gmail_id, subject, received_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        legacy.get("email_id"),
                        legacy.get("gmail_id"),
                        "",
                        received,
                    ),
                )

            if shipment_id and legacy.get("gmail_id"):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO shipment_notifications
                    (shipment_id, email_id, gmail_id, subject, received_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        shipment_id,
                        legacy.get("email_id"),
                        legacy.get("gmail_id"),
                        "",
                        received,
                        "brand",
                    ),
                )

        if "shipment_emails" in tables:
            for row in conn.execute("SELECT * FROM shipment_emails").fetchall():
                note = dict(row)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO shipment_notifications
                    (shipment_id, email_id, gmail_id, subject, received_at, source_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        note["shipment_id"],
                        note.get("email_id"),
                        note.get("gmail_id"),
                        note.get("subject"),
                        note.get("received_at"),
                        "brand",
                    ),
                )

    @staticmethod
    def _merge_order_status(current: str, incoming: str) -> str:
        cur = (current or "unknown").lower()
        inc = (incoming or "unknown").lower()
        if inc == "cancelled":
            return "cancelled"
        if cur == "cancelled":
            return "cancelled"
        if ORDER_STATUS_RANK.get(inc, 0) >= ORDER_STATUS_RANK.get(cur, 0):
            return inc
        return cur

    @staticmethod
    def _merge_shipment_status(current: str, incoming: str) -> str:
        cur = (current or "unknown").lower()
        inc = (incoming or "unknown").lower()
        if SHIPMENT_STATUS_RANK.get(inc, 0) >= SHIPMENT_STATUS_RANK.get(cur, 0):
            return inc
        return cur

    def upsert_order(
        self,
        *,
        order_number: str,
        brand_domain: str,
        status: str = "unknown",
        email_id: Optional[int] = None,
        gmail_id: str = "",
        subject: str = "",
        received_at: Optional[str] = None,
    ) -> Optional[int]:
        order_number = (order_number or "").strip().upper()
        brand_domain = (brand_domain or "").strip().lower()
        if not order_number or not brand_domain:
            return None

        now = datetime.utcnow().isoformat()
        ts = received_at or now

        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE brand_domain = ? AND order_number = ?",
                (brand_domain, order_number),
            ).fetchone()

            if row:
                order_id = row["id"]
                merged = self._merge_order_status(row["status"], status)
                conn.execute(
                    """
                    UPDATE orders SET
                        status = ?,
                        last_email_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (merged, ts, now, order_id),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO orders (
                        order_number, brand_domain, status,
                        first_email_at, last_email_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (order_number, brand_domain, (status or "unknown").lower(), ts, ts, now, now),
                )
                order_id = cursor.lastrowid

            if gmail_id:
                conn.execute(
                    """
                    INSERT INTO order_emails (order_id, email_id, gmail_id, subject, received_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(order_id, gmail_id) DO UPDATE SET
                        subject = excluded.subject,
                        received_at = excluded.received_at
                    """,
                    (order_id, email_id, gmail_id, subject, ts),
                )
            return order_id

    def upsert_shipment(
        self,
        *,
        tracking_number: str,
        carrier: str = "",
        status: str = "unknown",
        source_type: str = "brand",
        brand_domain: Optional[str] = None,
        order_id: Optional[int] = None,
        estimated_delivery: str = "",
        tracking_url: str = "",
        email_id: Optional[int] = None,
        gmail_id: str = "",
        subject: str = "",
        received_at: Optional[str] = None,
    ) -> Optional[int]:
        tracking_number = (tracking_number or "").strip().upper()
        if not tracking_number:
            return None

        brand_domain_norm = (brand_domain or "").strip().lower() or None
        now = datetime.utcnow().isoformat()
        ts = received_at or now

        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM shipments WHERE tracking_number = ?",
                (tracking_number,),
            ).fetchone()

            if row:
                shipment_id = row["id"]
                merged_status = self._merge_shipment_status(row["status"], status)
                resolved_order_id = order_id or row["order_id"]
                resolved_brand = brand_domain_norm or row["brand_domain"]
                resolved_carrier = carrier or row["carrier"]
                resolved_eta = estimated_delivery or row["estimated_delivery"]
                resolved_url = tracking_url or row["tracking_url"]
                resolved_source = source_type if source_type == "carrier" else row["source_type"]

                conn.execute(
                    """
                    UPDATE shipments SET
                        carrier = ?,
                        status = ?,
                        source_type = ?,
                        brand_domain = ?,
                        order_id = ?,
                        estimated_delivery = ?,
                        tracking_url = ?,
                        last_notification_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        resolved_carrier,
                        merged_status,
                        resolved_source,
                        resolved_brand,
                        resolved_order_id,
                        resolved_eta,
                        resolved_url,
                        ts,
                        now,
                        shipment_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO shipments (
                        tracking_number, carrier, status, source_type, brand_domain,
                        order_id, estimated_delivery, tracking_url,
                        last_notification_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tracking_number,
                        carrier or None,
                        (status or "unknown").lower(),
                        source_type or "brand",
                        brand_domain_norm,
                        order_id,
                        estimated_delivery or None,
                        tracking_url or None,
                        ts,
                        now,
                        now,
                    ),
                )
                shipment_id = cursor.lastrowid

            if gmail_id:
                conn.execute(
                    """
                    INSERT INTO shipment_notifications (
                        shipment_id, email_id, gmail_id, subject, received_at, source_type
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(shipment_id, gmail_id) DO UPDATE SET
                        subject = excluded.subject,
                        received_at = excluded.received_at,
                        source_type = excluded.source_type
                    """,
                    (shipment_id, email_id, gmail_id, subject, ts, source_type or "brand"),
                )
            return shipment_id

    def persist_commerce(
        self,
        *,
        email_id: Optional[int],
        gmail_id: str,
        thread_id: str,
        sender: str,
        subject: str,
        received_at: Optional[str],
        category: str,
        carrier_match,
        extracted: Dict[str, Any],
        brand_domain: str,
        is_carrier_sender: bool,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Persist order and/or shipment from extracted email data."""
        order_id = None
        shipment_id = None

        order_number = extracted.get("order_number", "")
        tracking_number = extracted.get("tracking_number", "")
        order_status = extracted.get("order_status", "unknown")
        shipment_status = extracted.get("shipment_status", "unknown")
        carrier = extracted.get("carrier", "") or (carrier_match.carrier_name if carrier_match else "")
        source_type = "carrier" if is_carrier_sender else "brand"
        shipment_brand = None if is_carrier_sender else (brand_domain or None)

        if order_number and brand_domain and not is_carrier_sender:
            order_id = self.upsert_order(
                order_number=order_number,
                brand_domain=brand_domain,
                status=order_status,
                email_id=email_id,
                gmail_id=gmail_id,
                subject=subject,
                received_at=received_at,
            )

        if tracking_number:
            shipment_id = self.upsert_shipment(
                tracking_number=tracking_number,
                carrier=carrier,
                status=shipment_status,
                source_type=source_type,
                brand_domain=shipment_brand,
                order_id=order_id,
                estimated_delivery=extracted.get("estimated_delivery", ""),
                tracking_url=extracted.get("tracking_url", ""),
                email_id=email_id,
                gmail_id=gmail_id,
                subject=subject,
                received_at=received_at,
            )
        elif category in ("receipt", "order") and order_number and brand_domain:
            pass

        return order_id, shipment_id

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row) if row else {}

    def _has_emails_table(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='emails'"
        ).fetchone()
        return row is not None

    def _fetch_order_emails(self, conn: sqlite3.Connection, order_id: int) -> List[Dict[str, Any]]:
        if self._has_emails_table(conn):
            query = """
                SELECT oe.gmail_id, oe.subject, oe.received_at,
                       COALESCE(e.snippet, '') AS snippet
                FROM order_emails oe
                LEFT JOIN emails e ON e.id = oe.email_id
                    OR (oe.email_id IS NULL AND e.gmail_id = oe.gmail_id)
                WHERE oe.order_id = ?
                ORDER BY oe.received_at DESC
            """
        else:
            query = """
                SELECT gmail_id, subject, received_at, '' AS snippet
                FROM order_emails
                WHERE order_id = ?
                ORDER BY received_at DESC
            """
        return [dict(r) for r in conn.execute(query, (order_id,)).fetchall()]

    def _fetch_shipment_notifications(
        self, conn: sqlite3.Connection, shipment_id: int
    ) -> List[Dict[str, Any]]:
        if self._has_emails_table(conn):
            query = """
                SELECT sn.gmail_id, sn.subject, sn.received_at, sn.source_type,
                       COALESCE(e.snippet, '') AS snippet
                FROM shipment_notifications sn
                LEFT JOIN emails e ON e.id = sn.email_id
                    OR (sn.email_id IS NULL AND e.gmail_id = sn.gmail_id)
                WHERE sn.shipment_id = ?
                ORDER BY sn.received_at DESC
            """
        else:
            query = """
                SELECT gmail_id, subject, received_at, source_type, '' AS snippet
                FROM shipment_notifications
                WHERE shipment_id = ?
                ORDER BY received_at DESC
            """
        return [dict(r) for r in conn.execute(query, (shipment_id,)).fetchall()]

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                return None
            order = self._row_to_dict(row)
            order["linked_emails"] = self._fetch_order_emails(conn, order_id)
            order["shipments"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM shipments WHERE order_id = ? ORDER BY last_notification_at DESC",
                    (order_id,),
                ).fetchall()
            ]
            return order

    def get_shipment_by_id(self, shipment_id: int) -> Optional[Dict[str, Any]]:
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
            if not row:
                return None
            shipment = self._row_to_dict(row)
            shipment["notifications"] = self._fetch_shipment_notifications(conn, shipment_id)
            if shipment.get("order_id"):
                order_row = conn.execute(
                    "SELECT order_number, brand_domain, status FROM orders WHERE id = ?",
                    (shipment["order_id"],),
                ).fetchone()
                if order_row:
                    shipment["order_number"] = order_row["order_number"]
                    shipment["order_brand_domain"] = order_row["brand_domain"]
            return shipment

    def list_orders(
        self,
        *,
        status: Optional[str] = None,
        brand_domain: Optional[str] = None,
        without_shipment: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT o.* FROM orders o WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND o.status = ?"
            params.append(status.lower())
        if brand_domain:
            query += " AND o.brand_domain = ?"
            params.append(brand_domain.lower())
        if without_shipment:
            query += """
                AND NOT EXISTS (
                    SELECT 1 FROM shipments s WHERE s.order_id = o.id
                )
            """
        query += " ORDER BY o.last_email_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.get_db() as conn:
            return [self._row_to_dict(r) for r in conn.execute(query, params).fetchall()]

    def list_shipments(
        self,
        *,
        status: Optional[str] = None,
        active: bool = False,
        brand_domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM shipments WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.lower())
        if active:
            query += " AND status NOT IN ('delivered')"
        if brand_domain:
            query += " AND brand_domain = ?"
            params.append(brand_domain.lower())
        query += " ORDER BY last_notification_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.get_db() as conn:
            return [self._row_to_dict(r) for r in conn.execute(query, params).fetchall()]

    def get_commerce_summary(self) -> Dict[str, Any]:
        with self.get_db() as conn:
            orders_total = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
            orders_open = conn.execute(
                """
                SELECT COUNT(*) as c FROM orders o
                WHERE o.status IN ('ordered', 'confirmed', 'unknown')
                  AND NOT EXISTS (SELECT 1 FROM shipments s WHERE s.order_id = o.id)
                """
            ).fetchone()["c"]

            by_shipment_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as count FROM shipments GROUP BY status"
            ):
                by_shipment_status[row["status"]] = row["count"]

            in_transit = conn.execute(
                "SELECT COUNT(*) as c FROM shipments WHERE status IN ('shipped', 'in_transit')"
            ).fetchone()["c"]
            out_for_delivery = conn.execute(
                "SELECT COUNT(*) as c FROM shipments WHERE status = 'out_for_delivery'"
            ).fetchone()["c"]

            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            arriving_this_week = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status NOT IN ('delivered')
                  AND estimated_delivery IS NOT NULL AND estimated_delivery >= ?
                """,
                (cutoff,),
            ).fetchone()["c"]

            delivered_cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
            delivered_recent = conn.execute(
                """
                SELECT COUNT(*) as c FROM shipments
                WHERE status = 'delivered' AND last_notification_at >= ?
                """,
                (delivered_cutoff,),
            ).fetchone()["c"]

            return {
                "orders_total": orders_total,
                "orders_open": orders_open,
                "shipments_total": sum(by_shipment_status.values()),
                "by_shipment_status": by_shipment_status,
                "in_transit": in_transit,
                "out_for_delivery": out_for_delivery,
                "arriving_this_week": arriving_this_week,
                "delivered_recent": delivered_recent,
                # backward compat
                "by_status": by_shipment_status,
                "total": sum(by_shipment_status.values()),
            }

    # Backward-compatible aliases
    def get_summary(self) -> Dict[str, Any]:
        return self.get_commerce_summary()

    def get_by_id(self, shipment_id: int) -> Optional[Dict[str, Any]]:
        return self.get_shipment_by_id(shipment_id)

    def list_recent_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.list_orders(without_shipment=True, limit=limit)
