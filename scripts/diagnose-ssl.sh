#!/bin/bash
# SSL Connection Diagnostic Script for Mailtagger

DOMAIN="${1:-hanweir.146sharon.com}"
PORT_HTTP=80
PORT_HTTPS=443

echo "================================================"
echo "SSL Connection Diagnostics for $DOMAIN"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: DNS Resolution
echo "1. Testing DNS resolution..."
if host $DOMAIN > /dev/null 2>&1; then
    IP=$(host $DOMAIN | grep "has address" | awk '{print $4}' | head -1)
    echo -e "${GREEN}✓ DNS resolves to: $IP${NC}"
else
    echo -e "${RED}✗ DNS resolution failed${NC}"
    echo "  Make sure you're connected to your VPN"
    exit 1
fi
echo ""

# Test 2: Port Connectivity
echo "2. Testing port connectivity..."
if timeout 5 bash -c "echo > /dev/tcp/$DOMAIN/$PORT_HTTP" 2>/dev/null; then
    echo -e "${GREEN}✓ Port $PORT_HTTP (HTTP) is reachable${NC}"
else
    echo -e "${RED}✗ Port $PORT_HTTP (HTTP) is NOT reachable${NC}"
fi

if timeout 5 bash -c "echo > /dev/tcp/$DOMAIN/$PORT_HTTPS" 2>/dev/null; then
    echo -e "${GREEN}✓ Port $PORT_HTTPS (HTTPS) is reachable${NC}"
else
    echo -e "${RED}✗ Port $PORT_HTTPS (HTTPS) is NOT reachable${NC}"
    echo "  Check firewall settings on server"
    exit 1
fi
echo ""

# Test 3: Certificate Information
echo "3. Checking SSL certificate..."
CERT_INFO=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SSL certificate found${NC}"
    echo ""
    echo -e "${BLUE}Certificate Details:${NC}"
    
    # Subject (who the cert is issued to)
    SUBJECT=$(echo "$CERT_INFO" | grep "Subject:" | sed 's/.*Subject: //')
    echo "  Subject: $SUBJECT"
    
    # Issuer (who signed it)
    ISSUER=$(echo "$CERT_INFO" | grep "Issuer:" | sed 's/.*Issuer: //')
    echo "  Issuer: $ISSUER"
    
    # Valid dates
    echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null | sed 's/^/  /'
    
    # Check if self-signed
    if echo "$CERT_INFO" | grep -q "CA:TRUE"; then
        echo -e "  ${YELLOW}⚠ Certificate is self-signed${NC}"
    fi
    
    # Check if expired
    if ! echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -checkend 0 > /dev/null 2>&1; then
        echo -e "  ${RED}✗ Certificate is EXPIRED${NC}"
    else
        echo -e "  ${GREEN}✓ Certificate is valid (not expired)${NC}"
    fi
else
    echo -e "${RED}✗ Could not retrieve SSL certificate${NC}"
    exit 1
fi
echo ""

# Test 4: Certificate Verification
echo "4. Testing certificate verification..."
VERIFY_OUTPUT=$(echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>&1)

if echo "$VERIFY_OUTPUT" | grep -q "Verify return code: 0"; then
    echo -e "${GREEN}✓ Certificate is trusted by system${NC}"
elif echo "$VERIFY_OUTPUT" | grep -q "self signed certificate"; then
    echo -e "${YELLOW}⚠ Certificate is self-signed and NOT trusted${NC}"
    echo "  This is expected for local VPN setup"
    echo "  You need to add it to your Mac's keychain"
elif echo "$VERIFY_OUTPUT" | grep -q "unable to verify"; then
    echo -e "${YELLOW}⚠ Certificate verification failed${NC}"
    VERIFY_CODE=$(echo "$VERIFY_OUTPUT" | grep "Verify return code:" | sed 's/.*Verify return code: //')
    echo "  Verify code: $VERIFY_CODE"
else
    echo -e "${YELLOW}⚠ Unknown verification status${NC}"
fi
echo ""

