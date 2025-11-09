#!/usr/bin/env python3
"""
Health check script for Mailtagger Docker container.
Returns exit code 0 if healthy, non-zero if unhealthy.
"""

import sys
import os
from pathlib import Path

def check_credentials():
    """Check if credentials files exist."""
    creds_path = os.getenv('CREDENTIALS_PATH', '/app/data')
    
    credentials_file = Path(creds_path) / 'credentials.json'
    token_file = Path(creds_path) / 'token.json'
    
    if not credentials_file.exists():
        print(f"ERROR: credentials.json not found at {credentials_file}", file=sys.stderr)
        return False
    
    if not token_file.exists():
        print(f"WARNING: token.json not found at {token_file}", file=sys.stderr)
        print("This is expected on first run before OAuth", file=sys.stderr)
    
    return True

def check_imports():
    """Check if required Python modules can be imported."""
    required_modules = [
        'googleapiclient',
        'google.auth',
        'requests',
    ]
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError as e:
            print(f"ERROR: Failed to import {module}: {e}", file=sys.stderr)
            return False
    
    return True

def check_environment():
    """Check if required environment variables are set."""
    required_vars = ['LLM_PROVIDER']
    
    for var in required_vars:
        if not os.getenv(var):
            print(f"ERROR: Required environment variable {var} not set", file=sys.stderr)
            return False
    
    provider = os.getenv('LLM_PROVIDER', '').lower()
    
    if provider == 'openai':
        if not os.getenv('OPENAI_API_KEY'):
            print("ERROR: OPENAI_API_KEY not set but LLM_PROVIDER=openai", file=sys.stderr)
            return False
    elif provider == 'ollama':
        # Ollama URL check would require network call, skip for basic health check
        pass
    else:
        print(f"ERROR: Invalid LLM_PROVIDER: {provider}", file=sys.stderr)
        return False
    
    return True

def main():
    """Run all health checks."""
    checks = [
        ("Python imports", check_imports),
        ("Environment variables", check_environment),
        ("Credentials", check_credentials),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                print(f"FAILED: {check_name}", file=sys.stderr)
                all_passed = False
        except Exception as e:
            print(f"ERROR in {check_name}: {e}", file=sys.stderr)
            all_passed = False
    
    if all_passed:
        print("Health check: OK")
        sys.exit(0)
    else:
        print("Health check: FAILED", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

