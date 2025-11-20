# Gmail OAuth Setup with Web Interface

Your Mailtagger now includes a web-based Gmail authorization flow! This makes it easy to authorize Gmail access on remote servers.

## Overview

The new "🔐 Gmail Auth" tab in the web interface allows you to:
- ✅ Check Gmail authorization status
- ✅ Authorize Gmail access directly through the browser
- ✅ Revoke authorization when needed
- ✅ See which Gmail account is connected

## Setup Steps

### 1. Create Google Cloud Project & OAuth Credentials

#### A. Go to Google Cloud Console

Visit: https://console.cloud.google.com/

#### B. Create or Select a Project

1. Click "Select a project" at the top
2. Click "New Project"
3. Name it (e.g., "Mailtagger Gmail Access")
4. Click "Create"

#### C. Enable Gmail API

1. In your project, go to **"APIs & Services" → "Library"**
2. Search for **"Gmail API"**
3. Click on it
4. Click **"Enable"**

#### D. Configure OAuth Consent Screen

1. Go to **"APIs & Services" → "OAuth consent screen"**
2. Choose **"External"** (unless you have a Google Workspace)
3. Click "Create"
4. Fill in required fields:
   - **App name**: Mailtagger
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click "Save and Continue"
6. On "Scopes" screen: Click "Add or Remove Scopes"
   - Find and select: `https://www.googleapis.com/auth/gmail.modify`
   - Click "Update" and "Save and Continue"
7. On "Test users" screen:
   - Click "Add Users"
   - Add your Gmail address
   - Click "Save and Continue"
8. Review and click "Back to Dashboard"

#### E. Create OAuth Client ID

1. Go to **"APIs & Services" → "Credentials"**
2. Click **"Create Credentials" → "OAuth client ID"**
3. Choose **"Web application"**
4. Name it: "Mailtagger Web"
5. Under "Authorized redirect URIs", click "Add URI" and enter:
   ```
   https://hanweir.146sharon.com/api/oauth/callback
   ```
   
   **Important:** Use your actual server URL (must match exactly):
   - If using HTTPS: `https://your-domain.com/api/oauth/callback`
   - If using HTTP (local): `http://your-domain.com/api/oauth/callback`
   - If using port: `https://your-domain.com:8000/api/oauth/callback`

6. Click **"Create"**
7. A dialog will appear with your credentials
8. Click **"Download JSON"**
9. Save this file

### 2. Upload credentials.json to Your Server

Copy the downloaded JSON file to your server:

```bash
# From your local machine
scp ~/Downloads/client_secret_*.json user@hanweir.146sharon.com:/opt/mailtagger/credentials.json

# Or if you renamed it already
scp ~/Downloads/credentials.json user@hanweir.146sharon.com:/opt/mailtagger/credentials.json
```

Set proper permissions:

```bash
# On your server
ssh user@hanweir.146sharon.com
cd /opt/mailtagger
chmod 600 credentials.json
```

### 3. Authorize Gmail via Web Interface

1. **Open your Mailtagger web interface:**
   ```
   https://hanweir.146sharon.com
   ```

2. **Go to the "🔐 Gmail Auth" tab**

3. **Check the status** - You should see:
   - ✅ credentials.json found
   - ⚠️ Not authorized

4. **Click "Authorize Gmail"**

5. **You'll be redirected to Google** where you'll:
   - Sign in to your Gmail account
   - Review the permissions (read, modify, and label emails)
   - Click "Allow"

6. **You'll be redirected back** to Mailtagger with a success message

7. **Verify authorization** - You should now see:
   - ✅ Gmail Authorized
   - Your email address displayed

That's it! You can now test emails and run the daemon.

---

## How It Works

### Architecture

```
Browser
   ↓
Web Interface (Gmail Auth Tab)
   ↓
Click "Authorize Gmail"
   ↓
API Server (/api/oauth/start)
   ↓
Redirect to Google OAuth
   ↓
User grants permissions
   ↓
Google redirects to /api/oauth/callback
   ↓
API server saves token.json
   ↓
Success! Redirect back to Web UI
```

### Files Created

- **`credentials.json`** - Your OAuth client credentials (from Google Cloud)
- **`token.json`** - Your access/refresh tokens (created after authorization)

Both files are in your `CREDENTIALS_PATH` (default: `/opt/mailtagger/`)

---

## Testing

### Quick Test via Web Interface

1. Go to "🧪 Test" tab
2. Enter number of emails (e.g., 5)
3. Click "Run Test"
4. You should see classifications for your recent emails

### Test via Command Line

