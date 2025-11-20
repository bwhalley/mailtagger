# Fix: Docker OAuth Flow Issue

## Problem

The daemon was trying to run an interactive OAuth flow when no token exists, causing:
```
ERROR - Failed to initialize Gmail service: could not locate runnable browser
```

This happened because the daemon auto-starts in Docker but can't open a browser for OAuth.

## Solution

Updated the code so the daemon:
1. ✅ Checks for existing token
2. ✅ If no token, displays helpful message instead of trying OAuth
3. ✅ Waits for you to authorize via web interface
4. ✅ Continues running and retries every 5 minutes

## What Changed

### `gmail_categorizer.py`

**Updated `gmail_service()` function:**
- Added `skip_auth_flow` parameter
- In daemon mode, skips interactive OAuth
- Shows helpful message directing to web interface

**Updated `run_once()` function:**
- Added `daemon_mode` parameter
- Passes `skip_auth_flow=True` when in daemon mode
- Handles "not authorized" gracefully

**Updated `run_daemon()` function:**
- Passes `daemon_mode=True` to `run_once()`
- Daemon now waits patiently for authorization

## How to Deploy

### 1. Update Code on Server

```bash
cd /Users/brian/Downloads/mailtagger

# Copy updated file
scp gmail_categorizer.py user@hanweir.146sharon.com:/opt/mailtagger/
```

### 2. Rebuild Docker Image (if using Docker)

```bash
# On server
ssh user@hanweir.146sharon.com
cd /opt/mailtagger
docker-compose build
docker-compose up -d
```

### 3. Authorize Gmail via Web Interface

```bash
# Open browser
https://hanweir.146sharon.com

# Go to "Gmail Auth" tab
# Click "Authorize Gmail"
# Complete authorization
```

### 4. Verify Daemon Starts Processing

Watch the logs:
```bash
docker-compose logs -f mailtagger-app

# You should see:
# "Gmail is authorized and ready!"
# "Starting email processing run..."
# "[ecommerce] conf=0.95 ..."
```

## New Daemon Behavior

### Before Authorization

```
INFO - Starting email processing run
WARNING - ========================================
WARNING - Gmail not authorized! Please authorize via web interface:
WARNING - 1. Open your Mailtagger web interface
WARNING - 2. Go to 'Gmail Auth' tab
WARNING - 3. Click 'Authorize Gmail'
WARNING - ========================================
ERROR - Failed to initialize Gmail service: Gmail not authorized
INFO - Waiting for Gmail authorization via web interface...
INFO - Next run scheduled at 2025-11-20 03:48:20 (in 300s)
```

The daemon keeps running and retries every 5 minutes automatically!

### After Authorization

```
INFO - Starting email processing run
INFO - Found 15 thread(s) to process
INFO - [ecommerce] conf=0.95  Black Friday Sale...
INFO - [political] conf=0.89  Help us win in 2024...
INFO - Run #1 completed in 12.3s
INFO - Total emails processed since startup: 15
```

## Testing Locally

```bash
cd /Users/brian/Downloads/mailtagger

# Test daemon mode (should show helpful message if no token)
./venv/bin/python gmail_categorizer.py --daemon

# Press Ctrl+C to stop

# Test with token (should work normally)
./venv/bin/python gmail_categorizer.py --dry-run --max 5
```

## Key Improvements

✅ **No more browser errors** - Daemon doesn't try to open browser
✅ **Helpful messages** - Clear instructions on what to do
✅ **Graceful waiting** - Daemon keeps running, retries automatically
✅ **Works with Docker** - Perfect for containerized deployments
✅ **Works with VPN servers** - No interactive terminal needed

## Flow Diagram

```
Docker Container Starts
   ↓
Daemon Starts
   ↓
Check for token.json
   ↓
   ├─ Token exists? → Process emails ✅
   │
   └─ No token? → Show message, wait for web auth
        ↓
        User authorizes via web interface
        ↓
        token.json created
        ↓
        Next daemon cycle (5 min) → Process emails ✅
```

## Important Notes

### Token Location

Token must be in `CREDENTIALS_PATH` (default: current directory or `/app/data` in Docker):
```
/app/data/token.json         ← Docker
/opt/mailtagger/token.json   ← Server without Docker
```

### Credentials Setup

You still need `credentials.json` in place BEFORE authorizing:
```bash
# Copy to server
scp credentials.json user@hanweir.146sharon.com:/opt/mailtagger/

# In Docker, make sure it's mounted
volumes:
  - ./credentials.json:/app/credentials.json:ro
  - ./data:/app/data
```

### Web Interface Authorization

The web interface OAuth flow creates `token.json` automatically:
1. Web interface calls `/api/oauth/start`
2. Redirects to Google
3. User authorizes
4. Google calls `/api/oauth/callback`
5. API saves `token.json`
6. Next daemon cycle picks it up ✅

## Troubleshooting

### Daemon still shows "could not locate runnable browser"

**Problem:** You're running old code.

**Solution:**
```bash
# Make sure you deployed the updated gmail_categorizer.py
scp gmail_categorizer.py user@server:/opt/mailtagger/
docker-compose build
docker-compose restart
```

### "credentials.json not found"

**Problem:** OAuth client credentials not on server.

**Solution:**
```bash
# Copy credentials.json to server
scp credentials.json user@server:/opt/mailtagger/

# Or in Docker data directory
scp credentials.json user@server:/opt/mailtagger/data/
```

### Daemon authorized but not processing

**Problem:** Token might be in wrong location.

**Solution:**
```bash
# Check token location
docker exec -it mailtagger-app ls -la /app/data/token.json

# Verify CREDENTIALS_PATH matches
docker exec -it mailtagger-app env | grep CREDENTIALS_PATH
```

### Web interface shows authorized but daemon doesn't

**Problem:** Token locations might differ.

**Solution:**
Make sure `CREDENTIALS_PATH` env var is set consistently:
```yaml
# In docker-compose.yml
environment:
  - CREDENTIALS_PATH=/app/data
  
volumes:
  - ./data:/app/data
```

## Summary

With this fix:
1. ✅ Daemon starts successfully even without Gmail auth
2. ✅ Shows helpful message instead of error
3. ✅ Waits patiently for web-based authorization
4. ✅ Auto-detects when authorization is complete
5. ✅ Starts processing emails automatically

Perfect for Docker and remote server deployments! 🎉

