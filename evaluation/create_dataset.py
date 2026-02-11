#!/usr/bin/env python3
"""
Create evaluation datasets from historical classification logs.

This module extracts email classification data from the prompts database
and formats it for DSPy evaluation and optimization.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Example:
    """DSPy-compatible example for evaluation and training.
    
    Attributes:
        sender: Email sender address
        subject: Email subject line
        body: Email body text (truncated)
        category: Gold-standard category ('ecommerce', 'political', 'none')
        metadata: Additional metadata (confidence, timestamp, etc.)
    """
    
    def __init__(self, sender: str, subject: str, body: str, category: str, **metadata):
        self.sender = sender
        self.subject = subject
        self.body = body
        self.category = category
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "category": self.category,
            **self.metadata
        }
    
    def __repr__(self):
        return f"Example(category={self.category}, subject={self.subject[:50]}...)"


def load_test_results(
    db_path: str = "./data/prompts.db",
    min_confidence: float = 0.7,
    limit: Optional[int] = None
) -> List[Example]:
    """Load test results from the database as examples.
    
    Test results are classifications that were manually verified through
    the web UI testing interface.
    
    Args:
        db_path: Path to prompts database
        min_confidence: Minimum confidence threshold for inclusion
        limit: Maximum number of examples to load (None = all)
        
    Returns:
        List of Example objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = """
        SELECT 
            email_from as sender,
            email_subject as subject,
            predicted_category as category,
            confidence,
            reason,
            processing_time,
            test_date
        FROM test_results
        WHERE confidence >= ?
        ORDER BY test_date DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor = conn.execute(query, (min_confidence,))
    rows = cursor.fetchall()
    conn.close()
    
    examples = []
    for row in rows:
        # Note: We don't have full email body in test_results
        # This is a limitation - we'd need to store more data for full evaluation
        example = Example(
            sender=row['sender'],
            subject=row['subject'],
            body="",  # Not stored in test_results
            category=row['category'],
            confidence=row['confidence'],
            reason=row['reason'],
            processing_time=row['processing_time'],
            timestamp=row['test_date']
        )
        examples.append(example)
    
    logger.info(f"Loaded {len(examples)} test results from {db_path}")
    return examples


def load_classification_logs(
    db_path: str = "./data/prompts.db",
    days: int = 30,
    min_confidence: float = 0.8,
    limit: Optional[int] = None,
    balanced: bool = True
) -> List[Example]:
    """Load classification logs as examples.
    
    Classification logs are production classifications. We use high-confidence
    classifications as pseudo-labels for training.
    
    Args:
        db_path: Path to prompts database
        days: Number of days of history to load
        min_confidence: Minimum confidence threshold for inclusion
        limit: Maximum number of examples to load (None = all)
        balanced: If True, balance examples across categories
        
    Returns:
        List of Example objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    query = """
        SELECT 
            category,
            confidence,
            processing_time,
            timestamp
        FROM classification_logs
        WHERE timestamp >= ?
          AND confidence >= ?
        ORDER BY timestamp DESC
    """
    
    cursor = conn.execute(query, (cutoff_date, min_confidence))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        logger.warning(f"No classification logs found in {db_path}")
        return []
    
    # Note: classification_logs doesn't store email content
    # We can only use this for statistics, not actual training
    logger.info(f"Found {len(rows)} high-confidence classifications")
    
    # Group by category for balancing
    by_category = {'ecommerce': [], 'political': [], 'none': []}
    for row in rows:
        cat = row['category']
        if cat in by_category:
            by_category[cat].append(row)
    
    logger.info(f"Distribution: ecommerce={len(by_category['ecommerce'])}, "
               f"political={len(by_category['political'])}, "
               f"none={len(by_category['none'])}")
    
    # For now, return empty since we don't have email content
    # In a real implementation, we'd need to store email_id and join with Gmail API
    return []


