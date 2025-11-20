# Gmail OAuth - Quick Start

## TL;DR

Your Mailtagger now has a web-based Gmail authorization flow!

### 5-Minute Setup

1. **Create OAuth credentials in Google Cloud:**
   - https://console.cloud.google.com/
   - Create project → Enable Gmail API
   - Create OAuth client (Web application)
   - Add redirect URI: `https://hanweir.146sharon.com/api/oauth/callback`
   - Download credentials.json

2. **Upload to server:**
   ```bash
   scp credentials.json user@hanweir.146sharon.com:/opt/mailtagger/
   ```

3. **Authorize via web interface:**
   - Open `https://hanweir.146sharon.com`
   - Go to "🔐 Gmail Auth" tab
   - Click "Authorize Gmail"
   - Sign in and grant permissions
   - Done!

---

## What Changed

### New Features

✅ **Web-based OAuth flow** - No SSH needed!
✅ **Visual status indicator** - See authorization status
✅ **One-click authorization** - Authorize through browser
✅ **Easy revocation** - Revoke access from the UI
✅ **Email display** - Shows which Gmail account is connected

### New API Endpoints

- `GET /api/gmail/status` - Check authorization status
- `GET /api/oauth/start` - Start OAuth flow
- `GET /api/oauth/callback` - OAuth callback handler
- `POST /api/gmail/revoke` - Revoke authorization

### New UI Tab

**"🔐 Gmail Auth"** tab with:
- Real-time authorization status
- Authorize/Revoke buttons
- Setup instructions
- Connected email display

---

## For Remote Servers

This is **perfect for remote servers** (like your `hanweir.146sharon.com`):

### Old Way (Complicated)
```bash
# SSH to server
ssh user@server
cd /opt/mailtagger
python3 gmail_categorizer.py --dry-run
# Get URL, open in browser, copy code, paste back
# Error-prone, requires terminal access
```

### New Way (Easy!)
```bash
# Just open browser
# https://hanweir.146sharon.com
# Click "Gmail Auth" tab
# Click "Authorize Gmail"
# Done!
```

---

## Important: OAuth Client Type

**Must use "Web application"** OAuth client type (not "Desktop app")!

### When Creating OAuth Client:

1. Application type: **"Web application"** ✅
2. Authorized redirect URIs: **`https://hanweir.146sharon.com/api/oauth/callback`** ✅

### Why?

- Desktop app: Redirects to `localhost` (doesn't work on remote server)
- Web app: Redirects to your actual server URL ✅

---

## Redirect URI Examples

Use your actual server URL:

**HTTPS (recommended):**
```
https://hanweir.146sharon.com/api/oauth/callback
```

**With custom port:**
```
https://hanweir.146sharon.com:8000/api/oauth/callback
```

**HTTP (local testing only):**
```
http://localhost:8000/api/oauth/callback
```

The path `/api/oauth/callback` must be exact!

---

## Testing

### 1. Check Status
```bash
curl https://hanweir.146sharon.com/api/gmail/status
```

### 2. Test Email Access
- Go to "🧪 Test" tab in web UI
- Run test on 5 emails
- Should see classifications

### 3. Run Daemon
```bash
python3 gmail_categorizer.py --daemon
# Should start processing emails automatically
```

---

## Troubleshooting

### "Redirect URI mismatch"

**Fix:** Add your exact URL to Google Cloud Console:
1. Go to Credentials
2. Edit OAuth client
3. Add redirect URI: `https://hanweir.146sharon.com/api/oauth/callback`
4. Save

### "App is not verified"

**Normal for testing!** Click "Advanced" → "Go to Mailtagger (unsafe)"

This warning appears because your app isn't published. Safe to proceed for personal use.

### "Access blocked"

**Fix:** Add yourself as a test user:
1. Go to "OAuth consent screen"
2. Scroll to "Test users"
3. Add your Gmail address
4. Save

---

## Security

### Protected Files

Both files are sensitive and already in `.gitignore`:

```
credentials.json  ← OAuth client secret
token.json        ← Your access token
```

### Permissions

```bash
chmod 600 /opt/mailtagger/credentials.json
chmod 600 /opt/mailtagger/token.json
```

### Token Refresh

Tokens auto-refresh! The refresh token lasts until you revoke it.

---

## Files on Server

After setup, you'll have:

```
/opt/mailtagger/
├── credentials.json       ← OAuth client (from Google Cloud)
├── token.json            ← Access token (created after auth)
├── data/
│   └── prompts.db
└── ...
```

---

## Deployment

### To Deploy This Update:

```bash
# From your local machine
cd /Users/brian/Downloads/mailtagger

# Copy updated files to server
scp api.py web/index.html web/app.js web/style.css \
    user@hanweir.146sharon.com:/opt/mailtagger/

# Restart API server on server
ssh user@hanweir.146sharon.com
sudo systemctl restart mailtagger-api  # or however you run it
```

---

## Complete Documentation

See `GMAIL_OAUTH_SETUP.md` for detailed instructions, troubleshooting, and API documentation.

---

## Summary

✅ **Web-based authorization** - Easy, secure, remote-friendly
✅ **No terminal needed** - Everything through the browser
✅ **Visual feedback** - See status and connected account
✅ **Auto token refresh** - Handles expiration automatically
✅ **One-time setup** - Authorize once, works forever (until revoked)

Perfect for VPN-hosted servers! 🎉

