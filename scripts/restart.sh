#!/bin/bash
# Prepare and restart Mailtagger locally
# Run from project root: ./scripts/restart.sh

set -e
cd "$(dirname "$0")/.."

echo "=== Mailtagger Restart ==="

# Create data directory
mkdir -p data
echo "  data/ directory ready"

# Create .env from example if missing
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        cp env.example .env
        echo "  Created .env from env.example (edit with your values)"
    elif [ -f .env.example ]; then
        cp .env.example .env
        echo "  Created .env from .env.example (edit with your values)"
    fi
else
    echo "  .env exists"
fi

# Create venv if missing
if [ ! -d .venv ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi

# Install dependencies
echo "  Installing dependencies..."
.venv/bin/pip install -q -r requirements.txt -r requirements-api.txt

echo ""
echo "=== Ready. Start with: ==="
echo "  source .venv/bin/activate"
echo "  python3 api.py                    # API on :8000"
echo "  python3 gmail_categorizer.py      # Run categorizer once"
echo "  python3 gmail_categorizer.py --daemon   # Daemon mode"
echo ""
echo "  Or with Docker: docker compose up -d"
echo ""
