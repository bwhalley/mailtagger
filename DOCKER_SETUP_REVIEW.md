# Docker Setup Review & Corrections

## Current Architecture

You have **3 Docker containers** running:

```
┌─────────────────────────────────────────────────────────────┐
│  Host: Ubuntu 24.04 (hanweir.146sharon.com)                 │
│                                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ mailtagger-app  │  │ mailtagger-api  │  │ mailtagger- │ │
│  │ (daemon)        │  │ (FastAPI)       │  │ ui (nginx)  │ │
│  │                 │  │                 │  │             │ │
│  │ Processes       │  │ Serves API      │  │ Serves      │ │
│  │ emails every    │  │ /api/*          │  │ web files   │ │
│  │ 5 minutes       │  │                 │  │             │ │
│  │                 │  │ Port: 8000      │  │ Port: 8080  │ │
│  │ Uses:           │  │                 │  │             │ │
│  │ - Ollama        │  │ Uses:           │  │             │ │
│  │ - Gmail API     │  │ - Gmail API     │  │             │ │
│  │ - prompts.db    │  │ - prompts.db    │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│         │                     │                     │        │
│         └─────────────────────┴─────────────────────┘        │
│                          │                                    │
│                    ./data/ (shared)                           │
│                    - credentials.json                         │
│                    - token.json                               │
│                    - prompts.db                               │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Host Services (via network_mode: host)              │   │
│  │  - Ollama on localhost:11434                         │   │
│  │  - nginx on port 80/443 (proxies to containers)      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Network Architecture

**All containers use `network_mode: host`:**
- Containers share the host's network namespace
- They communicate via `localhost`
- Port exposure is direct to host

**Flow:**
```
Browser (HTTPS)
    ↓
Host nginx (port 443)
    ↓
