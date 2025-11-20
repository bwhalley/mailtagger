# HTTPS Setup for Local VPN Server

This guide will help you set up HTTPS with a self-signed certificate for your Mailtagger deployment on hanweir.146sharon.com.

## Overview

Since your server is only accessible on your local VPN, a self-signed certificate is the appropriate solution. This provides encryption without the need for a public certificate authority.

## Prerequisites

On your Ubuntu server, you'll need:
- `openssl` (usually pre-installed)
- `nginx` (recommended) or another reverse proxy

## Option 1: Using Nginx (Recommended)

### Step 1: Generate SSL Certificate

On your **local machine**:

```bash
cd /Users/brian/Downloads/mailtagger
chmod +x scripts/generate-ssl-cert.sh
./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl
```

Or directly on the **server**:

```bash
cd /opt/mailtagger  # or wherever your app is deployed
mkdir -p ssl

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout ssl/privkey.pem \
    -out ssl/fullchain.pem \
    -subj "/C=US/ST=State/L=City/O=HomeServer/CN=hanweir.146sharon.com" \
    -addext "subjectAltName=DNS:hanweir.146sharon.com,DNS:localhost"

chmod 600 ssl/privkey.pem
chmod 644 ssl/fullchain.pem
```

### Step 2: Install Nginx (if not already installed)

```bash
sudo apt update
sudo apt install nginx -y
```

### Step 3: Copy Nginx Configuration

Copy the `nginx-ssl.conf` file to your server:

```bash
# From your local machine
scp /Users/brian/Downloads/mailtagger/nginx-ssl.conf \
    user@hanweir.146sharon.com:/tmp/

# On the server
sudo mv /tmp/nginx-ssl.conf /etc/nginx/sites-available/mailtagger
sudo ln -s /etc/nginx/sites-available/mailtagger /etc/nginx/sites-enabled/
```

### Step 4: Update Paths in Nginx Config

Edit `/etc/nginx/sites-available/mailtagger` and update:
- SSL certificate paths (if different from `/opt/mailtagger/ssl/`)
- Web root path (if different from `/opt/mailtagger/web/`)
- API proxy port (if not `8000`)

### Step 5: Test and Restart Nginx

```bash
# Test configuration
sudo nginx -t

# If test passes, restart nginx
sudo systemctl restart nginx

# Enable nginx to start on boot
sudo systemctl enable nginx
```

### Step 6: Update API Configuration

Make sure your API server is listening on localhost (not 0.0.0.0):

```bash
# In your .env file or docker-compose.yml
HOST=127.0.0.1  # Only accept connections from nginx
PORT=8000
```

### Step 7: Update Web UI API URL

Edit `/opt/mailtagger/web/app.js` to use HTTPS:

```javascript
// Change from:
const API_URL = 'http://localhost:8000';

// To:
const API_URL = window.location.origin;  // Use same protocol as page
```

Or explicitly:
```javascript
const API_URL = 'https://hanweir.146sharon.com';
```

### Step 8: Restart Services

```bash
# Restart API server
sudo systemctl restart mailtagger-api  # or however you run it

# Nginx should already be running from step 5
```

## Option 2: Direct HTTPS with Python (Alternative)

If you don't want to use nginx, you can serve HTTPS directly with Python:

### Step 1: Generate Certificate (same as above)

```bash
cd /opt/mailtagger
mkdir -p ssl
# Run the openssl command from Option 1, Step 1
```

### Step 2: Update API Server to Use HTTPS

Modify your API startup to use SSL:

```python
# In api.py or your startup script
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="/opt/mailtagger/ssl/privkey.pem",
        ssl_certfile="/opt/mailtagger/ssl/fullchain.pem",
        log_level="info"
    )
```

### Step 3: Serve Web UI with HTTPS

```bash
cd /opt/mailtagger/web

# Using Python's built-in server with SSL
python3 -m http.server 8080 \
    --bind 0.0.0.0 \
    --directory . \
    --protocol HTTP/1.1
```

For HTTPS with Python's http.server, you'll need a small wrapper script:

