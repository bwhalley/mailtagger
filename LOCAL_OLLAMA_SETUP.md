# Using Local Ollama Instance

This project has been configured to use your local Ollama instance instead of running Ollama in a Docker container.

## Configuration Changes

The `docker-compose.yml` has been modified to:
- **Removed** the `ollama` service (no longer needed)
- **Updated** `mailtagger` and `prompt-api` services to use `network_mode: host`
- **Changed** `OLLAMA_URL` to `http://localhost:11434/v1/chat/completions`

## Requirements

1. **Ollama must be running** on the host system before starting the containers
2. **Ollama must be accessible** on `localhost:11434`

## Starting Services

```bash
# Ensure Ollama is running
systemctl status ollama.service

# If not running, start it:
sudo systemctl start ollama.service

# Start Mailtagger services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f mailtagger
```

## Verifying Ollama Connection

Test that containers can reach Ollama:

```bash
# From inside a container
docker exec mailtagger-app curl -s http://localhost:11434/api/tags

# Should return JSON with available models
```

## Important Notes

- With `network_mode: host`, the containers share the host's network stack
- Port mappings are ignored for services using `network_mode: host`
- The `prompt-api` service will be accessible on `http://localhost:8000`
- The `prompt-ui` service still uses port mapping and is accessible on `http://localhost:8080`

## Troubleshooting

### Containers can't connect to Ollama

1. Verify Ollama is running:
   ```bash
   systemctl status ollama.service
   curl http://localhost:11434/api/tags
   ```

2. Check if Ollama is listening on the correct interface:
   ```bash
   sudo netstat -tlnp | grep 11434
   # Should show 0.0.0.0:11434 or 127.0.0.1:11434
   ```

3. If Ollama is only listening on 127.0.0.1, that's fine with `network_mode: host`

### Port Conflicts

If you get port conflicts:
- Port 8000: Used by `prompt-api` (via network_mode: host)
- Port 8080: Used by `prompt-ui` (via port mapping)
- Port 11434: Used by your local Ollama instance

## Switching Back to Containerized Ollama

If you want to use Ollama in a container instead:

1. Restore the `ollama` service in `docker-compose.yml`
2. Remove `network_mode: host` from `mailtagger` and `prompt-api`
3. Change `OLLAMA_URL` back to `http://ollama:11434/v1/chat/completions`
4. Add back `depends_on: ollama` to services that need it

