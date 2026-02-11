#!/bin/bash
# Fix ERR_SSL_PROTOCOL_ERROR on hanweir.146sharon.com

set -e

DOMAIN="${1:-hanweir.146sharon.com}"
CERT_DIR="${2:-/opt/mailtagger/ssl}"
NGINX_CONF="/etc/nginx/sites-available/mailtagger"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================"
echo "Fixing ERR_SSL_PROTOCOL_ERROR"
echo "================================================"
echo ""

# Check 1: Is nginx installed?
echo "1. Checking if nginx is installed..."
if ! command -v nginx > /dev/null 2>&1; then
    echo -e "${RED}✗ Nginx is not installed${NC}"
    echo "Installing nginx..."
    sudo apt update
    sudo apt install -y nginx
    echo -e "${GREEN}✓ Nginx installed${NC}"
else
    echo -e "${GREEN}✓ Nginx is installed${NC}"
fi
echo ""

# Check 2: Is nginx running?
echo "2. Checking nginx status..."
if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx is running${NC}"
else
    echo -e "${YELLOW}⚠ Nginx is not running${NC}"
    echo "Starting nginx..."
    sudo systemctl start nginx
    sudo systemctl enable nginx
    echo -e "${GREEN}✓ Nginx started${NC}"
fi
echo ""

# Check 3: Do certificate files exist?
echo "3. Checking SSL certificate files..."
if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
    echo -e "${GREEN}✓ Certificate files exist${NC}"
    ls -lh "$CERT_DIR/fullchain.pem" "$CERT_DIR/privkey.pem"
    
    # Check permissions
    PRIV_PERMS=$(stat -c %a "$CERT_DIR/privkey.pem" 2>/dev/null || stat -f %A "$CERT_DIR/privkey.pem")
    if [ "$PRIV_PERMS" != "600" ]; then
        echo -e "${YELLOW}⚠ Fixing private key permissions${NC}"
        sudo chmod 600 "$CERT_DIR/privkey.pem"
    fi
else
    echo -e "${RED}✗ Certificate files missing${NC}"
    echo "Generating new self-signed certificate..."
    
    sudo mkdir -p "$CERT_DIR"
    
    sudo openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=HomeServer/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost"
    
    sudo chmod 600 "$CERT_DIR/privkey.pem"
    sudo chmod 644 "$CERT_DIR/fullchain.pem"
    
    echo -e "${GREEN}✓ Certificate generated${NC}"
fi
echo ""

# Check 4: Is nginx configured correctly?
echo "4. Checking nginx configuration..."
if [ -f "$NGINX_CONF" ]; then
    echo -e "${GREEN}✓ Nginx config exists${NC}"
    
    # Verify certificate paths in config
    if grep -q "$CERT_DIR/fullchain.pem" "$NGINX_CONF" && grep -q "$CERT_DIR/privkey.pem" "$NGINX_CONF"; then
        echo -e "${GREEN}✓ Certificate paths are correct in config${NC}"
    else
        echo -e "${YELLOW}⚠ Certificate paths may be incorrect${NC}"
        echo "Expected paths:"
        echo "  ssl_certificate $CERT_DIR/fullchain.pem;"
        echo "  ssl_certificate_key $CERT_DIR/privkey.pem;"
    fi
    
    # Test nginx configuration
    if sudo nginx -t > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Nginx configuration is valid${NC}"
    else
        echo -e "${RED}✗ Nginx configuration has errors:${NC}"
        sudo nginx -t
        exit 1
    fi
else
    echo -e "${RED}✗ Nginx config not found at $NGINX_CONF${NC}"
    echo "You need to install the nginx configuration"
    exit 1
fi
echo ""

# Check 5: Is nginx listening on port 443?
echo "5. Checking if nginx is listening on port 443..."
if sudo netstat -tlnp 2>/dev/null | grep -q ":443.*nginx" || sudo ss -tlnp 2>/dev/null | grep -q ":443.*nginx"; then
    echo -e "${GREEN}✓ Nginx is listening on port 443${NC}"
    sudo netstat -tlnp 2>/dev/null | grep :443 || sudo ss -tlnp 2>/dev/null | grep :443
else
    echo -e "${RED}✗ Nothing listening on port 443${NC}"
    echo "Restarting nginx..."
    sudo systemctl restart nginx
    sleep 2
    
    if sudo netstat -tlnp 2>/dev/null | grep -q ":443.*nginx" || sudo ss -tlnp 2>/dev/null | grep -q ":443.*nginx"; then
        echo -e "${GREEN}✓ Nginx now listening on port 443${NC}"
    else
        echo -e "${RED}✗ Still not listening. Check nginx error log:${NC}"
        sudo tail -20 /var/log/nginx/error.log
        exit 1
    fi
fi
echo ""

# Check 6: Firewall
echo "6. Checking firewall..."
if command -v ufw > /dev/null 2>&1; then
    if sudo ufw status | grep -q "Status: active"; then
        if sudo ufw status | grep -q "443.*ALLOW"; then
            echo -e "${GREEN}✓ Port 443 is allowed in firewall${NC}"
        else
            echo -e "${YELLOW}⚠ Port 443 not explicitly allowed${NC}"
            echo "Opening port 443..."
            sudo ufw allow 443/tcp
            sudo ufw allow 80/tcp
            echo -e "${GREEN}✓ Ports opened${NC}"
        fi
    else
        echo -e "${BLUE}ℹ Firewall (ufw) is inactive${NC}"
    fi
else
    echo -e "${BLUE}ℹ ufw not installed${NC}"
fi
echo ""

# Check 7: Test SSL locally on server
echo "7. Testing SSL connection locally..."
if timeout 5 openssl s_client -connect localhost:443 -servername $DOMAIN < /dev/null 2>&1 | grep -q "CONNECTED"; then
    echo -e "${GREEN}✓ SSL handshake successful locally${NC}"
else
    echo -e "${RED}✗ SSL handshake failed locally${NC}"
    echo "Check nginx error log:"
    sudo tail -20 /var/log/nginx/error.log
    exit 1
fi
echo ""

# Check 8: Restart nginx to apply any fixes
echo "8. Restarting nginx to apply changes..."
sudo systemctl restart nginx
sleep 2

if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx restarted successfully${NC}"
else
    echo -e "${RED}✗ Nginx failed to start${NC}"
    sudo systemctl status nginx
    exit 1
fi
echo ""

echo "================================================"
echo "✅ Fix Complete!"
echo "================================================"
echo ""
echo "Test from your Mac:"
echo "  curl -k -I https://$DOMAIN/"
echo ""
echo "Or open in browser:"
echo "  https://$DOMAIN/"
echo ""
echo "If you still see errors, check:"
echo "  sudo tail -f /var/log/nginx/error.log"
echo "  sudo tail -f /var/log/nginx/mailtagger_error.log"
echo ""
