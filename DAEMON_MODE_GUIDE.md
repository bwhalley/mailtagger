# Daemon Mode Quick Start Guide

## 🚀 Quick Start

### Run in Daemon Mode (Continuous Processing)
```bash
# Basic daemon mode - check every 5 minutes
python3 gmail_categorizer.py --daemon

# Custom interval - check every 10 minutes
python3 gmail_categorizer.py --daemon --interval 600

# Dry run mode (no changes, just testing)
python3 gmail_categorizer.py --daemon --dry-run --interval 60
```

### Run Once (Original Behavior)
```bash
# Process emails once and exit
python3 gmail_categorizer.py

# Dry run (no changes)
python3 gmail_categorizer.py --dry-run
```

---

## 🎛️ Configuration Options

### Environment Variables (Recommended)
Create or edit `.env` file:
```bash
# Daemon settings
DAEMON_INTERVAL=300              # Check every 5 minutes
LOG_LEVEL=INFO                   # INFO, DEBUG, WARNING, ERROR
CREDENTIALS_PATH=.               # Path to credentials

# LLM settings
LLM_PROVIDER=ollama              # or 'openai'
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_MODEL=llama3.1:8b

# Processing settings
MAX_RESULTS=40                   # Emails per run
SLEEP_SECONDS=0.5               # Pause between emails
```

### Command Line Arguments (Override .env)
```bash
--daemon                         # Enable daemon mode
--interval 600                   # Seconds between runs
--log-level DEBUG                # Logging verbosity
--credentials-path /app/data     # Custom credentials location
--max 50                         # Max emails per run
--dry-run                        # Don't make changes
--verbose                        # Verbose LLM output
```

---

## 📊 Logging Levels

### INFO (Default) - Production
Shows important events only:
- Startup configuration
- Emails categorized (ecommerce/political only)
- Processing statistics
- Errors

```bash
python3 gmail_categorizer.py --daemon --log-level INFO
```

### DEBUG - Troubleshooting
Shows everything:
- All emails processed (including "none")
- API request/response details
- Token operations
- Internal operations

```bash
python3 gmail_categorizer.py --daemon --log-level DEBUG
```

### WARNING - Quiet Mode
Shows only warnings and errors:
- Health check failures
- API issues
- Parsing errors

```bash
python3 gmail_categorizer.py --daemon --log-level WARNING
```

---

## 🏥 Health Checks

The daemon performs health checks on startup:

### ✅ What's Checked
1. **Credentials**: `credentials.json` exists
2. **Token**: `token.json` exists (warning if missing)
3. **Ollama**: Service is reachable and model is available
4. **OpenAI**: API key is set (if using OpenAI)

### 🔴 If Health Checks Fail
The daemon will exit with an error message. Common issues:

**Ollama not running:**
```bash
# Start Ollama first
ollama serve
```

**Model not available:**
```bash
# Pull the model
ollama pull llama3.1:8b
```

**Credentials missing:**
```bash
# Get credentials from Google Cloud Console
# Download as credentials.json
# See README.md for details
```

---

## 🛑 Stopping the Daemon

### Graceful Shutdown
Press **Ctrl+C** or send SIGTERM:
```bash
# In terminal with daemon running
Ctrl+C

# Or from another terminal
pkill -TERM -f gmail_categorizer.py

# Docker
docker stop mailtagger
```

The daemon will:
1. Finish processing current email
2. Log shutdown statistics
3. Exit cleanly

### Force Kill (Not Recommended)
```bash
pkill -9 -f gmail_categorizer.py
```

---

## 📈 Monitoring the Daemon

### View Logs in Real-Time
```bash
# If running in foreground
python3 gmail_categorizer.py --daemon

# If running in background
tail -f mailtagger.log

# Docker
docker logs -f mailtagger
```

### Key Log Messages

**Startup:**
```
INFO - ================================================================================
INFO - Gmail Email Categorizer - Daemon Mode
INFO - Configuration:
INFO -   LLM Provider: ollama
INFO -   Interval: 300s (5.0 minutes)
INFO - Daemon started successfully
```

**Processing:**
```
INFO - Run #1 started at 2025-11-09 10:00:01
INFO - Found 12 thread(s) to process
INFO - [ecommerce ] conf=0.92  Black Friday Sale...
INFO - Processing complete. Processed: 12, Errors: 0
INFO - Next run scheduled at 2025-11-09 10:05:01
```

**Errors:**
```
ERROR - Failed to initialize Gmail service: ...
ERROR - Ollama health check failed: ...
ERROR - Gmail API error processing thread ...: ...
```

---

## 🐛 Troubleshooting

