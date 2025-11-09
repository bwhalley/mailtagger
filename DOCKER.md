# Mailtagger Docker Deployment Guide

Complete guide for deploying Mailtagger as a Docker container on an AMD Ubuntu server with local LLM support.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)
- [Security Considerations](#security-considerations)

---

## 🎯 Prerequisites

### Hardware Requirements

**Minimum:**
- CPU: 4 cores (AMD64/x86_64)
- RAM: 8GB
- Disk: 20GB free space

**Recommended:**
- CPU: 8+ cores (AMD Ryzen 5 or better)
- RAM: 16GB+ (for comfortable operation with 8B models)
- Disk: 50GB+ free space (for multiple models)
- GPU: AMD GPU with ROCm support (optional, for acceleration)

### Software Requirements

**Required:**
- Ubuntu 20.04+ (or other Linux distro)
- Docker 20.10+
- Docker Compose 1.29+

**Optional:**
- ROCm drivers (for AMD GPU acceleration)

### Gmail API Setup

**Required before deployment:**
1. Google Cloud Console account
2. Gmail API enabled
3. OAuth 2.0 credentials (Desktop app)
4. Downloaded `credentials.json` file

See [Gmail API Setup](#gmail-api-setup-detailed) for detailed instructions.

---

## ⚡ Quick Start

### 1. Clone or Download Repository

```bash
cd /opt
git clone <repository-url> mailtagger
cd mailtagger
```

### 2. Prepare Credentials

```bash
# Create data directory
mkdir -p data
chmod 700 data

# Copy your Gmail API credentials
cp /path/to/credentials.json data/

# Note: token.json will be created on first run
```

### 3. Run Setup Script

```bash
./scripts/setup-docker.sh
```

This script will:
- Check prerequisites
- Create necessary directories
- Build Docker images
- Start Ollama
- Pull the LLM model
- Verify setup

### 4. Generate OAuth Token (First Time Only)

**Option A: Local with Browser**
```bash
# On your local machine with browser
python3 gmail_categorizer.py --credentials-path ./data --dry-run
# Complete OAuth flow in browser
# Copy data/token.json to server
```

**Option B: On Server (if you have display/browser)**
```bash
docker-compose run --rm mailtagger python3 gmail_categorizer.py --credentials-path /app/data --dry-run
# Complete OAuth flow
```

### 5. Start Services

```bash
docker-compose up -d
```

### 6. Verify

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f mailtagger
```

---

## 📖 Detailed Setup

### Gmail API Setup (Detailed)

#### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project" or select existing
3. Name it (e.g., "Gmail Categorizer")
4. Click "Create"

#### Step 2: Enable Gmail API

1. In your project, go to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click "Enable"

#### Step 3: Create OAuth Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - User Type: External (or Internal if G Suite)
   - App name: "Gmail Categorizer"
   - User support email: your email
   - Developer contact: your email
   - Scopes: Don't add any (we'll use runtime scopes)
   - Test users: Add your Gmail address
4. Create OAuth Client ID:
   - Application type: "Desktop app"
   - Name: "Gmail Categorizer Desktop"
5. Click "Create"
6. Download JSON (this is your `credentials.json`)

#### Step 4: Copy to Server

```bash
# On your local machine
scp credentials.json user@server:/opt/mailtagger/data/

# On server
chmod 600 /opt/mailtagger/data/credentials.json
```

### Docker Installation (Ubuntu)

If Docker is not installed:

```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up stable repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### Building the Images

```bash
cd /opt/mailtagger

# Build the mailtagger image
docker-compose build

# Or build with no cache
docker-compose build --no-cache
```

### Pulling Ollama Models

The setup script pulls `llama3.1:8b` by default. To use different models:

```bash
# List available models
docker exec mailtagger-ollama ollama list

# Pull additional models
docker exec mailtagger-ollama ollama pull mistral:7b
docker exec mailtagger-ollama ollama pull qwen2.5:14b

# Update docker-compose.yml to use different model
# Edit: OLLAMA_MODEL=mistral:7b
docker-compose restart mailtagger
```

**Popular models for email classification:**

| Model | Size | RAM Needed | Speed | Quality |
|-------|------|------------|-------|---------|
| llama3.1:8b | ~5GB | 8GB | Fast | Good |
| mistral:7b | ~4GB | 7GB | Very Fast | Very Good |
| qwen2.5:7b | ~4GB | 7GB | Fast | Excellent |
| qwen2.5:14b | ~8GB | 16GB | Medium | Excellent |
| llama3.1:70b | ~40GB | 64GB | Slow | Best |

---

## ⚙️ Configuration

### Environment Variables

Edit `docker-compose.yml` to configure:

```yaml
environment:
  # LLM Provider
  - LLM_PROVIDER=ollama          # or 'openai'
  - OLLAMA_URL=http://ollama:11434/v1/chat/completions
  - OLLAMA_MODEL=llama3.1:8b
  
  # For OpenAI (alternative)
  # - LLM_PROVIDER=openai
  # - OPENAI_API_KEY=sk-...
  # - OPENAI_MODEL=gpt-4o-mini
  
  # Gmail Labels
  - LABEL_ECOMMERCE=AI_Ecommerce
  - LABEL_POLITICAL=AI_Political
  - LABEL_TRIAGED=AI_Triaged
  
  # Gmail Query
  - GMAIL_QUERY=in:inbox newer_than:14d -label:AI_Triaged
  
  # Processing
  - MAX_RESULTS=40               # Emails per run
  - SLEEP_SECONDS=0.5           # Pause between emails
  
  # Daemon
  - DAEMON_INTERVAL=300          # 5 minutes between runs
  
  # Logging
  - LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR
```

### Using .env File (Alternative)

Create `.env` file in project root:

```bash
# Copy example
cp env.example .env

# Edit
nano .env
```

Update `docker-compose.yml` to use it:

```yaml
services:
  mailtagger:
    env_file:
      - .env
```

### Volume Configuration

**Credentials (Required):**
```yaml
volumes:
  - ./data:/app/data:rw
```

**Custom models path:**
```yaml
services:
  ollama:
    volumes:
      - /mnt/storage/ollama:/root/.ollama
```

### Resource Limits

Adjust based on your hardware:

```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          memory: 16G           # Increase for larger models
        reservations:
          memory: 8G
  
  mailtagger:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
```

---

## 🚀 Running the Application

### Starting Services

```bash
# Start all services in background
docker-compose up -d

# Start only Ollama
docker-compose up -d ollama

# Start only mailtagger
docker-compose up -d mailtagger

# Start in foreground (see logs live)
docker-compose up
```

### Stopping Services

```bash
# Stop all services
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

### Restarting Services

```bash
# Restart all
docker-compose restart

# Restart mailtagger only
docker-compose restart mailtagger

# Rebuild and restart
docker-compose up -d --build mailtagger
```

### Running One-Time Commands

```bash
# Dry run (no changes)
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data

# Process last 10 emails
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --max 10 --credentials-path /app/data

# Debug mode
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --log-level DEBUG --credentials-path /app/data
```

---

## 📊 Monitoring & Maintenance

### Viewing Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow mailtagger only
docker-compose logs -f mailtagger

# Last 100 lines
docker-compose logs --tail=100 mailtagger

# Logs since specific time
docker-compose logs --since 2024-01-01T10:00:00 mailtagger
```

### Health Checks

```bash
# Check container health
docker-compose ps

# Manual health check
docker exec mailtagger-app python3 /app/scripts/healthcheck.py

# Check Ollama
docker exec mailtagger-ollama curl http://localhost:11434/api/tags
```

### Container Shell Access

```bash
# Access mailtagger container
docker exec -it mailtagger-app /bin/bash

# Access Ollama container
docker exec -it mailtagger-ollama /bin/bash
```

### Updating Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify
docker-compose logs -f mailtagger
```

### Backup & Restore

#### Backup Credentials

```bash
# Backup
tar -czf mailtagger-backup-$(date +%Y%m%d).tar.gz data/

# Restore
tar -xzf mailtagger-backup-20240101.tar.gz
```

#### Backup Ollama Models

```bash
# Backup models volume
docker run --rm \
  -v mailtagger_ollama-models:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/ollama-models-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm \
  -v mailtagger_ollama-models:/data \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/ollama-models-20240101.tar.gz -C /
```

### Log Rotation

Configure Docker logging:

```yaml
services:
  mailtagger:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Ollama Not Starting

**Symptoms:** Mailtagger can't connect to Ollama

**Solutions:**
```bash
# Check Ollama logs
docker-compose logs ollama

# Verify Ollama is running
docker-compose ps

# Restart Ollama
docker-compose restart ollama

# Check if model is loaded
docker exec mailtagger-ollama ollama list
```

#### 2. OAuth Token Expired

**Symptoms:** `Failed to refresh token` in logs

**Solution:**
```bash
# Delete old token
rm data/token.json

# Regenerate (requires browser access)
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data
```

#### 3. No Emails Processed

**Symptoms:** `No threads to process` in logs

**Solutions:**
```bash
# Check query
docker-compose logs mailtagger | grep "Query:"

# Try broader query
docker-compose run --rm -e GMAIL_QUERY="in:inbox newer_than:1d" mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data

# Verify labels exist
# Check Gmail web interface for AI_Triaged label
```

#### 4. High Memory Usage

**Symptoms:** OOM errors, slow performance

**Solutions:**
```bash
# Use smaller model
# Edit docker-compose.yml: OLLAMA_MODEL=mistral:7b

# Increase Docker memory limit
# Edit /etc/docker/daemon.json or Docker Desktop settings

# Monitor memory
docker stats
```

#### 5. Container Keeps Restarting

**Symptoms:** `docker-compose ps` shows repeated restarts

**Solutions:**
```bash
# Check logs for errors
docker-compose logs --tail=50 mailtagger

# Check health checks
docker inspect mailtagger-app | grep -A 20 Health

# Run health check manually
docker exec mailtagger-app python3 /app/scripts/healthcheck.py

# Disable restart temporarily
docker-compose run --rm mailtagger python3 gmail_categorizer.py --daemon --credentials-path /app/data
```

### Debug Mode

Enable verbose logging:

```bash
# Edit docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG

# Restart
docker-compose restart mailtagger

# Or run manually
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --daemon --log-level DEBUG --verbose --credentials-path /app/data
```

### Performance Issues

```bash
# Check system resources
docker stats

# Check Docker disk usage
docker system df

# Clean up unused resources
docker system prune -a

# Check network latency to Ollama
docker exec mailtagger-app time curl http://ollama:11434/api/tags
```

---

## 🔧 Advanced Configuration

### AMD GPU Acceleration (ROCm)

If you have an AMD GPU:

1. **Install ROCm drivers:**
```bash
# For Ubuntu
wget https://repo.radeon.com/amdgpu-install/latest/ubuntu/focal/amdgpu-install_*.deb
sudo dpkg -i amdgpu-install_*.deb
sudo amdgpu-install --usecase=rocm
```

2. **Update docker-compose.yml:**
```yaml
services:
  ollama:
    devices:
      - /dev/kfd
      - /dev/dri
    environment:
      - HSA_OVERRIDE_GFX_VERSION=10.3.0  # Check your GPU version
    group_add:
      - video
      - render
```

3. **Verify GPU access:**
```bash
docker exec mailtagger-ollama rocm-smi
```

### Systemd Service (Auto-start)

Create `/etc/systemd/system/mailtagger.service`:

```ini
[Unit]
Description=Mailtagger Email Categorizer
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/mailtagger
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mailtagger
sudo systemctl start mailtagger
sudo systemctl status mailtagger
```

### Reverse Proxy (Optional)

If you want to expose Ollama API:

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name ollama.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:11434;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Important:** Add authentication if exposed to internet!

### Multi-Instance Deployment

Run multiple instances with different queries:

```bash
# Create instance directories
mkdir -p instance1 instance2

# Copy configuration
cp docker-compose.yml instance1/
cp docker-compose.yml instance2/

# Edit each docker-compose.yml
# - Change container names
# - Change GMAIL_QUERY
# - Change volume paths

# Start each instance
cd instance1 && docker-compose up -d
cd instance2 && docker-compose up -d
```

---

## 🔒 Security Considerations

### Container Security

1. **Run as non-root** (already configured in Dockerfile)

2. **Use read-only filesystem where possible:**
```yaml
services:
  mailtagger:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - ./data:/app/data:rw
```

3. **Drop capabilities:**
```yaml
services:
  mailtagger:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

### Network Security

1. **Use internal network:**
```yaml
services:
  ollama:
    networks:
      - internal
    # Don't expose ports externally
    
  mailtagger:
    networks:
      - internal

networks:
  internal:
    internal: true
```

2. **Don't expose Ollama port publicly**

### Credentials Security

1. **Protect credentials directory:**
```bash
chmod 700 data/
chmod 600 data/credentials.json
chmod 600 data/token.json
```

2. **Use Docker secrets (Swarm mode):**
```yaml
services:
  mailtagger:
    secrets:
      - gmail_credentials
    environment:
      - CREDENTIALS_FILE=/run/secrets/gmail_credentials

secrets:
  gmail_credentials:
    file: ./data/credentials.json
```

3. **Regular credential rotation:**
   - Regenerate OAuth credentials periodically
   - Monitor access logs in Google Cloud Console

### Monitoring & Alerts

Set up monitoring:
- Log aggregation (ELK, Loki)
- Metrics collection (Prometheus)
- Alerting (AlertManager, PagerDuty)

---

## 📈 Performance Tuning

### Optimize Processing Speed

```yaml
environment:
  # Process more emails per run
  - MAX_RESULTS=100
  
  # Reduce delay between emails
  - SLEEP_SECONDS=0.2
  
  # Run more frequently
  - DAEMON_INTERVAL=120
```

### Optimize for Accuracy

```yaml
environment:
  # Use larger model
  - OLLAMA_MODEL=qwen2.5:14b
  
  # Allow more time for inference
  - OPENAI_TIMEOUT=60
```

### Optimize Resource Usage

```bash
# Use quantized models (smaller, faster)
docker exec mailtagger-ollama ollama pull llama3.1:8b-q4_0

# Limit concurrent processing
# Edit MAX_RESULTS to smaller batches
```

---

## 📞 Support & Resources

### Documentation
- [Main README](README.md) - Project overview
- [Daemon Mode Guide](DAEMON_MODE_GUIDE.md) - Usage guide
- [Security Guide](SECURITY.md) - Security best practices

### Community
- GitHub Issues - Bug reports and feature requests
- GitHub Discussions - Questions and discussions

### External Resources
- [Docker Documentation](https://docs.docker.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

---

## 🎉 Success!

Your Mailtagger instance should now be running continuously, processing emails with local LLM inference!

Check status:
```bash
docker-compose ps
docker-compose logs -f mailtagger
```

Happy categorizing! 📧✨

