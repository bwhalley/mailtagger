#!/usr/bin/env python3
"""
Simple prompt management service for mailtagger.
Handles prompt storage, retrieval, and testing.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager


class PromptService:
    """Simple service for managing email classification prompts."""
    
    def __init__(self, db_path: str = "./data/prompts.db"):
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
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id INTEGER,
                    test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email_subject TEXT,
                    email_from TEXT,
                    predicted_category VARCHAR(50),
                    confidence FLOAT,
                    reason TEXT,
                    processing_time FLOAT,
                    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    category VARCHAR(50),
                    confidence FLOAT,
                    processing_time FLOAT,
                    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sender_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern VARCHAR(255) NOT NULL,
                    priority VARCHAR(20) DEFAULT 'medium',
                    label VARCHAR(100),
                    rule_type VARCHAR(20) NOT NULL DEFAULT 'allowlist',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS priority_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category VARCHAR(100) NOT NULL UNIQUE,
                    default_priority VARCHAR(20) DEFAULT 'medium',
                    is_high_value BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default priority config for known categories
            cursor = conn.execute("SELECT COUNT(*) as count FROM priority_config")
            if cursor.fetchone()["count"] == 0:
                defaults = [
                    ("receipts", "high", True),
                    ("transactions", "high", True),
                    ("personal", "high", True),
                    ("critical", "high", True),
                    ("political", "low", False),
                    ("news", "low", False),
                    ("marketing", "low", False),
                    ("ecommerce", "low", False),
                    ("blocklist", "low", False),
                ]
                conn.executemany(
                    "INSERT INTO priority_config (category, default_priority, is_high_value) VALUES (?, ?, ?)",
                    defaults,
                )

            # Create default prompt if none exists
            cursor = conn.execute("SELECT COUNT(*) as count FROM prompts")
            if cursor.fetchone()["count"] == 0:
                self._create_default_prompt(conn)
    
    def _create_default_prompt(self, conn):
        """Create the default prompt from hardcoded PROMPT_RULES."""
        default_prompt = """You are a strict email classifier. Classify an email into exactly ONE of two buckets:
1) 'ecommerce' – marketing or campaign emails from stores/brands about sales, product launches, coupons, promotions, newsletters from retailers.
   Include brand newsletters, 'shop now', seasonal sales, product announcements, abandoned cart promos, discount codes.
   Exclude order receipts or shipping notifications if purely transactional.