### Daemon Starts But No Emails Processed
**Check the query:**
```bash
# See what query is being used
python3 gmail_categorizer.py --daemon --log-level DEBUG
# Look for: "Query: in:inbox newer_than:14d -label:AI_Triaged"

# Try a broader query
python3 gmail_categorizer.py --daemon --query "in:inbox newer_than:1d"
```

### High Error Rate
**Enable debug logging:**
```bash
python3 gmail_categorizer.py --daemon --log-level DEBUG --interval 300
```

Look for:
- API timeout errors → Increase `OPENAI_TIMEOUT`
- Rate limit errors → Increase `SLEEP_SECONDS`
- Parse errors → Check LLM responses

### Daemon Stops Unexpectedly
**Check logs for:**
- Out of memory
- Credential expiration
- API quota exceeded

**Test in foreground first:**
```bash
# Don't background it until it works
python3 gmail_categorizer.py --daemon --interval 60 --log-level DEBUG
```

### Gmail Token Expired
The daemon should auto-refresh. If it fails:
```bash
# Delete old token
rm token.json

# Run once to re-authenticate
python3 gmail_categorizer.py --dry-run

# Restart daemon
python3 gmail_categorizer.py --daemon
```

---

## 🔧 Advanced Usage

### Running in Background (Linux/Mac)
```bash
# Using nohup
nohup python3 gmail_categorizer.py --daemon > mailtagger.log 2>&1 &

# View logs
tail -f mailtagger.log

# Stop
pkill -TERM -f gmail_categorizer.py
```

### Running as systemd Service (Linux)
Create `/etc/systemd/system/mailtagger.service`:
```ini
[Unit]
Description=Gmail Email Categorizer
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/mailtagger
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 gmail_categorizer.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mailtagger
sudo systemctl start mailtagger
sudo systemctl status mailtagger
sudo journalctl -u mailtagger -f  # View logs
```

### Multiple Instances (Different Queries)
```bash
# Instance 1: Recent emails
python3 gmail_categorizer.py --daemon \
  --query "in:inbox newer_than:1d -label:AI_Triaged" \
  --interval 300 \
  --credentials-path ./data1

# Instance 2: Older emails
python3 gmail_categorizer.py --daemon \
  --query "in:inbox older_than:1d newer_than:7d -label:AI_Triaged" \
  --interval 3600 \
  --credentials-path ./data2
```

---

## 📋 Pre-Flight Checklist

Before running in production daemon mode:

- [ ] **Test one-time run**: `python3 gmail_categorizer.py --dry-run`
- [ ] **Test daemon mode**: `python3 gmail_categorizer.py --daemon --interval 60 --dry-run`
- [ ] **Verify health checks**: Check startup logs
- [ ] **Verify graceful shutdown**: Ctrl+C and check logs
- [ ] **Configure interval**: Set appropriate `DAEMON_INTERVAL`
- [ ] **Set log level**: Use INFO for production
- [ ] **Test token refresh**: Wait for token to expire (or delete it)
- [ ] **Monitor first hour**: Watch for errors or issues
- [ ] **Set up monitoring**: Log aggregation, alerting, etc.

---

## 🔐 Security Best Practices

### Daemon Mode
1. **Run as non-root user** (especially in containers)
2. **Use least-privilege OAuth scopes** (gmail.modify, not gmail.full)
3. **Protect credentials directory**: `chmod 700 data/`
4. **Rotate credentials periodically**
5. **Monitor for unusual activity**

### Production
1. **Don't log full email content** (already implemented)
2. **Use environment variables** (not .env in production)
3. **Encrypt credentials at rest** (volume encryption)
4. **Use secrets management** (Vault, K8s secrets, etc.)
5. **Audit access logs** regularly

---

## 📞 Getting Help

### Check Logs First
```bash
# Last 50 lines
tail -50 mailtagger.log

# Search for errors
grep ERROR mailtagger.log

# Search for specific email
grep "subject@email.com" mailtagger.log
```

### Enable Debug Mode
```bash
python3 gmail_categorizer.py --daemon --log-level DEBUG --verbose
```

### Test Components Separately
```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Test Gmail credentials
python3 -c "from gmail_categorizer import gmail_service; svc = gmail_service(); print('OK')"

# Test classifier (with small snippet)
python3 -c "from gmail_categorizer import call_llm_classifier; result = call_llm_classifier('Test', 'Hello', 'test@example.com'); print(result)"
```

---

## 🎯 Performance Tips

### Optimize for Speed
```bash
# Process fewer emails more frequently
python3 gmail_categorizer.py --daemon --interval 120 --max 20
```

### Optimize for Thoroughness
```bash
# Process more emails less frequently
python3 gmail_categorizer.py --daemon --interval 600 --max 100
```

### Balance Load
```bash
# Medium settings (recommended)
python3 gmail_categorizer.py --daemon --interval 300 --max 40
```

---

**Happy Categorizing! 🎉**

