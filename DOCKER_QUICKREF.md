# Docker Quick Reference - Mailtagger

## 🚀 Quick Start Commands

```bash
# Initial setup
./scripts/setup-docker.sh

# Start everything
docker-compose up -d

# View logs
docker-compose logs -f mailtagger

# Stop everything
docker-compose down
```

---

## 📋 Common Commands

### Service Management

```bash
# Start services
docker-compose up -d                    # All services in background
docker-compose up -d ollama             # Only Ollama
docker-compose up -d mailtagger         # Only mailtagger

# Stop services
docker-compose stop                     # Stop all
docker-compose stop mailtagger          # Stop mailtagger only
docker-compose down                     # Stop and remove containers

# Restart services
docker-compose restart                  # Restart all
docker-compose restart mailtagger       # Restart mailtagger only

# Rebuild and restart
docker-compose up -d --build           # Rebuild all
docker-compose up -d --build mailtagger # Rebuild mailtagger only
```

### Logs & Monitoring

```bash
# View logs
docker-compose logs                     # All logs
docker-compose logs -f                  # Follow all logs
docker-compose logs -f mailtagger       # Follow mailtagger logs
docker-compose logs --tail=100 mailtagger # Last 100 lines
docker-compose logs --since 10m         # Last 10 minutes

# Check status
docker-compose ps                       # Service status
docker stats                            # Resource usage
docker-compose top                      # Process list
```

### Running Commands

```bash
# Dry run (test without changes)
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data

# Process specific number of emails
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --max 10 --credentials-path /app/data

# Debug mode
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --log-level DEBUG --credentials-path /app/data

# Shell access
docker exec -it mailtagger-app /bin/bash
docker exec -it mailtagger-ollama /bin/bash
```

### Ollama Commands

```bash
# List models
docker exec mailtagger-ollama ollama list

# Pull new model
docker exec mailtagger-ollama ollama pull llama3.1:8b
docker exec mailtagger-ollama ollama pull mistral:7b

# Remove model
docker exec mailtagger-ollama ollama rm llama3.1:8b

# Test Ollama
docker exec mailtagger-ollama curl http://localhost:11434/api/tags
```

### Health Checks

```bash
# Check container health
docker-compose ps
docker inspect mailtagger-app --format='{{.State.Health.Status}}'

# Manual health check
docker exec mailtagger-app python3 /app/scripts/healthcheck.py

# Check Ollama health
docker exec mailtagger-ollama curl -f http://localhost:11434/api/tags
```

---

## 🔧 Configuration Changes

### Change Environment Variable

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Apply changes
docker-compose up -d
```

### Change Daemon Interval

```bash
# Option 1: Edit docker-compose.yml
environment:
  - DAEMON_INTERVAL=600  # 10 minutes

# Option 2: Override command
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --daemon --interval 600 --credentials-path /app/data
```

### Change LLM Model

```bash
# Edit docker-compose.yml
environment:
  - OLLAMA_MODEL=mistral:7b

# Pull the model
docker exec mailtagger-ollama ollama pull mistral:7b

# Restart mailtagger
docker-compose restart mailtagger
```

### Switch to OpenAI

```bash
# Edit docker-compose.yml
environment:
  - LLM_PROVIDER=openai
  - OPENAI_API_KEY=sk-your-key-here
  - OPENAI_MODEL=gpt-4o-mini

# Restart
docker-compose restart mailtagger
```

---

## 🐛 Troubleshooting

### View Error Logs

```bash
# Last 50 lines
docker-compose logs --tail=50 mailtagger

# Search for errors
docker-compose logs mailtagger | grep ERROR

# Specific time range
docker-compose logs --since 2024-01-01T10:00:00 mailtagger
```

### Container Won't Start

```bash
# Check logs
docker-compose logs mailtagger

# Try running manually
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --log-level DEBUG --credentials-path /app/data

# Check health
docker exec mailtagger-app python3 /app/scripts/healthcheck.py
```

### Ollama Issues

```bash
# Check Ollama status
docker-compose ps ollama

# Check Ollama logs
docker-compose logs ollama

# Restart Ollama
docker-compose restart ollama

