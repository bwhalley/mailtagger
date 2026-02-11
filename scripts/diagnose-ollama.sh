#!/bin/bash
# Ollama Connectivity Diagnostic Script

echo "================================================"
echo "Ollama Connectivity Diagnostic"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if Ollama service is running
echo "1. Checking if Ollama service is running..."
if systemctl is-active --quiet ollama.service 2>/dev/null; then
    echo -e "${GREEN}✓ Ollama service is running${NC}"
elif ps aux | grep -v grep | grep ollama > /dev/null; then
    echo -e "${GREEN}✓ Ollama process is running (not as systemd service)${NC}"
else
    echo -e "${RED}✗ Ollama is NOT running${NC}"
    echo "  Start it with: sudo systemctl start ollama.service"
    echo "  Or: ollama serve"
    exit 1
fi
echo ""

# Test 2: Check if port 11434 is listening
echo "2. Checking if port 11434 is listening..."
if sudo netstat -tlnp 2>/dev/null | grep 11434 > /dev/null || sudo ss -tlnp 2>/dev/null | grep 11434 > /dev/null; then
    echo -e "${GREEN}✓ Port 11434 is listening${NC}"
    sudo netstat -tlnp 2>/dev/null | grep 11434 || sudo ss -tlnp 2>/dev/null | grep 11434
else
    echo -e "${RED}✗ Port 11434 is NOT listening${NC}"
    echo "  Ollama may not be configured correctly"
    exit 1
fi
echo ""

# Test 3: Test API from host
echo "3. Testing Ollama API from host..."
if curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama API is accessible from host${NC}"
    echo "  Available models:"
    curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | sed 's/^/    - /'
else
    echo -e "${RED}✗ Cannot connect to Ollama API from host${NC}"
    echo "  This is unusual if the service is running and port is listening"
    exit 1
fi
echo ""

# Test 4: Check if required model exists
echo "4. Checking if required model (gpt-oss:20b) exists..."
if curl -s http://localhost:11434/api/tags | grep -q "gpt-oss:20b"; then
    echo -e "${GREEN}✓ Model gpt-oss:20b is available${NC}"
else
    echo -e "${YELLOW}⚠ Model gpt-oss:20b NOT found${NC}"
    echo "  Download it with: ollama pull gpt-oss:20b"
    echo "  Or use a different model in docker-compose.yml"
fi
echo ""

# Test 5: Test from container (if running)
echo "5. Testing Ollama API from mailtagger container..."
if docker ps --format '{{.Names}}' | grep -q mailtagger-app; then
    if docker exec mailtagger-app curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Container can reach Ollama API${NC}"
    else
        echo -e "${RED}✗ Container CANNOT reach Ollama API${NC}"
        echo "  Check network_mode: host in docker-compose.yml"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ mailtagger-app container is not running${NC}"
    echo "  Start it with: docker compose up -d"
fi
echo ""

# Test 6: Test actual chat completion
echo "6. Testing chat completion endpoint..."
RESPONSE=$(curl -s --max-time 10 http://localhost:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"gpt-oss:20b","messages":[{"role":"user","content":"Say test"}],"max_tokens":10}' 2>&1)

if echo "$RESPONSE" | grep -q '"content"'; then
    echo -e "${GREEN}✓ Chat completion endpoint is working${NC}"
elif echo "$RESPONSE" | grep -qi "model.*not found"; then
    echo -e "${YELLOW}⚠ Chat endpoint works but model not found${NC}"
    echo "  Download it with: ollama pull gpt-oss:20b"
else
    echo -e "${RED}✗ Chat completion failed${NC}"
    echo "  Response: $RESPONSE"
fi
echo ""

echo "================================================"
echo "Diagnostic Complete"
echo "================================================"
echo ""
echo "If all tests pass, restart the mailtagger container:"
echo "  docker compose restart mailtagger"
echo ""
echo "View logs with:"
echo "  docker compose logs -f mailtagger"


