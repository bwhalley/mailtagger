#!/bin/bash
# Initialize Ollama and pull required models for mailtagger

set -e  # Exit on error

echo "🚀 Initializing Ollama for Mailtagger..."
echo ""

# Configuration
CONTAINER_NAME="mailtagger-ollama"
DEFAULT_MODEL="llama3.1:8b"
MODEL="${OLLAMA_MODEL:-$DEFAULT_MODEL}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi

echo "✓ Docker is running"

# Check if Ollama container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ Error: Ollama container '${CONTAINER_NAME}' not found${NC}"
    echo "Run 'docker-compose up -d ollama' first"
    exit 1
fi

echo "✓ Ollama container found"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}⚠️  Ollama container is not running, starting it...${NC}"
    docker start "${CONTAINER_NAME}"
    sleep 5
fi

echo "✓ Ollama container is running"
echo ""

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to be ready..."
MAX_WAIT=30
WAITED=0
while ! docker exec "${CONTAINER_NAME}" curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -e "${RED}❌ Error: Ollama did not become ready in ${MAX_WAIT} seconds${NC}"
        exit 1
    fi
    echo -n "."
    sleep 1
    WAITED=$((WAITED + 1))
done
echo ""
echo -e "${GREEN}✓ Ollama is ready${NC}"
echo ""

# Check if model already exists
echo "🔍 Checking if model '${MODEL}' is already installed..."
if docker exec "${CONTAINER_NAME}" ollama list | grep -q "${MODEL}"; then
    echo -e "${GREEN}✓ Model '${MODEL}' is already installed${NC}"
    echo ""
    echo "Model details:"
    docker exec "${CONTAINER_NAME}" ollama list | grep "${MODEL}" || true
    echo ""
    echo "To reinstall, run: docker exec ${CONTAINER_NAME} ollama rm ${MODEL}"
    exit 0
fi

# Pull the model
echo -e "${YELLOW}📥 Pulling model '${MODEL}'...${NC}"
echo "This may take a while depending on model size and internet connection..."
echo ""

if docker exec "${CONTAINER_NAME}" ollama pull "${MODEL}"; then
    echo ""
    echo -e "${GREEN}✓ Model '${MODEL}' pulled successfully!${NC}"
    echo ""
    
    # Show model info
    echo "Installed models:"
    docker exec "${CONTAINER_NAME}" ollama list
    echo ""
    
    echo -e "${GREEN}🎉 Ollama initialization complete!${NC}"
    echo ""
    echo "You can now start the mailtagger service:"
    echo "  docker-compose up -d mailtagger"
    echo ""
    echo "To pull additional models:"
    echo "  docker exec ${CONTAINER_NAME} ollama pull <model-name>"
    echo ""
    echo "Popular models:"
    echo "  - llama3.1:8b      (Fast, good quality)"
    echo "  - mistral:7b       (Fast, very good)"
    echo "  - qwen2.5:14b      (Slower, excellent)"
    echo "  - llama3.1:70b     (Slow, best quality, requires 40GB+ RAM)"
else
    echo ""
    echo -e "${RED}❌ Error: Failed to pull model '${MODEL}'${NC}"
    echo ""
    echo "Common issues:"
    echo "  - Network connectivity problems"
    echo "  - Insufficient disk space"
    echo "  - Invalid model name"
    echo ""
    echo "Available models: https://ollama.ai/library"
    exit 1
fi

