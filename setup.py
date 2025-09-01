#!/usr/bin/env python3
"""
Setup script for Gmail LLM Categorizer
This script helps set up the project safely for GitHub publication
"""

import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        sys.exit(1)

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    if os.path.exists('.env'):
        print("✅ .env file already exists")
        return
    
    if os.path.exists('env.example'):
        shutil.copy('env.example', '.env')
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env with your actual values")
    else:
        print("❌ env.example not found")

def check_git_safety():
    """Check if the repository is safe for GitHub publication"""
    print("🔒 Checking GitHub safety...")
    
    # Check if sensitive files exist
    sensitive_files = ['.env', 'credentials.json', 'token.json']
    found_sensitive = []
    
    for file in sensitive_files:
        if os.path.exists(file):
            found_sensitive.append(file)
    
    if found_sensitive:
        print("⚠️  Found sensitive files that should not be committed:")
        for file in found_sensitive:
            print(f"   - {file}")
        print("   These files are in .gitignore and will not be committed")
    
    # Check .gitignore
    if not os.path.exists('.gitignore'):
        print("❌ .gitignore file not found - this is required for security!")
        return False
    
    print("✅ .gitignore file found")
    
    # Check if sensitive files are in .gitignore
    with open('.gitignore', 'r') as f:
        gitignore_content = f.read()
    
    required_patterns = ['.env', 'credentials.json', 'token.json']
    missing_patterns = []
    
    for pattern in required_patterns:
        if pattern not in gitignore_content:
            missing_patterns.append(pattern)
    
    if missing_patterns:
        print("❌ .gitignore is missing required patterns:")
        for pattern in missing_patterns:
            print(f"   - {pattern}")
        return False
    
    print("✅ .gitignore properly configured")
    return True

def main():
    """Main setup function"""
    print("🚀 Setting up Gmail LLM Categorizer...")
    print()
    
    check_python_version()
    print()
    
    install_dependencies()
    print()
    
    create_env_file()
    print()
    
    if check_git_safety():
        print("✅ Repository is safe for GitHub publication")
    else:
        print("❌ Repository needs configuration before GitHub publication")
        print("   Please fix the issues above before pushing to GitHub")
        sys.exit(1)
    
    print()
    print("🎉 Setup complete!")
    print()
    print("Next steps:")
    print("1. Edit .env with your actual configuration")
    print("2. Set up Gmail API credentials (see README.md)")
    print("3. Install and start Ollama (if using local LLM)")
    print("4. Run: python3 gmail_categorizer.py --dry-run")

if __name__ == "__main__":
    main() 