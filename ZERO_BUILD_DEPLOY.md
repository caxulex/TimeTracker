# 🚀 Zero-Build Deployment Guide

This guide explains how to deploy without building on the server (avoiding OOM crashes on limited Lightsail instances).

## How It Works

1. **GitHub Actions builds the images** on GitHub's powerful runners when you push to `master`
2. **Images are stored in GHCR** (GitHub Container Registry)
3. **Server only pulls pre-built images** - no npm install, no build process

## Setup (One-Time)

### 1. Push your changes to master
```bash
git add -A
git commit -m "feat: Add AI components and accessibility improvements"
git push origin master
```

### 2. Wait for GitHub Actions to complete
- Go to: https://github.com/caxulex/TimeTracker/actions
- Wait for the "Build and Push Docker Images" job to complete (✅)
- This builds the images on GitHub's servers (not your Lightsail)

### 3. Setup GHCR authentication on Lightsail (one-time)

SSH into your Lightsail server:
```bash
ssh ubuntu@100.52.110.180
```

Create a Personal Access Token on GitHub:
1. Go to: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `read:packages`
4. Copy the token

Login to GHCR:
```bash
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u caxulex --password-stdin
```

### 4. Copy the new compose file to server
```bash
scp docker-compose.prod.ghcr.yml ubuntu@100.52.110.180:/home/ubuntu/timetracker/
```

Or on the server, create/edit the file manually.

## Deploying Updates

After pushing to master and GitHub Actions completes:

```bash
# SSH to server
ssh ubuntu@100.52.110.180

# Navigate to app
cd /home/ubuntu/timetracker

# Pull and restart (NO BUILD!)
docker compose -f docker-compose.prod.ghcr.yml pull
docker compose -f docker-compose.prod.ghcr.yml down
docker compose -f docker-compose.prod.ghcr.yml up -d

# Check status
docker compose -f docker-compose.prod.ghcr.yml ps
docker logs timetracker-backend --tail 20
```

## Quick Reference

| Step | Command |
|------|---------|
| Pull new images | `docker compose -f docker-compose.prod.ghcr.yml pull` |
| Restart services | `docker compose -f docker-compose.prod.ghcr.yml down && docker compose -f docker-compose.prod.ghcr.yml up -d` |
| View logs | `docker logs timetracker-frontend --tail 50` |
| Check status | `docker compose -f docker-compose.prod.ghcr.yml ps` |

## Why This Works

| Old Method | New Method |
|------------|------------|
| Build on Lightsail (512MB-1GB RAM) | Build on GitHub Actions (7GB RAM) |
| `npm ci` uses 1GB+ RAM | Server only pulls ~200MB image |
| Server crashes during build | Server stays stable |
| Build takes 5-10 min on server | Build happens in parallel on GitHub |

## Troubleshooting

### "unauthorized" when pulling images
```bash
# Re-authenticate
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u caxulex --password-stdin
```

### Images not updated after push
- Check GitHub Actions completed: https://github.com/caxulex/TimeTracker/actions
- Force pull: `docker compose -f docker-compose.prod.ghcr.yml pull --ignore-pull-failures`

### Frontend showing old version
```bash
# Force recreate the container
docker compose -f docker-compose.prod.ghcr.yml up -d --force-recreate frontend
```
