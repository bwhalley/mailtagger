#!/bin/bash
# Fix nginx domain configuration for mailtagger and n8n

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================"
echo "Nginx Domain Configuration Fix"
echo "================================================"
echo ""

echo -e "${BLUE}Current configuration:${NC}"
echo ""
echo "Checking mailtagger config..."
sudo grep "server_name" /etc/nginx/sites-available/mailtagger | head -2
echo ""
echo "Checking n8n config..."
sudo grep "server_name" /etc/nginx/sites-available/n8n 2>/dev/null | head -2 || echo "n8n config not found"
echo ""

echo -e "${YELLOW}Recommended setup:${NC}"
echo "  - Mailtagger: hanweir.146sharon.com (main domain)"
echo "  - n8n: n8n.hanweir.146sharon.com (subdomain)"
echo ""

read -p "Do you want to apply this configuration? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Updating mailtagger config to use main domain..."
    sudo sed -i 's/server_name mailtagger\.hanweir\.146sharon\.com;/server_name hanweir.146sharon.com;/g' /etc/nginx/sites-available/mailtagger
    
    echo "Updating n8n config to use subdomain..."
    if [ -f /etc/nginx/sites-available/n8n ]; then
        sudo sed -i 's/server_name hanweir\.146sharon\.com;/server_name n8n.hanweir.146sharon.com;/g' /etc/nginx/sites-available/n8n
    fi
    
    echo ""
    echo "Testing nginx configuration..."
    if sudo nginx -t; then
        echo -e "${GREEN}✓ Configuration is valid${NC}"
        echo ""
        echo "Restarting nginx..."
        sudo systemctl restart nginx
        echo -e "${GREEN}✓ Nginx restarted${NC}"
        echo ""
        echo -e "${GREEN}Done!${NC}"
        echo ""
        echo "Access your services at:"
        echo "  - Mailtagger: https://hanweir.146sharon.com/"
        echo "  - n8n: https://n8n.hanweir.146sharon.com/"
        echo ""
        echo "Note: For n8n subdomain to work, you need DNS or /etc/hosts entry"
    else
        echo -e "${RED}✗ Configuration has errors${NC}"
        exit 1
    fi
else
    echo "Configuration not changed."
fi