# Test 5: HTTP to HTTPS Redirect
echo "5. Testing HTTP to HTTPS redirect..."
REDIRECT=$(curl -s -o /dev/null -w "%{http_code}" -L http://$DOMAIN/ 2>/dev/null)
if [ "$REDIRECT" = "200" ]; then
    echo -e "${GREEN}✓ HTTP redirects to HTTPS successfully${NC}"
elif [ "$REDIRECT" = "301" ] || [ "$REDIRECT" = "302" ]; then
    echo -e "${GREEN}✓ HTTP redirect configured (${REDIRECT})${NC}"
else
    echo -e "${YELLOW}⚠ Unexpected redirect response: $REDIRECT${NC}"
fi
echo ""

# Test 6: HTTPS Connection Test
echo "6. Testing HTTPS connection (ignoring certificate)..."
HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://$DOMAIN/ 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ HTTPS connection successful (HTTP $HTTP_CODE)${NC}"
    echo "  Server is responding correctly"
else
    echo -e "${RED}✗ HTTPS connection failed (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# Test 7: API Health Check
echo "7. Testing API endpoint..."
API_RESPONSE=$(curl -k -s -w "\n%{http_code}" https://$DOMAIN/health 2>/dev/null)
API_CODE=$(echo "$API_RESPONSE" | tail -1)
API_BODY=$(echo "$API_RESPONSE" | head -1)

if [ "$API_CODE" = "200" ]; then
    echo -e "${GREEN}✓ API is responding (HTTP $API_CODE)${NC}"
    echo "  Response: $API_BODY"
else
    echo -e "${RED}✗ API endpoint failed (HTTP $API_CODE)${NC}"
fi
echo ""

# Test 8: Check if Certificate is in Mac Keychain
echo "8. Checking Mac keychain..."
if command -v security > /dev/null 2>&1; then
    if security find-certificate -a -c "$DOMAIN" -p /Library/Keychains/System.keychain > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Certificate found in System keychain${NC}"
        
        # Check trust settings
        TRUST_SETTINGS=$(security dump-trust-settings 2>/dev/null | grep -A 5 "$DOMAIN" || echo "")
        if [ -n "$TRUST_SETTINGS" ]; then
            echo "  Trust settings configured"
        else
            echo -e "${YELLOW}⚠ Certificate in keychain but trust settings may not be configured${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Certificate NOT found in System keychain${NC}"
        echo "  You need to add and trust the certificate on your Mac"
    fi
else
    echo -e "${YELLOW}⚠ Not running on macOS, skipping keychain check${NC}"
fi
echo ""

echo "================================================"
echo "Diagnostic Summary"
echo "================================================"
echo ""

# Provide recommendations
if echo "$VERIFY_OUTPUT" | grep -q "self signed certificate"; then
    echo -e "${YELLOW}🔧 ACTION REQUIRED: Trust the self-signed certificate${NC}"
    echo ""
    echo "On your Mac, run these commands:"
    echo ""
    echo -e "${BLUE}# 1. Download the certificate${NC}"
    echo "  curl -k https://$DOMAIN/ --output /dev/null --stderr - 2>&1 | sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' > ~/Downloads/${DOMAIN}.pem"
    echo ""
    echo -e "${BLUE}# 2. Or copy from server${NC}"
    echo "  scp user@${DOMAIN}:/opt/mailtagger/ssl/fullchain.pem ~/Downloads/${DOMAIN}.pem"
    echo ""
    echo -e "${BLUE}# 3. Add to keychain and trust${NC}"
    echo "  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/Downloads/${DOMAIN}.pem"
    echo ""
    echo -e "${BLUE}# 4. Restart your browser${NC}"
    echo "  Completely quit and reopen your browser"
    echo ""
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Everything looks good!${NC}"
    echo ""
    echo "If you're still seeing SSL errors in your browser:"
    echo "1. Clear browser cache (Cmd+Shift+Delete)"
    echo "2. Close and reopen browser completely"
    echo "3. Try visiting: https://$DOMAIN/"
else
    echo -e "${RED}⚠ Server issues detected${NC}"
    echo ""
    echo "SSH to your server and check:"
    echo "  sudo systemctl status nginx"
    echo "  sudo nginx -t"
    echo "  docker compose ps"
    echo "  docker compose logs -f"
fi
echo ""

# Browser-specific instructions
echo "================================================"
echo "Browser Certificate Acceptance"
echo "================================================"
echo ""
echo -e "${BLUE}Chrome/Edge:${NC}"
echo "  Click 'Advanced' → 'Proceed to $DOMAIN (unsafe)'"
echo ""
echo -e "${BLUE}Firefox:${NC}"
echo "  Click 'Advanced' → 'Accept the Risk and Continue'"
echo ""
echo -e "${BLUE}Safari:${NC}"
echo "  Click 'Show Details' → 'visit this website' → 'Visit Website'"
echo ""
