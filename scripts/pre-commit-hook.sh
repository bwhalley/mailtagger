#!/bin/bash
# Pre-commit hook to prevent committing sensitive files
# Copy this to .git/hooks/pre-commit to use it

echo "🔒 Running pre-commit security checks..."

# Check for sensitive files in staged changes
sensitive_files=(".env" "credentials.json" "token.json" "*.key" "*.pem" "*.p12" "*.pfx")

found_sensitive=false

for pattern in "${sensitive_files[@]}"; do
    if git diff --cached --name-only | grep -q "$pattern"; then
        echo "❌ ERROR: Attempting to commit sensitive file: $pattern"
        echo "   This file contains sensitive information and should not be committed."
        echo "   Please remove it from staging and ensure it's in .gitignore"
        found_sensitive=true
    fi
done

if [ "$found_sensitive" = true ]; then
    echo ""
    echo "🚫 Commit blocked for security reasons."
    echo "Please fix the issues above before committing."
    exit 1
fi

# Check for potential API keys in staged changes
if git diff --cached | grep -q "sk-[a-zA-Z0-9]"; then
    echo "❌ ERROR: Potential API key found in staged changes"
    echo "   Please remove any API keys before committing"
    exit 1
fi

if git diff --cached | grep -q "AIza[a-zA-Z0-9_-]"; then
    echo "❌ ERROR: Potential Google API key found in staged changes"
    echo "   Please remove any API keys before committing"
    exit 1
fi

echo "✅ Security checks passed - commit allowed"
exit 0 