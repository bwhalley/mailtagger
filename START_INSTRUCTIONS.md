# Starting Mailtagger - Quick Start Guide

## Current Status ✅

- ✅ Data directory created (`data/`)
- ✅ Environment file created (`.env`)
- ✅ Docker Compose v2 available
- ⚠️ Docker permissions need to be configured

## Required Steps

### 1. Fix Docker Permissions

You need to add your user to the docker group to run Docker commands without sudo:

```bash
# Add user to docker group (requires your password)
sudo usermod -aG docker $USER

# Apply the new group membership
# Option A: Log out and log back in (recommended)
# Option B: Run this command in your current shell:
newgrp docker

# Verify you can run docker commands
docker ps
```

### 2. Prepare Gmail Credentials (if not already done)

Place your Gmail API credentials in the `data/` directory:

```bash
# Copy your credentials.json to:
cp /path/to/your/credentials.json /home/brian/mailtagger/data/

# Set proper permissions
chmod 600 /home/brian/mailtagger/data/credentials.json
```

**Note:** If you don't have `credentials.json` yet:
1. Go to https://console.cloud.google.com/
2. Create/select a project
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop app type)
5. Download as `credentials.json`

### 3. Start the Services

Once Docker permissions are fixed, start all services:

```bash
cd /home/brian/mailtagger

# Build and start all services
docker compose up -d

# Or use the setup script (recommended for first time)
./scripts/setup-docker.sh
```

### 4. Verify Services Are Running

```bash
# Check service status
docker compose ps

# View logs
docker compose logs -f mailtagger

# Check Ollama is ready
docker exec mailtagger-ollama ollama list
```

### 5. Generate OAuth Token (First Time Only)

If you don't have `token.json` yet, you'll need to generate it:

```bash
# Run a dry-run to trigger OAuth flow
docker compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data
```

This will open a browser for OAuth authorization. After completing it, `token.json` will be created in `data/`.

## Service Endpoints

Once running, you can access:

- **Ollama API**: `http://localhost:11434` (internal)
- **Prompt Management API**: `http://localhost:8000`
- **Prompt Management UI**: `http://localhost:8080`

## Useful Commands

```bash
# View all logs
docker compose logs -f

# Restart a service
docker compose restart mailtagger

# Stop all services
docker compose down

# Pull a different Ollama model
docker exec mailtagger-ollama ollama pull mistral:7b

# Check resource usage
docker stats
```

## Troubleshooting

### Permission Denied Errors
- Make sure you've added yourself to the docker group and logged out/in
- Verify with: `groups | grep docker`

### Ollama Not Starting
- Check logs: `docker compose logs ollama`
- Verify model is pulled: `docker exec mailtagger-ollama ollama list`

### Gmail Authentication Issues
- Check `data/credentials.json` exists and has correct permissions
- Regenerate token: `rm data/token.json` then run dry-run again

## Next Steps

After services are running:
1. Monitor logs to ensure emails are being processed
2. Access the web UI at http://localhost:8080 to manage prompts
3. Check Gmail labels to see categorized emails

For more details, see:
- `DOCKER_QUICKREF.md` - Quick command reference
- `DOCKER.md` - Complete Docker deployment guide
- `README.md` - Project overview