```bash
# On your server
cd /opt/mailtagger
python3 gmail_categorizer.py --dry-run --max 5

# You should see emails being classified
```

---

## Troubleshooting

### "credentials.json not found"

**Problem:** The credentials file isn't in the right location.

**Solution:**
```bash
# Check if file exists
ls -l /opt/mailtagger/credentials.json

# If not, copy it from the correct location
# Make sure CREDENTIALS_PATH env var matches
```

### "Redirect URI mismatch"

**Problem:** The redirect URI in Google Cloud doesn't match your server URL.

**Solution:**
1. Go to Google Cloud Console → Credentials
2. Edit your OAuth client
3. Add the exact redirect URI:
   ```
   https://your-actual-domain.com/api/oauth/callback
   ```
4. Save and try again

### "Access blocked: This app's request is invalid"

**Problem:** The OAuth consent screen isn't properly configured.

**Solution:**
1. Go to Google Cloud Console → "OAuth consent screen"
2. Make sure your app is in "Testing" mode
3. Add your Gmail address to "Test users"
4. Add the Gmail API scope: `https://www.googleapis.com/auth/gmail.modify`

### "Token expired"

**Problem:** The access token expired (they expire after 1 hour).

**Solution:**
This should refresh automatically. If it doesn't:
1. Go to "🔐 Gmail Auth" tab
2. Click "Revoke Authorization"
3. Click "Authorize Gmail" again

### "Invalid credentials"

**Problem:** The credentials.json file is malformed or for a different app type.

**Solution:**
1. Make sure you downloaded the "Web application" OAuth client (not Desktop)
2. Re-download credentials.json from Google Cloud Console
3. Make sure the redirect URIs are configured correctly

---

## Security Notes

### Files to Protect

Both `credentials.json` and `token.json` are sensitive:

```bash
# Set restrictive permissions
chmod 600 /opt/mailtagger/credentials.json
chmod 600 /opt/mailtagger/token.json
```

### .gitignore

These files are already in `.gitignore`:
```
credentials.json
token.json
```

**Never commit these files to git!**

### Server Security

Since your server is on a VPN:
- ✅ Already network isolated
- ✅ OAuth credentials only work with your configured redirect URI
- ✅ Token has limited scope (gmail.modify only)

---

## Alternative: Local Authorization

If you prefer to authorize locally and copy the token:

### Method 1: Local Desktop Authorization

```bash
# On your LOCAL machine (with browser)
python3 gmail_categorizer.py --dry-run --credentials-path ./local_credentials

# Complete OAuth in browser
# Then copy token to server:
scp ./local_credentials/token.json user@server:/opt/mailtagger/token.json
```

### Method 2: Console Flow (SSH)

```bash
# On server via SSH
cd /opt/mailtagger
python3 gmail_categorizer.py --dry-run

# It will print a URL
# Copy URL to browser, authorize, copy code back to terminal
```

But the web interface is much easier! 🎉

---

## API Endpoints

The following endpoints are available:

### Check Status
```bash
GET /api/gmail/status
```

Returns:
```json
{
  "credentials_exists": true,
  "token_exists": true,
  "authorized": true,
  "email": "your@gmail.com",
  "token_valid": true,
  "message": "Gmail is authorized and ready!"
}
```

### Start OAuth Flow
```bash
GET /api/oauth/start
```

Returns authorization URL to redirect user to.

### OAuth Callback
```bash
GET /api/oauth/callback?code=...&state=...
```

Handles Google's OAuth callback, saves token, redirects to UI.

### Revoke Authorization
```bash
POST /api/gmail/revoke
```

Deletes token.json (revokes authorization).

---

## Environment Variables

Configure in your `.env` or environment:

```bash
# OAuth redirect URI (usually auto-detected)
OAUTH_REDIRECT_URI=https://hanweir.146sharon.com/api/oauth/callback

# Credentials path
CREDENTIALS_PATH=/opt/mailtagger
```

---

## Docker Setup

If using Docker, mount your credentials:

```yaml
volumes:
  - ./credentials.json:/app/credentials.json:ro
  - ./data:/app/data  # token.json saved here
```

Then use the web interface as normal.

---

## Summary

With the new web-based OAuth flow:

1. ✅ **No SSH needed** - authorize through the browser
2. ✅ **No manual token copying** - everything handled automatically
3. ✅ **Visual status** - see authorization status at a glance
4. ✅ **Easy to revoke** - one-click deauthorization
5. ✅ **Works on remote servers** - perfect for VPN deployments

Just set up your OAuth client once, click "Authorize Gmail", and you're done! 🚀

