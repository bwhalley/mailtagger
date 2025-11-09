#!/usr/bin/env python3
"""
Simple prompt management service for mailtagger.
Handles prompt storage, retrieval, and testing.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
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


if __name__ == "__main__":
    main()