def create_synthetic_examples() -> List[Example]:
    """Create synthetic examples for initial testing.
    
    These are hand-crafted examples that represent common email patterns.
    Useful for initial development and testing before real data is available.
    
    Returns:
        List of synthetic Example objects
    """
    examples = [
        # Ecommerce examples
        Example(
            sender="deals@amazon.com",
            subject="⚡ Flash Sale: 50% Off Electronics Today Only!",
            body="Don't miss out on our biggest electronics sale of the year! Shop now and save up to 50% on laptops, tablets, and smart home devices. Sale ends tonight at midnight!",
            category="ecommerce",
            source="synthetic"
        ),
        Example(
            sender="newsletter@target.com",
            subject="Your Weekly Deals: New Arrivals + Extra 20% Off",
            body="Shop this week's hottest deals! New arrivals in clothing, home decor, and beauty. Plus, use code SAVE20 for an extra 20% off your order. Free shipping on orders $35+.",
            category="ecommerce",
            source="synthetic"
        ),
        Example(
            sender="info@etsy.com",
            subject="Trending: Handmade Holiday Gifts",
            body="Discover unique handmade gifts perfect for the holidays. From custom jewelry to personalized home decor, find something special for everyone on your list.",
            category="ecommerce",
            source="synthetic"
        ),
        Example(
            sender="promo@ubereats.com",
            subject="Hungry? Get $10 off your next order",
            body="Your exclusive promo code: SAVE10. Order from your favorite restaurants and save $10 on orders $25+. Limited time offer.",
            category="ecommerce",
            source="synthetic"
        ),
        
        # Political examples
        Example(
            sender="team@berniesanders.com",
            subject="We need 10,000 donors before midnight",
            body="Our grassroots movement depends on small-dollar donations from supporters like you. Can you chip in $27 before our end-of-quarter deadline? Every contribution helps us fight for Medicare for All.",
            category="political",
            source="synthetic"
        ),
        Example(
            sender="info@actblue.com",
            subject="Your donation receipt - Thank you!",
            body="Thank you for your contribution to the Democratic Party. Your donation of $50 will help elect progressive candidates nationwide. Paid for by ActBlue.",
            category="political",
            source="synthetic"
        ),
        Example(
            sender="action@moveon.org",
            subject="URGENT: Call your senator TODAY",
            body="The Senate is voting on critical voting rights legislation this week. Call your senator NOW and demand they vote YES on the Freedom to Vote Act. Our democracy depends on it.",
            category="political",
            source="synthetic"
        ),
        Example(
            sender="team@winred.com",
            subject="President Trump needs your help",
            body="The radical left is trying to silence conservative voices. Stand with President Trump and donate $50 today to fight back. 500% MATCH ACTIVE - Don't wait!",
            category="political",
            source="synthetic"
        ),
        
        # None examples
        Example(
            sender="noreply@github.com",
            subject="[mailtagger] New pull request opened",
            body="User johndoe opened a new pull request: 'Add DSPy integration'. Review the changes and provide feedback.",
            category="none",
            source="synthetic"
        ),
        Example(
            sender="calendar@google.com",
            subject="Reminder: Team meeting in 30 minutes",
            body="Your meeting 'Weekly Team Sync' starts at 2:00 PM. Join Zoom: https://zoom.us/j/123456789",
            category="none",
            source="synthetic"
        ),
        Example(
            sender="billing@netflix.com",
            subject="Your Netflix payment receipt",
            body="Your payment of $15.99 for Netflix Premium has been processed. Your subscription will renew on March 15, 2026.",
            category="none",
            source="synthetic"
        ),
        Example(
            sender="support@stripe.com",
            subject="Payment successful for your subscription",
            body="Your payment of $29.00 to Example SaaS has been processed successfully. Invoice #12345 is attached.",
            category="none",
            source="synthetic"
        ),
    ]
    
    logger.info(f"Created {len(examples)} synthetic examples")
    return examples


