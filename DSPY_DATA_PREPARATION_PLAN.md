# DSPy Sample Data Preparation Plan

**Date:** February 24, 2026  
**Status:** Planning phase - awaiting data source decision

---

## Current State

### DSPy Implementation Complete ✅
- `dspy_signatures.py` - Email classification signatures
- `dspy_config.py` - LLM provider configuration (OpenAI/Ollama)
- `dspy_metrics.py` - Evaluation metrics (accuracy, F1, calibration)
- `dspy_optimizer.py` - BootstrapFewShot, Random Search, MIPRO optimizers
- `evaluation/create_dataset.py` - Dataset creation tools

### Database Schema (current)
```sql
classification_logs
├── category
├── confidence
├── processing_time
└── timestamp
```

**Gap:** Email content (`email_from`, `email_subject`, `email_body`) not stored

---

## Next Steps for Sample Data Preparation

### Option 1: Enhance Database Schema (Recommended for 200+ examples)

**Task 1.1: Add email content columns to database** (30 min)

```sql
-- Run in your SQLite database
ALTER TABLE classification_logs ADD COLUMN email_from TEXT;
ALTER TABLE classification_logs ADD COLUMN email_subject TEXT;
ALTER TABLE classification_logs ADD COLUMN email_body TEXT;
```

**Task 1.2: Modify `_persist_to_index()` to store email content** (30 min)

File: `gmail_categorizer.py:933`

```python
def _persist_to_index(
    gmail_id: str,
    thread_id: str,
    sender: str,
    subject: str,
    snippet: str = "",
    body_text: str = "",
    ...
):
    # Update SQL to include email content
    cursor.execute("""
        INSERT INTO classification_logs 
        (category, confidence, processing_time, timestamp,
         email_from, email_subject, email_body)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (category, confidence, elapsed, datetime.now().isoformat(),
          sender, subject, body_text))
```

**Task 1.3: Extract emails for labeling** (1 hour)

```bash
# Create labeling batches
python -m evaluation.extract_for_labeling \
    --output-dir ./data/labeling_batches \
    --batch-size 50
```

**Task 1.4: Manual labeling workflow** (4-8 hours for 200+ examples)

1. Open web UI: `http://localhost:8080`
2. Review emails and assign categories
3. Save labeled batches
4. Combine into final dataset

**Task 1.5: Format for DSPy** (30 min)

```python
import json
from evaluation.create_dataset import Example, save_dataset, split_dataset

# Load labeled examples
with open('./data/labeled_dataset.json') as f:
    labeled = json.load(f)

# Convert to Example objects
examples = [Example(
    sender=e['sender'],
    subject=e['subject'],
    body=e['body'],
    category=e['category']
) for e in labeled]

# Split: 20% train, 80% val (DSPy best practice)
train, val = split_dataset(examples, train_ratio=0.2)

# Save
save_dataset(train, './data/train.json')
save_dataset(val, './data/val.json')
```

---

### Option 2: Start Small with Synthetic Data (Quick Validation)

**Task 2.1: Create synthetic dataset** (5 min)

```bash
python evaluation/create_dataset.py --synthetic --output ./data/eval.json
```

**Task 2.2: Split dataset** (5 min)

```bash
# Manually split or use Python:
python -c "
from evaluation.create_dataset import load_dataset, split_dataset, save_dataset
train, val = split_dataset(load_dataset('./data/eval.json'), train_ratio=0.2)
save_dataset(train, './data/train.json')
save_dataset(val, './data/val.json')
"
```

**Task 2.3: Run BootstrapFewShot optimization** (10-15 min)

```bash
python dspy_optimizer.py \
    --train-data ./data/train.json \
    --val-data ./data/val.json \
    --optimizer bootstrap \
    --metric accuracy \
    --max-demos 5 \
    --output ./data/optimized_classifier.json
```

**Task 2.4: Test with USE_DSPY enabled** (5 min)

