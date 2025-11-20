# Quick HTTPS Setup Guide

## TL;DR - Fastest Method

### On Your Server (hanweir.146sharon.com)

```bash
# 1. Copy files to server
cd /opt/mailtagger  # or wherever your app is

# 2. Run the automated setup script
sudo ./scripts/setup-https-server.sh hanweir.146sharon.com /opt/mailtagger

# 3. Done! Visit https://hanweir.146sharon.com
```

That's it! The script handles everything automatically.

---

## Manual Method (if you prefer)

### Step 1: Generate Certificate

```bash
cd /opt/mailtagger
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

### Step 2: Install & Configure Nginx

```bash
# Install nginx
sudo apt update && sudo apt install -y nginx

# Copy nginx config
sudo cp nginx-ssl.conf /etc/nginx/sites-available/mailtagger
sudo ln -s /etc/nginx/sites-available/mailtagger /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Update paths in config if needed
sudo nano /etc/nginx/sites-available/mailtagger

# Test and restart
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Step 3: Update Web UI

```bash
# Edit app.js to use HTTPS
nano /opt/mailtagger/web/app.js

# Change:
const API_URL = 'http://localhost:8000';
# To:
const API_URL = window.location.origin;
```

### Step 4: Open Firewall

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Step 5: Visit Your Site

Open `https://hanweir.146sharon.com` and accept the certificate warning.

---

## Copying Files to Server

From your local machine:

```bash
cd /Users/brian/Downloads/mailtagger

# Copy all necessary files
scp nginx-ssl.conf user@hanweir.146sharon.com:/opt/mailtagger/
scp scripts/setup-https-server.sh user@hanweir.146sharon.com:/opt/mailtagger/scripts/
scp scripts/generate-ssl-cert.sh user@hanweir.146sharon.com:/opt/mailtagger/scripts/

# Make scripts executable on server
ssh user@hanweir.146sharon.com "chmod +x /opt/mailtagger/scripts/*.sh"
```

---

## What the Setup Does

1. ✅ Installs nginx
2. ✅ Generates self-signed SSL certificate (valid 365 days)
3. ✅ Configures nginx with SSL
4. ✅ Sets up HTTP → HTTPS redirect
5. ✅ Configures reverse proxy for API
6. ✅ Opens firewall ports
7. ✅ Updates web UI to use HTTPS

---

## After Setup

### Access Your Site
```
https://hanweir.146sharon.com
```

### Accept Certificate in Browser
First visit will show a warning - this is normal for self-signed certificates.

**Chrome/Edge:** Click "Advanced" → "Proceed to hanweir.146sharon.com"
**Firefox:** Click "Advanced" → "Accept the Risk and Continue"
**Safari:** Click "Show Details" → "Visit this website"

### Check Status
```bash
# Nginx status
sudo systemctl status nginx

# View logs
sudo tail -f /var/log/nginx/mailtagger_access.log
sudo tail -f /var/log/nginx/mailtagger_error.log

# Test HTTPS
curl -k https://hanweir.146sharon.com/health
```

---

## Architecture

```
Browser (HTTPS) → Nginx (443)
                    ↓
    ┌──────────────┴────────────────┐
    ↓                                ↓
Web Files                     API (localhost:8000)
(/opt/mailtagger/web)        (FastAPI Backend)
```

---

## Troubleshooting

### Can't connect
```bash
# Check nginx is running
sudo systemctl status nginx

# Check firewall
sudo ufw status

# Check ports
sudo netstat -tulpn | grep -E ':(80|443)'
```

### Certificate errors
```bash
# Regenerate certificate
cd /opt/mailtagger
./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl
sudo systemctl restart nginx
```

### API not working
```bash
# Check API is running
ps aux | grep api.py

# Check nginx config
sudo nginx -t

# Check logs
sudo tail -20 /var/log/nginx/mailtagger_error.log
```

---

## Files Created

```
/opt/mailtagger/
├── ssl/
│   ├── privkey.pem          # Private key (keep secret!)
│   └── fullchain.pem        # Certificate (safe to share)
├── nginx-ssl.conf           # Nginx configuration
└── scripts/
    ├── generate-ssl-cert.sh # Certificate generator
    └── setup-https-server.sh # Automated setup
```

---

## Renewal Reminder

Self-signed certificates expire after 365 days. Set a calendar reminder!

To renew:
```bash
cd /opt/mailtagger
sudo ./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl
sudo systemctl restart nginx
```

---

## Need Help?

See the detailed guide: `HTTPS_SETUP.md`