2) 'political' – messages from campaigns, candidates, PACs, NGOs/activist orgs soliciting donations, petitions, or political actions. Look for cues like ActBlue/WinRed links, 'chip in', 'end-of-quarter', 'paid for by', election/candidate names.
If neither fits, choose 'ecommerce' ONLY if it's clearly a store/brand campaign; otherwise return 'none'.
IMPORTANT: Respond with ONLY valid JSON. No additional text, no explanations outside the JSON.
Format: {"category": "ecommerce|political|none", "reason": "short explanation", "confidence": 0.9}
Be conservative and only pick 'political' if clearly political."""
        
        conn.execute(
            "INSERT INTO prompts (name, content, is_active) VALUES (?, ?, ?)",
            ("Default Classifier", default_prompt, True)
        )
    
    def get_active_prompt(self) -> Optional[Dict[str, Any]]:
        """Get the currently active prompt."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM prompts WHERE is_active = 1 LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def update_prompt(self, name: str, content: str) -> Dict[str, Any]:
        """Update the active prompt (or create if none exists)."""
        with self.get_db() as conn:
            # Deactivate all prompts
            conn.execute("UPDATE prompts SET is_active = 0")
            
            # Check if a prompt with this name exists
            cursor = conn.execute(
                "SELECT id FROM prompts WHERE name = ?", (name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                conn.execute(
                    """UPDATE prompts 
                       SET content = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (content, existing["id"])
                )
                prompt_id = existing["id"]
            else:
                # Create new
                cursor = conn.execute(
                    "INSERT INTO prompts (name, content, is_active) VALUES (?, ?, 1)",
                    (name, content)
                )
                prompt_id = cursor.lastrowid
            
            return self.get_prompt_by_id(prompt_id)
    
    def get_prompt_by_id(self, prompt_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific prompt by ID."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def save_test_result(
        self,
        prompt_id: int,
        email_subject: str,
        email_from: str,
        category: str,
        confidence: float,
        reason: str,
        processing_time: float
    ) -> int:
        """Save a test result."""
        with self.get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO test_results 
                   (prompt_id, email_subject, email_from, predicted_category, 
                    confidence, reason, processing_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (prompt_id, email_subject, email_from, category, confidence, 
                 reason, processing_time)
            )
            return cursor.lastrowid
    
    def get_recent_test_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent test results."""
        with self.get_db() as conn:
            cursor = conn.execute(
                """SELECT * FROM test_results 
                   ORDER BY test_date DESC LIMIT ?""",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def log_classification(
        self,
        prompt_id: int,
        category: str,
        confidence: float,
        processing_time: float
    ):
        """Log a production classification."""
        with self.get_db() as conn:
            conn.execute(
                """INSERT INTO classification_logs 
                   (prompt_id, category, confidence, processing_time)
                   VALUES (?, ?, ?, ?)""",
                (prompt_id, category, confidence, processing_time)
            )
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get classification statistics for the last N days."""
        with self.get_db() as conn:
            # Get active prompt
            active = self.get_active_prompt()
            if not active:
                return {"error": "No active prompt"}
            
            # Get counts by category
            cursor = conn.execute(
                """SELECT category, COUNT(*) as count, AVG(confidence) as avg_conf
                   FROM classification_logs
                   WHERE prompt_id = ?
                   AND timestamp >= datetime('now', '-' || ? || ' days')
                   GROUP BY category""",
                (active["id"], days)
            )
            
            categories = {}
            total = 0
            for row in cursor:
                cat = row["category"]
                count = row["count"]
                categories[cat] = {
                    "count": count,
                    "avg_confidence": round(row["avg_conf"], 3) if row["avg_conf"] else 0
                }
                total += count
            
            # Get overall stats
            cursor = conn.execute(
                """SELECT 
                     AVG(confidence) as avg_conf,
                     AVG(processing_time) as avg_time
                   FROM classification_logs
                   WHERE prompt_id = ?
                   AND timestamp >= datetime('now', '-' || ? || ' days')""",
                (active["id"], days)
            )
            
            overall = cursor.fetchone()
            
            return {
                "prompt_id": active["id"],
                "prompt_name": active["name"],
                "days": days,
                "total_classifications": total,
                "categories": categories,
                "avg_confidence": round(overall["avg_conf"], 3) if overall["avg_conf"] else 0,
                "avg_processing_time": round(overall["avg_time"], 3) if overall["avg_time"] else 0
            }
    
    def clear_old_logs(self, days: int = 30):
        """Clear classification logs older than N days."""
        with self.get_db() as conn:
            conn.execute(
                """DELETE FROM classification_logs 
                   WHERE timestamp < datetime('now', '-' || ? || ' days')""",
                (days,)
            )
            
            conn.execute(
                """DELETE FROM test_results 
                   WHERE test_date < datetime('now', '-' || ? || ' days')""",
                (days,)
            )

    # ---- Sender rules ----

    def get_sender_rules(self) -> List[Dict[str, Any]]:
        """Get all sender rules."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM sender_rules ORDER BY rule_type, pattern"
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_sender_rule(
        self,
        pattern: str,
        priority: str = "medium",
        label: Optional[str] = None,
        rule_type: str = "allowlist",
    ) -> int:
        """Add a sender rule (allowlist or blocklist)."""
        with self.get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO sender_rules (pattern, priority, label, rule_type)
                   VALUES (?, ?, ?, ?)""",
                (pattern, priority, label, rule_type),
            )
            return cursor.lastrowid

    def delete_sender_rule(self, rule_id: int):
        """Delete a sender rule."""
        with self.get_db() as conn:
            conn.execute("DELETE FROM sender_rules WHERE id = ?", (rule_id,))

    def get_priority_for_sender(self, sender: str) -> Optional[Tuple[str, str]]:
        """
        Check sender against rules. Returns (priority, rule_type) if matched.
        allowlist = high-value sender; blocklist = low-value.
        """
        sender_lower = sender.lower()
        with self.get_db() as conn:
            for row in conn.execute("SELECT * FROM sender_rules ORDER BY id"):
                pattern = row["pattern"].lower()
                if pattern in sender_lower or pattern in sender_lower.split("@")[0]:
                    if row["rule_type"] == "allowlist":
                        return (row["priority"] or "high", "allowlist")
                    return (row["priority"] or "low", "blocklist")
        return None

    # ---- Priority config ----

    def get_priority_config(self) -> List[Dict[str, Any]]:
        """Get all category priority config."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM priority_config ORDER BY is_high_value DESC, category"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_priority_for_category(self, category: str) -> str:
        """Get default priority for a category."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT default_priority FROM priority_config WHERE category = ?",
                (category.lower(),),
            )
            row = cursor.fetchone()
            return row["default_priority"] if row else "medium"

    def update_priority_config(
        self,
        category: str,
        default_priority: str,
        is_high_value: bool = False,
    ):
        """Insert or update priority for a category."""
        with self.get_db() as conn:
            conn.execute(
                """INSERT INTO priority_config (category, default_priority, is_high_value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(category) DO UPDATE SET
                       default_priority = excluded.default_priority,
                       is_high_value = excluded.is_high_value""",
                (category.lower(), default_priority, is_high_value),
            )


class ExampleStore:
    """Store and retrieve few-shot examples for DSPy optimization.
    
    This class manages a collection of high-quality classification examples
    that can be used for few-shot learning and prompt optimization.
    """
    
    def __init__(self, db_path: str = "./data/prompts.db"):
        self.db_path = db_path
        self._ensure_examples_table()
    
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
    
    def _ensure_examples_table(self):
        """Create few_shot_examples table if it doesn't exist."""
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS few_shot_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id VARCHAR(255),
                    sender VARCHAR(255) NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT,
                    category VARCHAR(50) NOT NULL,
                    confidence FLOAT DEFAULT 1.0,
                    verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    use_count INTEGER DEFAULT 0,
                    notes TEXT
                )
            """)
            
            # Create indices for faster retrieval
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category 
                ON few_shot_examples(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified 
                ON few_shot_examples(verified)
            """)
    
    def add_example(
        self,
        sender: str,
        subject: str,
        body: str,
        category: str,
        confidence: float = 1.0,
        verified: bool = False,
        email_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Add a classification example to the store.
        
        Args:
            sender: Email sender address
            subject: Email subject line
            body: Email body text
            category: Category ('ecommerce', 'political', 'none')
            confidence: Confidence score (0.0-1.0)
            verified: If True, this is a human-verified example
            email_id: Gmail email ID (optional)
            notes: Additional notes (optional)
            
        Returns:
            ID of the inserted example
        """
        with self.get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO few_shot_examples 
                   (email_id, sender, subject, body, category, confidence, verified, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (email_id, sender, subject, body, category, confidence, verified, notes)
            )
            return cursor.lastrowid
    
    def get_example(self, example_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific example by ID.
        
        Args:
            example_id: Example ID
            
        Returns:
            Example dict or None if not found
        """
        with self.get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM few_shot_examples WHERE id = ?",
                (example_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_best_examples(
        self,
        category: Optional[str] = None,
        k: int = 5,
        verified_only: bool = True,
        min_confidence: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Retrieve best examples for few-shot prompting.
        
        Selection strategy:
        1. Prioritize verified examples
        2. Filter by confidence threshold
        3. Balance across categories (if category not specified)
        4. Prefer less-frequently-used examples (to avoid overfitting)
        
        Args:
            category: If specified, only return examples from this category
            k: Number of examples to return
            verified_only: If True, only return human-verified examples
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of example dicts
        """
        with self.get_db() as conn:
            conditions = ["confidence >= ?"]
            params = [min_confidence]
            
            if verified_only:
                conditions.append("verified = 1")
            
            if category:
                conditions.append("category = ?")
                params.append(category)
            
            where_clause = " AND ".join(conditions)
            
            # Order by: verified first, then by use_count (ascending) to balance usage
            query = f"""
                SELECT * FROM few_shot_examples
                WHERE {where_clause}
                ORDER BY verified DESC, use_count ASC, confidence DESC
                LIMIT ?
            """
            params.append(k)
            
            cursor = conn.execute(query, params)
            examples = [dict(row) for row in cursor.fetchall()]
            
            # Update use counts
            if examples:
                example_ids = [ex['id'] for ex in examples]
                placeholders = ','.join('?' * len(example_ids))
                conn.execute(
                    f"""UPDATE few_shot_examples 
                        SET use_count = use_count + 1, 
                            last_used_at = CURRENT_TIMESTAMP
                        WHERE id IN ({placeholders})""",
                    example_ids
                )
            
            return examples
    
    def get_stratified_examples(
        self,
        k_per_category: int = 2,
        verified_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get balanced examples across all categories.
        
        Args:
            k_per_category: Number of examples per category
            verified_only: If True, only return verified examples
            
        Returns:
            List of examples with balanced representation
        """
        categories = ['ecommerce', 'political', 'none']
        all_examples = []
        
        for category in categories:
            examples = self.get_best_examples(
                category=category,
                k=k_per_category,
                verified_only=verified_only
            )
            all_examples.extend(examples)
        
        return all_examples
    
    def mark_verified(self, example_id: int, verified: bool = True):
        """Mark an example as verified (or unverified).
        
        Args:
            example_id: Example ID
            verified: Verification status
        """
        with self.get_db() as conn:
            conn.execute(
                "UPDATE few_shot_examples SET verified = ? WHERE id = ?",
                (verified, example_id)
            )
    
    def delete_example(self, example_id: int):
        """Delete an example from the store.
        
        Args:
            example_id: Example ID
        """
        with self.get_db() as conn:
            conn.execute(
                "DELETE FROM few_shot_examples WHERE id = ?",
                (example_id,)
            )
    
    def get_all_examples(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all examples (for UI display).
        
        Args:
            limit: Maximum number of examples
            offset: Offset for pagination
            
        Returns:
            List of example dicts
        """
        with self.get_db() as conn:
            query = """
                SELECT * FROM few_shot_examples
                ORDER BY created_at DESC
            """
            
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the example store.
        
        Returns:
            Dict with statistics
        """
        with self.get_db() as conn:
            # Total examples
            total = conn.execute(
                "SELECT COUNT(*) as count FROM few_shot_examples"
            ).fetchone()['count']
            
            # Verified examples
            verified = conn.execute(
                "SELECT COUNT(*) as count FROM few_shot_examples WHERE verified = 1"
            ).fetchone()['count']
            
            # By category
            by_category = {}
            cursor = conn.execute("""
                SELECT category, COUNT(*) as count, AVG(confidence) as avg_conf
                FROM few_shot_examples
                GROUP BY category
            """)
            for row in cursor:
                by_category[row['category']] = {
                    'count': row['count'],
                    'avg_confidence': round(row['avg_conf'], 3) if row['avg_conf'] else 0
                }
            
            return {
                'total_examples': total,
                'verified_examples': verified,
                'by_category': by_category
            }


def main():
    """Test the prompt service."""
    service = PromptService("./data/prompts.db")
    
    # Get active prompt
    prompt = service.get_active_prompt()
    print(f"Active prompt: {prompt['name']}")
    print(f"Content length: {len(prompt['content'])} chars")
    
    # Get stats
    stats = service.get_statistics()
    print(f"\nStatistics: {json.dumps(stats, indent=2)}")
    
    # Test ExampleStore
    print("\n--- Testing ExampleStore ---")
    example_store = ExampleStore("./data/prompts.db")
    
    # Add a test example
    example_id = example_store.add_example(
        sender="test@example.com",
        subject="Test ecommerce email",
        body="Shop our amazing sale! 50% off everything!",
        category="ecommerce",
        confidence=0.95,
        verified=True,
        notes="Test example"
    )
    print(f"Added example ID: {example_id}")
    
    # Get statistics
    ex_stats = example_store.get_statistics()
    print(f"Example store stats: {json.dumps(ex_stats, indent=2)}")
    
    # Clean up test example
    example_store.delete_example(example_id)
    print("Cleaned up test example")


if __name__ == "__main__":
    main()

