#!/bin/bash
# Setup script for Mailtagger Docker deployment

set -e  # Exit on error

echo "🚀 Mailtagger Docker Setup"
echo "=========================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Step 1: Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo "✓ Docker is installed"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi
echo "✓ Docker Compose is installed"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Step 2: Create data directory
echo -e "${BLUE}Step 2: Creating data directory...${NC}"
echo ""

if [ ! -d "data" ]; then
    mkdir -p data
    chmod 700 data
    echo "✓ Created data/ directory"
else
    echo "✓ data/ directory already exists"
fi
echo ""

# Step 3: Check for credentials
echo -e "${BLUE}Step 3: Checking for Gmail credentials...${NC}"
echo ""

CREDENTIALS_FOUND=true

if [ ! -f "data/credentials.json" ]; then
    echo -e "${YELLOW}⚠️  data/credentials.json not found${NC}"
    CREDENTIALS_FOUND=false
else
    echo "✓ credentials.json found"
fi

if [ ! -f "data/token.json" ]; then
    echo -e "${YELLOW}⚠️  data/token.json not found${NC}"
    echo "  (This will be created on first run via OAuth)"
else
    echo "✓ token.json found"
fi

if [ "$CREDENTIALS_FOUND" = false ]; then
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  IMPORTANT: Gmail API credentials required!${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "To get Gmail API credentials:"
    echo "  1. Go to: https://console.cloud.google.com/"
    echo "  2. Create a new project (or select existing)"
    echo "  3. Enable the Gmail API"
    echo "  4. Create OAuth 2.0 credentials (Desktop app)"
    echo "  5. Download credentials as 'credentials.json'"
    echo "  6. Copy to: data/credentials.json"
    echo ""
    echo "For token.json (OAuth token):"
    echo "  - Run the app once locally with browser access"
    echo "  - Or run: docker-compose run --rm mailtagger python3 gmail_categorizer.py --dry-run"
    echo "  - Complete OAuth flow in browser"
    echo "  - token.json will be created in data/"
    echo ""
    
    read -p "Press Enter when credentials.json is ready (or Ctrl+C to exit)..." 
    
    if [ ! -f "data/credentials.json" ]; then
        echo -e "${RED}❌ credentials.json still not found in data/${NC}"
        exit 1
    fi
    echo ""
    echo "✓ credentials.json detected"
fi
echo ""

# Step 4: Create or check .env file
echo -e "${BLUE}Step 4: Checking environment configuration...${NC}"
echo ""

if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "✓ Created .env from env.example"
        echo -e "${YELLOW}  Please review and edit .env file if needed${NC}"
    else
        echo -e "${YELLOW}⚠️  No env.example found, skipping .env creation${NC}"
    fi
else
    echo "✓ .env file already exists"
fi
echo ""

# Step 5: Build Docker images
echo -e "${BLUE}Step 5: Building Docker images...${NC}"
echo ""

if docker-compose build; then
    echo ""
    echo "✓ Docker images built successfully"
else
    echo ""
    echo -e "${RED}❌ Failed to build Docker images${NC}"
    exit 1
fi
echo ""

# Step 6: Start Ollama
echo -e "${BLUE}Step 6: Starting Ollama service...${NC}"
echo ""

if docker-compose up -d ollama; then
    echo "✓ Ollama service started"
    echo "  Waiting for Ollama to be ready..."
    sleep 10
else
    echo -e "${RED}❌ Failed to start Ollama${NC}"
    exit 1
fi
echo ""

# Step 7: Pull Ollama model
echo -e "${BLUE}Step 7: Initializing Ollama model...${NC}"
echo ""

if [ -x "$SCRIPT_DIR/init-ollama.sh" ]; then
    if "$SCRIPT_DIR/init-ollama.sh"; then
        echo "✓ Ollama model initialized"
    else
        echo -e "${YELLOW}⚠️  Ollama model initialization had issues${NC}"
        echo "  You may need to pull the model manually:"
        echo "  docker exec mailtagger-ollama ollama pull llama3.1:8b"
    fi
else
    echo -e "${YELLOW}⚠️  init-ollama.sh not found or not executable${NC}"
    echo "  You may need to pull the model manually:"
    echo "  docker exec mailtagger-ollama ollama pull llama3.1:8b"
fi
echo ""

# Step 8: Final checks
echo -e "${BLUE}Step 8: Final checks...${NC}"
echo ""

# Check if Ollama is healthy
if docker exec mailtagger-ollama curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is responding"
else
    echo -e "${YELLOW}⚠️  Ollama is not responding yet${NC}"
fi

# Check if model is loaded
if docker exec mailtagger-ollama ollama list 2>/dev/null | grep -q "llama"; then
    echo "✓ At least one model is loaded"
else
    echo -e "${YELLOW}⚠️  No models detected${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup Complete! 🎉${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the mailtagger service:"
echo -e "   ${BLUE}docker-compose up -d mailtagger${NC}"
echo ""
echo "2. View logs:"
echo -e "   ${BLUE}docker-compose logs -f mailtagger${NC}"
echo ""
echo "3. Check status:"
echo -e "   ${BLUE}docker-compose ps${NC}"
echo ""
echo "4. Stop services:"
echo -e "   ${BLUE}docker-compose down${NC}"
echo ""
echo "Useful commands:"
echo -e "  ${BLUE}docker-compose restart mailtagger${NC}  # Restart mailtagger"
echo -e "  ${BLUE}docker-compose logs -f${NC}             # View all logs"
echo -e "  ${BLUE}docker exec mailtagger-ollama ollama list${NC}  # List models"
echo ""
echo "Documentation:"
echo "  - DOCKER.md - Docker deployment guide"
echo "  - DAEMON_MODE_GUIDE.md - Daemon usage guide"
echo ""