def split_dataset(
    examples: List[Example],
    train_ratio: float = 0.2,
    val_ratio: float = 0.8,
    random_seed: int = 42
) -> tuple[List[Example], List[Example]]:
    """Split dataset into training and validation sets.
    
    DSPy optimizers work best with small training sets and large validation sets,
    contrary to traditional ML. This is because prompt optimization needs stable
    validation metrics more than extensive training data.
    
    Args:
        examples: List of examples to split
        train_ratio: Fraction for training (default: 0.2)
        val_ratio: Fraction for validation (default: 0.8)
        random_seed: Random seed for reproducibility
        
    Returns:
        Tuple of (train_examples, val_examples)
    """
    import random
    random.seed(random_seed)
    
    # Shuffle examples
    shuffled = examples.copy()
    random.shuffle(shuffled)
    
    # Calculate split points
    n = len(shuffled)
    train_size = int(n * train_ratio)
    
    train_set = shuffled[:train_size]
    val_set = shuffled[train_size:]
    
    logger.info(f"Split {n} examples into {len(train_set)} train, {len(val_set)} val")
    return train_set, val_set


def save_dataset(
    examples: List[Example],
    output_path: str,
    format: str = "json"
):
    """Save dataset to file.
    
    Args:
        examples: List of examples to save
        output_path: Path to output file
        format: Format ('json' or 'jsonl')
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        # Single JSON array
        data = [ex.to_dict() for ex in examples]
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    elif format == "jsonl":
        # JSON Lines (one example per line)
        with open(output_path, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex.to_dict()) + '\n')
    
    else:
        raise ValueError(f"Unknown format: {format}")
    
    logger.info(f"Saved {len(examples)} examples to {output_path}")


def load_dataset(input_path: str, format: str = "json") -> List[Example]:
    """Load dataset from file.
    
    Args:
        input_path: Path to input file
        format: Format ('json' or 'jsonl')
        
    Returns:
        List of Example objects
    """
    with open(input_path, 'r') as f:
        if format == "json":
            data = json.load(f)
        elif format == "jsonl":
            data = [json.loads(line) for line in f]
        else:
            raise ValueError(f"Unknown format: {format}")
    
    examples = []
    for item in data:
        metadata = {k: v for k, v in item.items() 
                   if k not in ['sender', 'subject', 'body', 'category']}
        example = Example(
            sender=item['sender'],
            subject=item['subject'],
            body=item.get('body', ''),
            category=item['category'],
            **metadata
        )
        examples.append(example)
    
    logger.info(f"Loaded {len(examples)} examples from {input_path}")
    return examples


def main():
    """CLI for creating evaluation datasets."""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description="Create DSPy evaluation dataset")
    parser.add_argument('--output', default='./data/eval_dataset.json',
                       help='Output path for dataset')
    parser.add_argument('--format', choices=['json', 'jsonl'], default='json',
                       help='Output format')
    parser.add_argument('--synthetic', action='store_true',
                       help='Use synthetic examples')
    parser.add_argument('--db-path', default='./data/prompts.db',
                       help='Path to prompts database')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='Minimum confidence for test results')
    
    args = parser.parse_args()
    
    # Load examples
    if args.synthetic:
        print("Creating synthetic examples...")
        examples = create_synthetic_examples()
    else:
        print(f"Loading test results from {args.db_path}...")
        examples = load_test_results(
            db_path=args.db_path,
            min_confidence=args.min_confidence
        )
        
        if not examples:
            print("No test results found, using synthetic examples")
            examples = create_synthetic_examples()
    
    # Split into train/val
    train_examples, val_examples = split_dataset(examples)
    
    # Save datasets
    train_path = args.output.replace('.json', '_train.json')
    val_path = args.output.replace('.json', '_val.json')
    
    save_dataset(train_examples, train_path, args.format)
    save_dataset(val_examples, val_path, args.format)
    
    print(f"\n✓ Created evaluation datasets:")
    print(f"  Training:   {train_path} ({len(train_examples)} examples)")
    print(f"  Validation: {val_path} ({len(val_examples)} examples)")
    print(f"\nNext steps:")
    print(f"  1. Review the datasets for quality")
    print(f"  2. Run optimization: python -m evaluation.optimize")
    print(f"  3. Evaluate results: python -m evaluation.evaluate")


if __name__ == "__main__":
    main()