# Verify model is loaded
docker exec mailtagger-ollama ollama list
```

### Token Expired

```bash
# Remove old token
rm data/token.json

# Regenerate (needs browser)
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# Use smaller model
docker exec mailtagger-ollama ollama pull llama3.1:8b-q4_0

# Edit docker-compose.yml
environment:
  - OLLAMA_MODEL=llama3.1:8b-q4_0
```

---

## 🔄 Updates & Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify
docker-compose logs -f mailtagger
```

### Backup Credentials

```bash
# Backup
tar -czf mailtagger-backup-$(date +%Y%m%d).tar.gz data/

# List backups
ls -lh mailtagger-backup-*.tar.gz

# Restore
tar -xzf mailtagger-backup-20240101.tar.gz
```

### Clean Up

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Full cleanup
docker system prune -a --volumes
```

---

## 📊 Monitoring

### Resource Usage

```bash
# Real-time stats
docker stats

# Container details
docker inspect mailtagger-app

# Disk usage
docker system df
```

### Log Analysis

```bash
# Count processed emails
docker-compose logs mailtagger | grep "Processed:" | tail -1

# Count errors
docker-compose logs mailtagger | grep ERROR | wc -l

# View categorizations
docker-compose logs mailtagger | grep "\[ecommerce\]"
docker-compose logs mailtagger | grep "\[political\]"
```

---

## 🎯 Common Workflows

### Initial Setup

```bash
./scripts/setup-docker.sh
# Follow prompts
docker-compose up -d
docker-compose logs -f mailtagger
```

### Daily Operation

```bash
# Check status
docker-compose ps

# View recent activity
docker-compose logs --tail=20 mailtagger

# Check resource usage
docker stats --no-stream
```

### Changing Configuration

```bash
# Edit configuration
nano docker-compose.yml

# Apply changes
docker-compose up -d

# Verify
docker-compose logs -f mailtagger
```

### Troubleshooting Workflow

```bash
# 1. Check status
docker-compose ps

# 2. View logs
docker-compose logs --tail=100 mailtagger

# 3. Check health
docker exec mailtagger-app python3 /app/scripts/healthcheck.py

# 4. Test manually
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --dry-run --log-level DEBUG --credentials-path /app/data

# 5. Restart if needed
docker-compose restart mailtagger
```

---

## 💡 Pro Tips

### Performance

```bash
# Check processing time per run
docker-compose logs mailtagger | grep "completed in"

# Monitor Ollama response time
docker-compose logs mailtagger | grep "received in"

# Use faster model for testing
docker exec mailtagger-ollama ollama pull mistral:7b
```

### Security

```bash
# Check file permissions
ls -la data/

# Verify no secrets in logs
docker-compose logs mailtagger | grep -i "api.key\|password\|secret"

# Audit container access
docker exec mailtagger-app whoami
docker exec mailtagger-app id
```

### Debugging

```bash
# Enable verbose logging
docker-compose run --rm mailtagger \
  python3 gmail_categorizer.py --daemon --log-level DEBUG --verbose --credentials-path /app/data

# Test specific email query
docker-compose run --rm -e GMAIL_QUERY="from:specific@email.com" mailtagger \
  python3 gmail_categorizer.py --dry-run --credentials-path /app/data

# Check Gmail API connectivity
docker exec mailtagger-app python3 -c "from gmail_categorizer import gmail_service; svc = gmail_service(); print('OK')"
```

---

## 📱 Quick Reference Card

| Task | Command |
|------|---------|
| **Start** | `docker-compose up -d` |
| **Stop** | `docker-compose down` |
| **Restart** | `docker-compose restart mailtagger` |
| **Logs** | `docker-compose logs -f mailtagger` |
| **Status** | `docker-compose ps` |
| **Shell** | `docker exec -it mailtagger-app /bin/bash` |
| **Dry Run** | `docker-compose run --rm mailtagger python3 gmail_categorizer.py --dry-run --credentials-path /app/data` |
| **Health** | `docker exec mailtagger-app python3 /app/scripts/healthcheck.py` |
| **Models** | `docker exec mailtagger-ollama ollama list` |
| **Update** | `git pull && docker-compose up -d --build` |

---

**Bookmark this page for quick reference! 🔖**

