# Fix Docker Permissions

You're getting permission denied errors because your user is not in the `docker` group.

## Quick Fix

Run these commands (you'll need to enter your password for sudo):

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Apply the new group membership immediately
newgrp docker

# Verify you can now run docker commands
docker ps
```

## Alternative: Use sudo (temporary workaround)

If you can't add yourself to the docker group right now, you can use sudo:

```bash
sudo docker compose up -d
sudo docker compose ps
sudo docker compose logs -f
```

**Note:** Using sudo for docker commands is not recommended for security reasons, but it works as a temporary solution.

## After Adding to Docker Group

Once you've added yourself to the docker group and run `newgrp docker`, you can start the services:

```bash
cd /home/brian/mailtagger

# Verify Ollama is running
systemctl status ollama.service

# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f mailtagger
```

## Verify It Worked

After running `newgrp docker`, test with:

```bash
docker ps
docker compose version
```

If these work without sudo, you're all set!

