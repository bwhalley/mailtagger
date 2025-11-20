# Fix ERR_SSL_PROTOCOL_ERROR on Port 8080

## The Problem

You're getting `ERR_SSL_PROTOCOL_ERROR` on port 8080 because:
- Port 8080 is serving **HTTP** (not HTTPS)
- You're trying to access it with **HTTPS** in your browser
- The HTTP server can't handle HTTPS connections

## Architecture Overview

Currently you have:
```
Port 80   → nginx → HTTP (redirects to 443)
Port 443  → nginx → HTTPS ✅ (serves web + proxies API)
Port 8000 → FastAPI → HTTP (localhost only, proxied by nginx)
Port 8080 → Python http.server → HTTP ❌ (conflicts with nginx)
```

## Recommended Solution: Use Nginx Only

**Stop the Python HTTP server on port 8080 and use nginx on port 443:**

### Step 1: Stop Port 8080 Server

```bash
# SSH to your server
ssh user@hanweir.146sharon.com

# Stop the Python HTTP server
pkill -f "http.server 8080"
# or
pkill -f "python3 -m http.server 8080"
```

### Step 2: Ensure Nginx is Serving Web Files

Check that nginx configuration points to your web directory:

```bash
# Check nginx config
sudo nano /etc/nginx/sites-available/mailtagger

# Make sure this line points to your web files:
# root /opt/mailtagger/web;
```

### Step 3: Access via Standard HTTPS Port

```bash
# No port number needed!
https://hanweir.146sharon.com
```

Nginx will:
- Serve web UI from `/opt/mailtagger/web/`
- Proxy API calls to `localhost:8000`
- Handle HTTPS with your certificate

### Step 4: Restart Nginx (if you changed config)

```bash
sudo nginx -t                    # Test configuration
sudo systemctl restart nginx     # Restart if test passes
```

---

## Alternative: Access Port 8080 with HTTP

If you want to keep the Python server on 8080, use HTTP (not HTTPS):

```bash
# Use HTTP, not HTTPS
http://hanweir.146sharon.com:8080
```

But this defeats the purpose of SSL setup.

---

## Alternative: Make Port 8080 Serve HTTPS

If you specifically need HTTPS on port 8080:

### Step 1: Copy the HTTPS Server Script

```bash
# From your local machine
scp /Users/brian/Downloads/mailtagger/scripts/https-web-server.py \
    user@hanweir.146sharon.com:/opt/mailtagger/scripts/
```

### Step 2: Stop Old HTTP Server

```bash
# On server
pkill -f "http.server 8080"
```

### Step 3: Start HTTPS Server

```bash
# On server
cd /opt/mailtagger/web
python3 ../scripts/https-web-server.py 8080
```

### Step 4: Open Firewall (if needed)

```bash
sudo ufw allow 8080/tcp
```

### Step 5: Access with HTTPS

```bash
https://hanweir.146sharon.com:8080
```

---

## Troubleshooting

### Check What's Running

```bash
# See what's listening on each port
sudo netstat -tulpn | grep -E ':(80|443|8000|8080)'

# Or with ss
sudo ss -tulpn | grep -E ':(80|443|8000|8080)'
```

Expected output with nginx setup:
```
tcp  0  0  0.0.0.0:80    LISTEN  nginx
tcp  0  0  0.0.0.0:443   LISTEN  nginx
tcp  0  0  127.0.0.1:8000 LISTEN  python (api.py)
```

### Check Nginx Status

```bash
sudo systemctl status nginx
sudo nginx -t
sudo tail -20 /var/log/nginx/mailtagger_error.log
```

### Test Each Service

```bash
# Test nginx HTTPS
curl -k https://hanweir.146sharon.com/

# Test nginx API proxy
curl -k https://hanweir.146sharon.com/api/prompt

# Test API directly (from server)
curl http://localhost:8000/health
```

---

## Recommended Final Setup

For simplicity and security, use **nginx only**:

```
✅ Port 443 (HTTPS) → Nginx → Serves everything
   ├── Web UI (static files)
   └── API (proxied to localhost:8000)

✅ Port 80 (HTTP) → Nginx → Redirects to 443

✅ Port 8000 (HTTP) → FastAPI → localhost only

❌ Port 8080 → Not needed! (Stop this service)
```

### Commands to Implement This

```bash
# On your server

# 1. Stop port 8080 service
pkill -f "http.server 8080"

# 2. Ensure nginx is running
sudo systemctl status nginx
sudo systemctl restart nginx

# 3. Test it works
curl -k https://hanweir.146sharon.com/health

# 4. Access in browser (no port number!)
# https://hanweir.146sharon.com
```

---

## Why This is Better

**Using nginx only (no port 8080):**

✅ One service to manage
✅ Standard ports (443/80)
✅ Better security (API not directly exposed)
✅ Better performance (nginx is faster than Python HTTP server)
✅ No port numbers in URLs
✅ Easier firewall configuration
✅ Professional setup

**Using separate port 8080:**

❌ Extra service to manage
❌ Non-standard port in URLs
❌ More firewall rules needed
❌ More confusion
❌ No real benefit

---

## Summary

**Do this:**
1. Stop the Python HTTP server on port 8080
2. Use nginx on port 443 for everything
3. Access at `https://hanweir.146sharon.com` (no port number)

That's it! Nginx handles it all.