```python
# https_server.py
import http.server
import ssl
import sys

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server_address = ('0.0.0.0', port)

httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
httpd.socket = ssl.wrap_socket(httpd.socket,
                                server_side=True,
                                certfile='/opt/mailtagger/ssl/fullchain.pem',
                                keyfile='/opt/mailtagger/ssl/privkey.pem',
                                ssl_version=ssl.PROTOCOL_TLS)

print(f"Serving HTTPS on port {port}...")
httpd.serve_forever()
```

Run it:
```bash
cd /opt/mailtagger/web
python3 ../https_server.py 443  # Requires sudo for port 443
```

## Browser Setup

### Accept Self-Signed Certificate

When you first visit `https://hanweir.146sharon.com`, your browser will show a security warning. This is expected for self-signed certificates.

**Chrome/Edge:**
1. Click "Advanced"
2. Click "Proceed to hanweir.146sharon.com (unsafe)"

**Firefox:**
1. Click "Advanced"
2. Click "Accept the Risk and Continue"

**Safari:**
1. Click "Show Details"
2. Click "visit this website"
3. Click "Visit Website" again

### Optional: Add Certificate to Trust Store (More Permanent)

**On macOS:**
```bash
# Copy certificate from server
scp user@hanweir.146sharon.com:/opt/mailtagger/ssl/fullchain.pem ~/Downloads/

# Add to keychain
sudo security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain ~/Downloads/fullchain.pem
```

**On Linux:**
```bash
sudo cp /opt/mailtagger/ssl/fullchain.pem /usr/local/share/ca-certificates/hanweir.crt
sudo update-ca-certificates
```

**On Windows:**
1. Copy certificate to your Windows machine
2. Double-click the certificate file
3. Click "Install Certificate"
4. Select "Local Machine"
5. Choose "Place all certificates in the following store"
6. Browse to "Trusted Root Certification Authorities"
7. Click OK and Finish

## Firewall Configuration

Make sure your firewall allows HTTPS traffic:

```bash
# Using ufw
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp  # For HTTP redirect
sudo ufw reload

# Using firewalld
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

## Testing

### Test from Command Line

```bash
# Test HTTPS connection (accepting self-signed cert)
curl -k https://hanweir.146sharon.com/

# Test API
curl -k https://hanweir.146sharon.com/api/prompt
```

### Test from Browser

1. Open `https://hanweir.146sharon.com`
2. Accept the certificate warning
3. You should see the Mailtagger web interface
4. Test the API functionality

## Troubleshooting

### "Connection Reset" or "ERR_CONNECTION_REFUSED"

- Check nginx is running: `sudo systemctl status nginx`
- Check API server is running: `ps aux | grep api.py`
- Check firewall rules: `sudo ufw status`

### "SSL Protocol Error"

- Verify certificate files exist and have correct permissions
- Check nginx error log: `sudo tail -f /var/log/nginx/mailtagger_error.log`
- Test nginx config: `sudo nginx -t`

### API Calls Not Working

- Check browser console for errors
- Verify API_URL in `app.js` points to the correct HTTPS URL
- Check CORS settings in `api.py`

### Certificate Expired

Self-signed certificates expire after 365 days. Regenerate:

```bash
cd /opt/mailtagger
./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl
sudo systemctl restart nginx
```

## Docker Deployment

If using Docker, update your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./web:/usr/share/nginx/html:ro
    depends_on:
      - api
    restart: unless-stopped

  api:
    build: .
    expose:
      - "8000"
    environment:
      - HOST=0.0.0.0
      - PORT=8000
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

## Security Notes

1. **Self-signed certificates provide encryption** but not identity verification
2. **Only use self-signed certs for internal/VPN services**
3. **Never expose this to the public internet** without a proper CA-signed certificate
4. **Keep your private key secure**: Only root and the web server should have access
5. **Rotate certificates annually**: Set a calendar reminder

## Summary

With this setup, you'll have:
- ✅ Encrypted HTTPS connections
- ✅ Automatic HTTP to HTTPS redirect
- ✅ Secure API proxying through nginx
- ✅ Proper security headers
- ✅ Valid for 1 year (self-signed)

Your Mailtagger instance will be securely accessible at `https://hanweir.146sharon.com`!

