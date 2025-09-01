# Security Guide

This document outlines security best practices for the Gmail LLM Categorizer project.

## 🚨 Critical Security Notes

### Never Commit These Files
- `.env` - Contains your actual API keys and configuration
- `credentials.json` - Gmail OAuth credentials
- `token.json` - Gmail access tokens
- Any files with `.key`, `.pem`, `.p12`, or `.pfx` extensions
- Log files that might contain sensitive information

### Environment Variables
All sensitive configuration should use environment variables:
```bash
# ✅ Good - Use environment variables
OPENAI_API_KEY=your_actual_key_here

# ❌ Bad - Hardcode in source code
OPENAI_API_KEY = "sk-1234567890abcdef"
```

## 🔒 Security Features

### 1. .gitignore Protection
The `.gitignore` file is configured to exclude:
- Environment files (`.env`, `.env.*`)
- Credential files (`credentials.json`, `token.json`)
- Virtual environments (`.venv`, `venv/`)
- Log files and temporary files

### 2. Environment Variable Usage
The application uses `os.getenv()` for all configuration:
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
```

### 3. No Hardcoded Secrets
- No API keys in source code
- No hardcoded URLs (except localhost defaults)
- No hardcoded credentials

## 🛡️ Pre-Publication Checklist

Before publishing to GitHub, verify:

- [ ] `.env` file exists and is in `.gitignore`
- [ ] `credentials.json` is in `.gitignore`
- [ ] `token.json` is in `.gitignore`
- [ ] No API keys in commit history
- [ ] No real email addresses in examples
- [ ] `env.example` contains only placeholder values
- [ ] All sensitive files are excluded from git

## 🚀 Setup Security

### 1. Initial Setup
```bash
# Copy environment template
cp env.example .env

# Edit with real values (never commit this file)
nano .env
```

### 2. Gmail API Setup
1. Create project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download as `credentials.json` (excluded from git)
5. First run will create `token.json` (excluded from git)

### 3. API Keys
- OpenAI: Get from https://platform.openai.com/api-keys
- Store in `.env` file only
- Never share or commit API keys

## 🔍 Security Monitoring

### GitHub Actions
The repository includes automated security checks:
- Sensitive file detection
- .gitignore validation
- API key pattern detection
- Basic functionality tests

### Pre-commit Hook
Optional pre-commit hook prevents accidental commits:
```bash
# Copy to git hooks
cp scripts/pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## 🚨 Incident Response

If you accidentally commit sensitive information:

1. **Immediate Action**
   - Remove the file from git: `git rm --cached <file>`
   - Commit the removal: `git commit -m "Remove sensitive file"`
   - Force push: `git push --force-with-lease`

2. **Rotate Credentials**
   - Revoke and regenerate API keys
   - Regenerate Gmail OAuth credentials
   - Update your `.env` file

3. **Review History**
   - Check if sensitive data exists in other commits
   - Consider using `git filter-branch` for deep cleanup

## 📚 Additional Resources

- [GitHub Security Best Practices](https://docs.github.com/en/github/authenticating-to-github/keeping-your-account-and-data-secure)
- [Python Security Best Practices](https://docs.python-guide.org/writing/style/#security)
- [Environment Variables Best Practices](https://12factor.net/config)

## 🤝 Reporting Security Issues

If you find a security vulnerability:

1. **DO NOT** create a public issue
2. **DO** email the maintainer privately
3. **DO** provide detailed reproduction steps
4. **DO** wait for acknowledgment before disclosure

## 📝 Security Policy

This project follows a responsible disclosure policy:
- Security issues are addressed within 30 days
- Critical vulnerabilities are patched immediately
- Security updates are clearly documented
- Users are notified of security-relevant changes 