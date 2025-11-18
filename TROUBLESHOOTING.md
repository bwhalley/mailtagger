# Troubleshooting Docker "docker: executable file not found" Error

If you're getting this error, try these steps:

## Step 1: Clean up existing containers and images

```bash
# Stop and remove all containers
docker compose down

# Remove the images (if they exist)
docker rmi mailtagger-mailtagger mailtagger-prompt-api 2>/dev/null || true

# Clean build cache
docker builder prune -f
```

## Step 2: Rebuild from scratch

```bash
# Build without cache
docker compose build --no-cache

# Start services
docker compose up -d
```

## Step 3: Check Docker and Docker Compose versions

```bash
docker --version
docker compose version
```

If you're using an older version, consider updating.

## Step 4: Alternative - Try without network_mode: host

If the issue persists, you can try using `host.docker.internal` instead:

1. Configure Ollama to listen on all interfaces:
   ```bash
   sudo systemctl edit ollama.service
   ```
   Add:
   ```
   [Service]
   Environment="OLLAMA_HOST=0.0.0.0:11434"
   ```
   Then:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart ollama.service
   ```

2. Update docker-compose.yml to use `host.docker.internal`:
   - Remove `network_mode: host` from services
   - Change `OLLAMA_URL` to `http://host.docker.internal:11434/v1/chat/completions`
   - Add `extra_hosts: - "host.docker.internal:host-gateway"` to services

## Step 5: Check for conflicting containers

```bash
# List all containers
docker ps -a

# Remove any conflicting containers
docker rm -f mailtagger-app mailtagger-api mailtagger-ui 2>/dev/null || true
```

## Step 6: Check Docker daemon logs

```bash
# On systemd systems
sudo journalctl -u docker.service -n 50

# Or check Docker logs
sudo tail -f /var/log/docker.log
```