├─→ Static files: /home/brian/mailtagger/web/
└─→ API requests (/api/*): → localhost:8000 (mailtagger-api container)
        ↓
        └─→ Can access Gmail API (needs credentials.json + token.json)
        └─→ Can access Ollama (localhost:11434)

mailtagger-app container:
    └─→ Also needs credentials.json + token.json
    └─→ Also accesses Ollama (localhost:11434)
```

## Current Issues

### 1. OAuth Credentials Type Mismatch

**DOCKER.md says:** Use "Desktop app" OAuth credentials
**But we're using:** Web-based OAuth flow (needs "Web application" credentials)

**Problem:** Desktop app credentials don't support web redirect URIs!

### 2. Credentials Location

**Current setup:**
- Both containers mount: `./data:/app/data:rw`
- Both set: `CREDENTIALS_PATH=/app/data`
- credentials.json should be in: `/home/brian/mailtagger/data/`

**Correct!** ✅

### 3. Old vs New Client ID

The container is somehow caching or using old credentials. Let's verify:

```bash
# What's on the host?
cat /home/brian/mailtagger/data/credentials.json | jq -r '.web.client_id'

# What's in the container?
docker exec -it mailtagger-api cat /app/data/credentials.json | jq -r '.web.client_id'

# Should both show: 566089143934-2q3bnpe3tfatj4sonc7kterkhiqjh7i3
```

---

## Corrected Setup Guide

### Step 1: Verify Credentials File

```bash
cd /home/brian/mailtagger

# Check credentials.json has the RIGHT client_id and is "web" type
cat data/credentials.json | jq '{
  type: (if .web then "web" else if .installed then "desktop" else "unknown" end end),
  client_id: (.web.client_id // .installed.client_id)
}'

# Should show:
# {
#   "type": "web",
#   "client_id": "566089143934-2q3bnpe3tfatj4sonc7kterkhiqjh7i3..."
# }
```

**If it shows "desktop" type:** You need to create a new "Web application" OAuth client!

### Step 2: Ensure Redirect URIs are Configured

In Google Cloud Console for client `...jh7i3`:

**Must have these redirect URIs:**
```
https://hanweir.146sharon.com/api/oauth/callback
http://localhost:8000/api/oauth/callback
```

### Step 3: Completely Rebuild Containers

```bash
cd /home/brian/mailtagger

# Stop everything
docker-compose down

# Remove old images
docker rmi mailtagger-mailtagger mailtagger-prompt-api

# Clear any potential caches
docker builder prune -f

# Rebuild from scratch
docker-compose build --no-cache

# Start services
docker-compose up -d

# Watch logs
docker-compose logs -f
```

### Step 4: Verify Container Can Read Credentials

```bash
# Check the API container
docker exec -it mailtagger-api python3 << 'EOF'
import json
import os
from pathlib import Path

creds_path = Path(os.getenv('CREDENTIALS_PATH', '.')) / 'credentials.json'
print(f"Reading from: {creds_path}")
print(f"Exists: {creds_path.exists()}")

if creds_path.exists():
    with open(creds_path) as f:
        data = json.load(f)
        if 'web' in data:
            print(f"Type: WEB APPLICATION ✅")
            print(f"Client ID: {data['web']['client_id']}")
            print(f"Redirect URIs: {data['web'].get('redirect_uris', [])}")
        elif 'installed' in data:
            print(f"Type: DESKTOP APPLICATION ❌")
            print(f"Client ID: {data['installed']['client_id']}")
            print("ERROR: Need 'web' type, not 'installed'!")
EOF
```

### Step 5: Test OAuth Flow

1. Open: `https://hanweir.146sharon.com`
2. Go to "Gmail Auth" tab
3. Click "Revoke Authorization" (if shown)
4. Click "Authorize Gmail"
5. Watch what happens

**Debug in browser:**
- Open DevTools (F12)
- Network tab
- Click "Authorize Gmail"
- Look at `/api/oauth/start` response
- The `auth_url` should contain client_id ending in `...jh7i3`

---

## Common Problems & Solutions

### Problem: "redirect_uri_mismatch" Error

**Cause:** Google OAuth client doesn't have the redirect URI configured

**Fix:**
1. Note the exact redirect URI from the error URL
2. Go to Google Cloud Console → Credentials
3. Edit the OAuth client (the one matching the client_id in error)
4. Add the exact redirect URI
5. Save and wait 2 minutes

### Problem: Still Using Old Client ID

**Possible causes:**
1. **Wrong file on host:** Check `/home/brian/mailtagger/data/credentials.json`
2. **Container not rebuilt:** Need `--no-cache` rebuild
3. **Multiple credentials.json files:** Search: `find /home/brian/mailtagger -name "credentials.json"`
4. **Python import cache:** Rebuild container completely

**Fix:**
```bash
# Nuclear option - completely clean and rebuild
cd /home/brian/mailtagger
docker-compose down
docker system prune -af  # WARNING: Removes ALL unused Docker data
docker-compose build --no-cache
docker-compose up -d
```

### Problem: Container Can't Find credentials.json

**Cause:** File permissions or volume mount issues

**Fix:**
```bash
# Check file exists and has right permissions
ls -la /home/brian/mailtagger/data/credentials.json
# Should be readable: -rw-r--r-- or -rw-rw-r--

# Fix permissions if needed
chmod 644 /home/brian/mailtagger/data/credentials.json

# Verify mount in container
docker exec -it mailtagger-api ls -la /app/data/
# Should show credentials.json
```

---

## OAuth Credentials: Desktop vs Web

### Desktop App Credentials (OLD - Don't Use for Web OAuth)

```json
{
  "installed": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"]
  }
}
```

**Used for:** Command-line OAuth (copy/paste code)
**Problem:** Can't redirect to your web server!

### Web Application Credentials (NEW - Required for Web OAuth)

```json
{
  "web": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uris": [
      "https://hanweir.146sharon.com/api/oauth/callback",
      "http://localhost:8000/api/oauth/callback"
    ]
  }
}
```

**Used for:** Web-based OAuth (automatic redirect)
**Required for:** Your web UI OAuth flow ✅

---

## Testing Checklist

After setup, verify each component:

### ✅ Container Status
```bash
docker ps
# All 3 containers should be "Up" and "healthy"
```

### ✅ Credentials File
```bash
docker exec -it mailtagger-api cat /app/data/credentials.json | jq '.web.client_id'
# Should show: "566089143934-2q3bnpe3tfatj4sonc7kterkhiqjh7i3..."
```

### ✅ API Health
```bash
curl http://localhost:8000/health | jq
# Should return healthy with oauth_available: true
```

### ✅ Gmail Status
```bash
curl http://localhost:8000/api/gmail/status | jq
# Should show credentials_exists: true
```

### ✅ Web UI
```bash
# Open in browser
https://hanweir.146sharon.com
# Should load without 500 error
```

### ✅ OAuth Flow
1. Browser → Gmail Auth tab
2. Click "Authorize Gmail"
3. Should redirect to Google (with correct client_id in URL)
4. Sign in and grant permissions
5. Should redirect back successfully
6. Gmail Auth tab shows "✅ Gmail Authorized"

---

## Summary of Fixes Needed

1. ✅ **Credentials location:** Already correct (`./data/`)
2. ❓ **Credentials type:** Verify it's "web" not "desktop"
3. ❓ **Client ID:** Verify containers use new one (`...jh7i3`)
4. ❓ **Redirect URIs:** Add to Google Cloud Console
5. 🔄 **Container rebuild:** Do a clean `--no-cache` rebuild

Run the verification commands above and share the output!

