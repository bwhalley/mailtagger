#!/bin/bash
# Diagnose OAuth setup issues

echo "====================================="
echo "  Mailtagger OAuth Diagnostics"
echo "====================================="
echo ""

cd /home/brian/mailtagger

echo "1. Checking credentials.json on host..."
if [ -f "data/credentials.json" ]; then
    echo "   ✅ Found: data/credentials.json"
    
    # Check type and client_id
    TYPE=$(cat data/credentials.json | python3 -c "import sys, json; d=json.load(sys.stdin); print('web' if 'web' in d else 'desktop' if 'installed' in d else 'unknown')")
    CLIENT_ID=$(cat data/credentials.json | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('web', d.get('installed', {})).get('client_id', 'NOT FOUND'))")
    
    echo "   Type: $TYPE"
    echo "   Client ID: $CLIENT_ID"
    
    if [ "$TYPE" = "web" ]; then
        echo "   ✅ Correct type (web application)"
    else
        echo "   ❌ WRONG TYPE! Need 'web' application, got '$TYPE'"
        echo "   → Create new OAuth client as 'Web application' in Google Cloud Console"
    fi
    
    if [[ $CLIENT_ID == *"jh7i3"* ]]; then
        echo "   ✅ Using NEW client ID (...jh7i3)"
    elif [[ $CLIENT_ID == *"7hq3dl"* ]]; then
        echo "   ❌ Using OLD client ID (...7hq3dl)"
        echo "   → Replace with new credentials.json"
    else
        echo "   ⚠️  Unknown client ID: $CLIENT_ID"
    fi
else
    echo "   ❌ NOT FOUND: data/credentials.json"
    echo "   → Copy credentials.json to /home/brian/mailtagger/data/"
fi

echo ""
echo "2. Checking credentials.json in API container..."
docker exec -it mailtagger-api test -f /app/data/credentials.json && {
    echo "   ✅ Found in container: /app/data/credentials.json"
    
    CONTAINER_CLIENT_ID=$(docker exec -it mailtagger-api python3 -c "import json; d=json.load(open('/app/data/credentials.json')); print(d.get('web', d.get('installed', {})).get('client_id', 'NOT FOUND'))" 2>/dev/null)
    echo "   Container Client ID: $CONTAINER_CLIENT_ID"
    
    if [ "$CLIENT_ID" = "$CONTAINER_CLIENT_ID" ]; then
        echo "   ✅ MATCH: Container has same credentials as host"
    else
        echo "   ❌ MISMATCH: Container has different credentials!"
        echo "   → Rebuild container with: docker-compose build --no-cache prompt-api"
    fi
} || {
    echo "   ❌ NOT FOUND in container"
    echo "   → Check docker-compose.yml volume mount"
}

echo ""
echo "3. Checking API health..."
curl -s http://localhost:8000/health | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"   Status: {d.get('status', 'unknown')}\")
    print(f\"   Gmail available: {d.get('gmail_available', False)}\")
    print(f\"   OAuth available: {d.get('oauth_available', False)}\")
    if d.get('oauth_available'):
        print('   ✅ OAuth libraries loaded')
    else:
        print('   ❌ OAuth libraries NOT available')
except:
    print('   ❌ API not responding')
" || echo "   ❌ API not reachable"

echo ""
echo "4. Checking Gmail authorization status..."
curl -s http://localhost:8000/api/gmail/status | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"   Credentials exist: {d.get('credentials_exists', False)}\")
    print(f\"   Token exists: {d.get('token_exists', False)}\")
    print(f\"   Authorized: {d.get('authorized', False)}\")
    print(f\"   Token valid: {d.get('token_valid', False)}\")
    if d.get('message'):
        print(f\"   Message: {d['message']}\")
except:
    print('   ❌ Cannot check status')
"

echo ""
echo "5. Checking container status..."
docker ps --filter "name=mailtagger" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "====================================="
echo "  Diagnosis Complete"
echo "====================================="
echo ""
echo "If you see issues above, run:"
echo "  1. Fix credentials.json type (must be 'web')"
echo "  2. Ensure correct client_id (...jh7i3)"
echo "  3. Rebuild: docker-compose build --no-cache"
echo "  4. Restart: docker-compose up -d"
echo ""