```bash
export USE_DSPY=true
python gmail_categorizer.py --dry-run --max-results 10
```

---

## Dataset Preparation Cheat Sheet

### DSPy Dataset Format

```json
[
  {
    "sender": "deals@amazon.com",
    "subject": "Flash Sale: 50% Off",
    "body": "Don't miss out on our biggest sale...",
    "category": "ecommerce"
  }
]
```

### Recommended Split Ratios

- **Training set:** 20% (DSPy optimizers need small training sets)
- **Validation set:** 80% (stable metrics for optimization)

### Category Distribution

Aim for balanced representation:
- `ecommerce`: ~33%
- `political`: ~33%
- `none`: ~34%

---

## Optimization Algorithms Comparison

| Algorithm | Time | Quality | Use Case |
|-----------|------|---------|----------|
| **BootstrapFewShot** | 2-5 min | Good | Initial testing |
| **Random Search** | 5-15 min | Better | Production optimization |
| **MIPRO** | 10-30 min | Best | Final production run |

---

## Post-Preparation Steps

### 1. Save Optimized Classifier

```bash
python dspy_optimizer.py --train-data ./data/train.json --val-data ./data/val.json --output ./data/optimized.json
```

### 2. Compare with Baseline

```python
from dspy_optimizer import compare_classifiers, EmailClassifierModule

baseline = EmailClassifierModule(use_cot=True)
optimized = load_optimized_classifier('./data/optimized.json')

test_examples = load_dataset('./data/val.json')
compare_classifiers(baseline, optimized, test_examples)
```

### 3. Deploy to Production

```bash
# Enable DSPy
export USE_DSPY=true

# Or in docker-compose.yml
environment:
  - USE_DSPY=true
  - DSPY_MODEL=gpt-4o-mini
```

---

## Troubleshooting

### "No examples found in dataset"
- Use synthetic examples: `--synthetic` flag
- Verify JSON format matches DSPy expectations

### "DSPy not available"
```bash
pip install dspy-ai>=2.5.0 pydantic>=2.0.0
```

### Low accuracy after optimization
- Check category balance in dataset
- Try different metrics (`weighted` or `combined`)
- Add more verified examples
- Increase validation set size

### Optimization takes too long
- Start with `bootstrap` (fastest)
- Reduce training examples (10-20 is optimal for DSPy)
- Use smaller `--max-demos` (3 instead of 5)

---

## File Locations

```
mailtagger/
├── evaluation/
│   ├── create_dataset.py          # Dataset creation tools
│   └── extract_for_labeling.py    # Email extraction for manual labeling (NEW)
├── data/
│   ├── prompts.db                 # Database (needs schema update)
│   ├── train.json                 # Training set (to be created)
│   ├── val.json                   # Validation set (to be created)
│   └── optimized_classifier.json  # Saved optimizer output
├── dspy_optimizer.py              # Optimization scripts
└── gmail_categorizer.py           # Main app (needs DB update)
```

---

## Quick Start Commands

### Immediate (5 minutes)
```bash
# Test with synthetic data
python evaluation/create_dataset.py --synthetic --output ./data/eval.json
python -c "from evaluation.create_dataset import load_dataset, split_dataset, save_dataset; train, val = split_dataset(load_dataset('./data/eval.json')); save_dataset(train, './data/train.json'); save_dataset(val, './data/val.json')"
```

### Short-term (1 hour)
```bash
# Enhance database schema
# Modify gmail_categorizer.py to store email content
# Run full email processing
```

### Medium-term (1 day)
```bash
# Manual labeling of 50-100 examples
# Re-run optimization
# Compare vs baseline
```

---

## Success Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Dataset ready | 1-2 hours | With database enhancement |
| First optimization | 15 minutes | Synthetic data |
| Production accuracy | +5-15% | vs baseline |
| Token reduction | 50-80% | Text extraction optimization already done |

---

**Next Session:** Decide between Option 1 (database enhancement) or Option 2 (quick synthetic validation)
