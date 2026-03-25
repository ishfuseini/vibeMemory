# Deployment Guide

Production deployment of vibeMemory to a VPS. Ports 8000 (MCP) and 8080 (dashboard) are exposed directly — put a reverse proxy or Cloudflare Tunnel in front when ready.

## Prerequisites

- A VPS running Linux (Ubuntu 22.04+ recommended)
- Docker with Compose plugin installed (`apt install docker.io docker-compose-v2`)

---

## 1. Clone the repository

```bash
git clone <repo-url> /opt/vibeMemory
cd /opt/vibeMemory
```

---

## 2. Create the `.env` file

```bash
cp .env.example .env
```

Generate strong random values for each variable:

```bash
echo "VIBEMEMORY_API_KEY=$(openssl rand -hex 32)"
echo "DASHBOARD_PASSWORD=$(openssl rand -base64 16)"
echo "STORAGE_SECRET=$(openssl rand -hex 32)"
```

Paste the output into `.env`:

```env
VIBEMEMORY_API_KEY=<generated>
DASHBOARD_PASSWORD=<generated>
STORAGE_SECRET=<generated>
```

> **Important:** Never commit `.env` — it is listed in `.gitignore`.

---

## 3. Start the stack

```bash
docker compose up -d
```

Services:

| Service | Port | Public |
|---------|------|--------|
| qdrant | 6333 | No — internal only |
| memory-server | 8000 | Yes |
| dashboard | 8080 | Yes |

---

## 4. Verify the deployment

```bash
# Health check (no auth required)
curl -s http://YOUR_VPS_IP:8000/health | python3 -m json.tool
# Expected: {"status": "ok", ...}

# Dashboard
open http://YOUR_VPS_IP:8080
# Expected: password prompt, then the memory browser

# MCP server (requires API key)
curl -s http://YOUR_VPS_IP:8000/mcp \
  -H "Authorization: Bearer $VIBEMEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 -m json.tool
# Expected: four tools listed — remember, recall, forget, list_memories
```

---

## 5. Configure your MCP client

### Claude Code

Add to `~/.claude/mcp.json` (or your project-level `mcp.json`):

```json
{
  "mcpServers": {
    "vibeMemory": {
      "type": "http",
      "url": "http://YOUR_VPS_IP:8000/mcp",
      "headers": {
        "Authorization": "Bearer <your VIBEMEMORY_API_KEY>"
      }
    }
  }
}
```

### Cursor

In Settings → MCP → Add Server:

```
URL:  http://YOUR_VPS_IP:8000/mcp
Header name:  Authorization
Header value: Bearer <your VIBEMEMORY_API_KEY>
```

---

## 6. View logs

```bash
docker compose logs -f memory-server
docker compose logs -f dashboard
```

---

## 7. Updating

```bash
git pull
docker compose build
docker compose up -d
```

Only the services whose images changed will restart.

---

## 8. Rotating secrets

1. Generate new values with `openssl rand -hex 32`
2. Update `.env`
3. Restart affected services:

```bash
docker compose up -d memory-server dashboard
```

> Rotating `STORAGE_SECRET` invalidates all active dashboard sessions — users will need to log in again.

---

## 9. Backup

Qdrant data lives in the `qdrant_data` Docker volume. To back it up:

```bash
docker run --rm \
  -v qdrant_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant-$(date +%Y%m%d).tar.gz -C /data .
```

To restore:

```bash
docker compose down
docker run --rm \
  -v qdrant_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant-<date>.tar.gz -C /data
docker compose up -d
```

---

## 10. Troubleshooting

### Dashboard shows 500 on startup

```
RuntimeError: STORAGE_SECRET environment variable must be set
```

The `STORAGE_SECRET` variable is missing from `.env`. Set it and restart:

```bash
docker compose up -d dashboard
```

### MCP server returns 401

The `Authorization` header is missing or the key does not match `VIBEMEMORY_API_KEY`. Verify with:

```bash
curl -v http://YOUR_VPS_IP:8000/mcp \
  -H "Authorization: Bearer $VIBEMEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Qdrant unreachable from memory-server or dashboard

```
RuntimeError: Cannot connect to Qdrant at http://qdrant:6333
```

Check Qdrant health:

```bash
docker compose ps qdrant
docker compose logs qdrant
```

Both `memory-server` and `dashboard` wait for Qdrant's healthcheck before starting. If manually restarted:

```bash
docker compose restart memory-server dashboard
```
