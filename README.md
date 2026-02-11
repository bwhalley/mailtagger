# Gmail LLM Categorizer — Ollama (local) or OpenAI

Switch between **Ollama** and **OpenAI** with an env var (no code edits).

## ⚠️ Security Notice

**IMPORTANT**: This project handles sensitive data (Gmail access, API keys). In the operation of this project, all data is handled locally or in conversation with Google only. But be careful! Before publishing anything back to GitHub:

1. **NEVER commit sensitive files**:
   - `credentials.json` (Gmail OAuth credentials)
   - `token.json` (Gmail access token)
   - `.env` (environment variables with API keys)
   - Any files containing real API keys or tokens

2. **Use environment variables** for all sensitive configuration
3. **Check your `.gitignore`** ensures sensitive files are excluded
4. **Review your git history** to ensure no secrets were committed

## 🚀 Quick Start

### 1. Environment Setup

Copy the example environment file and configure it:
```bash
cp env.example .env
# Edit .env with your actual values
```

### 2. Ollama Setup
1. Install Ollama and start it: `ollama serve`
2. Pull a local model you can run (quantized works great):
   ```bash
   ollama pull llama3.1:8b
   # or gpt-oss:20b, qwen2.5:14b, mistral-nemo:12b, etc.
   ```
3. Configure your `.env`:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_URL=http://localhost:11434/v1/chat/completions
   OLLAMA_MODEL=llama3.1:8b
   ```

### 3. Gmail API Setup
- Enable **Gmail API** in Google Cloud, create Desktop OAuth client, save as `credentials.json`
- First run opens a browser to authorize; `token.json` is then saved for future runs

### 4. Install Dependencies & Run
```bash
# Option A: Virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-api.txt

# Option B: Quick restart script
./scripts/restart.sh
source .venv/bin/activate

# Run categorizer
python3 gmail_categorizer.py --dry-run
python3 gmail_categorizer.py

# Run API + web UI (optional)
python3 api.py   # API on http://localhost:8000
# Serve web/ with any static server (e.g. nginx, or python -m http.server 8080)
```

### 5. Docker Restart
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

## 🔒 Security Features

- **Environment Variables**: All sensitive config uses `.env` files (excluded from git)
- **OAuth Tokens**: Gmail tokens stored locally, never committed
- **API Keys**: OpenAI keys stored in environment variables only
- **Local Processing**: Ollama runs entirely on your local machine

## 📁 File Structure

```
mailtagger-local/
├── gmail_categorizer.py    # Main application
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── env.example             # Environment variables template
├── .gitignore              # Git ignore rules
├── .env                    # Your environment variables (not in git)
├── credentials.json        # Gmail OAuth (not in git)
└── token.json             # Gmail access token (not in git)
```

## 🛡️ GitHub Safety Checklist

Before pushing to GitHub, verify:

- [ ] `.env` file is in `.gitignore`
- [ ] `credentials.json` is in `.gitignore`
- [ ] `token.json` is in `.gitignore`
- [ ] No API keys in code or commit history
- [ ] No real email addresses or personal data in examples
- [ ] `env.example` contains only placeholder values

## 📝 Notes

- JSON mode is enforced with `format=json` for Ollama; script falls back to `none` on parse errors.
- Labels created automatically: `AI_Ecommerce`, `AI_Political`, `AI_Triaged`.
- Only `gmail.modify` scope is used—no delete/send/archive.
- Supports both streaming and non-streaming Ollama responses.

## 🤝 Contributing

When contributing:
1. Never include real API keys or credentials
2. Use placeholder values in examples
3. Test with your own credentials locally
4. Ensure all sensitive files remain in `.gitignore`
