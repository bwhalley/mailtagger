#!/bin/bash
# Quick setup script for HTTPS on Ubuntu server
# Run this on your hanweir.146sharon.com server

set -e

DOMAIN="${1:-hanweir.146sharon.com}"
APP_DIR="${2:-/opt/mailtagger}"

echo "================================================"
echo "Mailtagger HTTPS Setup Script"
echo "================================================"
echo "Domain: $DOMAIN"
echo "App Directory: $APP_DIR"
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./setup-https-server.sh)"
    exit 1
fi

echo "Step 1: Installing nginx..."
apt update
apt install -y nginx

echo ""
echo "Step 2: Generating self-signed SSL certificate..."
mkdir -p "$APP_DIR/ssl"

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$APP_DIR/ssl/privkey.pem" \
    -out "$APP_DIR/ssl/fullchain.pem" \
    -subj "/C=US/ST=State/L=City/O=HomeServer/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost"

chmod 600 "$APP_DIR/ssl/privkey.pem"
chmod 644 "$APP_DIR/ssl/fullchain.pem"

echo ""
echo "Step 3: Configuring nginx..."

# Update nginx config with actual paths
sed -e "s|/opt/mailtagger|$APP_DIR|g" \
    -e "s|hanweir.146sharon.com|$DOMAIN|g" \
    "$APP_DIR/nginx-ssl.conf" > /etc/nginx/sites-available/mailtagger

# Enable site
ln -sf /etc/nginx/sites-available/mailtagger /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Remove default site

echo ""
echo "Step 4: Testing nginx configuration..."
nginx -t

echo ""
echo "Step 5: Restarting nginx..."
systemctl restart nginx
systemctl enable nginx

echo ""
echo "Step 6: Configuring firewall (if ufw is active)..."
if command -v ufw &> /dev/null; then
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "Firewall rules added for ports 80 and 443"
fi

echo ""
echo "Step 7: Updating web UI configuration..."
if [ -f "$APP_DIR/web/app.js" ]; then
    # Update API URL to use relative path (same protocol as page)
    sed -i.bak 's|http://localhost:8000|window.location.origin|g' "$APP_DIR/web/app.js"
    echo "Updated app.js to use HTTPS"
fi

echo ""
echo "================================================"
echo "✅ HTTPS Setup Complete!"
echo "================================================"
echo ""
echo "Your site is now available at: https://$DOMAIN"
echo ""
echo "Next steps:"
echo "  1. Visit https://$DOMAIN in your browser"
echo "  2. Accept the self-signed certificate warning"
echo "  3. Bookmark the HTTPS URL for future use"
echo ""
echo "Certificate files:"
echo "  - Certificate: $APP_DIR/ssl/fullchain.pem"
echo "  - Private Key: $APP_DIR/ssl/privkey.pem"
echo "  - Valid for: 365 days"
echo ""
echo "Nginx configuration:"
echo "  - Config: /etc/nginx/sites-available/mailtagger"
echo "  - Logs: /var/log/nginx/mailtagger_*.log"
echo ""
echo "To check nginx status:"
echo "  sudo systemctl status nginx"
echo ""
echo "To view logs:"
echo "  sudo tail -f /var/log/nginx/mailtagger_access.log"
echo "  sudo tail -f /var/log/nginx/mailtagger_error.log"
echo ""

