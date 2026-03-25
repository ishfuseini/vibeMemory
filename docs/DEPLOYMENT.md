# Deployment Guide

Production deployment of vibeMemory to a VPS, served over HTTPS at a custom domain via Caddy.

## Prerequisites

- A VPS running Linux (Ubuntu 22.04+ recommended)
- Docker or Podman with Compose installed
- A domain with an A record pointing to the VPS IP
- Ports 80 and 443 open in the VPS firewall

### DNS

Add an A record for your subdomain:

```
mem.ishf.dev  →  <your VPS IP>
```

Caddy handles TLS certificate issuance automatically once DNS resolves.

---

## 1. Clone the repository

```bash
git clone <repo-url> vibememory
cd vibememory
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
podman compose up -d
# or
docker compose up -d
```

Services that start:

| Service | Internal address | Public |
|---------|-----------------|--------|
| qdrant | qdrant:6333 | No — internal only |
| memory-server | memory-server:8000 | Via Caddy at `/mcp` |
| dashboard | dashboard:8080 | Via Caddy at `/` |
| caddy | — | Ports 80, 443 |

Caddy requests a Let's Encrypt TLS certificate on first start. This requires port 80 to be reachable for the ACME HTTP-01 challenge.

---

## 4. Verify the deployment

```bash
# Health check (no auth required)
curl -s https://mem.ishf.dev/health | python3 -m json.tool
# Expected: {"status": "ok", ...}

# Dashboard
open https://mem.ishf.dev
# Expected: password prompt, then the memory browser

# MCP server (requires API key)
curl -s https://mem.ishf.dev/mcp \
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
      "url": "https://mem.ishf.dev/mcp",
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
URL:  https://mem.ishf.dev/mcp
Header name:  Authorization
Header value: Bearer <your VIBEMEMORY_API_KEY>
```

---

## 6. View logs

```bash
podman compose logs -f memory-server
podman compose logs -f dashboard
podman compose logs -f caddy
```

---

## 7. Updating

```bash
git pull
podman compose build
podman compose up -d
```

Only the services whose images changed will restart.

---

## 8. Rotating secrets

1. Generate new values with `openssl rand -hex 32`
2. Update `.env`
3. Restart affected services:

```bash
podman compose up -d memory-server dashboard
```

> Rotating `STORAGE_SECRET` invalidates all active dashboard sessions — users will need to log in again.

---

## 9. Backup

Qdrant data lives in the `qdrant_data` Docker volume. To back it up:

```bash
podman run --rm \
  -v qdrant_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant-$(date +%Y%m%d).tar.gz -C /data .
```

To restore:

```bash
podman compose down
podman run --rm \
  -v qdrant_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/qdrant-<date>.tar.gz -C /data
podman compose up -d
```

---

## 10. Troubleshooting

### Caddy fails to get TLS certificate

```
error obtaining certificate: ...
```

- Confirm DNS A record is pointing to the VPS IP (`dig mem.ishf.dev`)
- Confirm port 80 is open in the VPS firewall
- Check Caddy logs: `podman compose logs caddy`

### Dashboard shows 500 on startup

```
RuntimeError: STORAGE_SECRET environment variable must be set
```

The `STORAGE_SECRET` variable is missing from `.env`. Set it and restart:

```bash
podman compose up -d dashboard
```

### MCP server returns 401

The `Authorization` header is missing or the key does not match `VIBEMEMORY_API_KEY`. Verify with:

```bash
curl -v https://mem.ishf.dev/mcp \
  -H "Authorization: Bearer $VIBEMEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Qdrant unreachable from memory-server or dashboard

```
RuntimeError: Cannot connect to Qdrant at http://qdrant:6333
```

Qdrant may still be starting up. Check its health:

```bash
podman compose ps qdrant
podman compose logs qdrant
```

Both `memory-server` and `dashboard` wait for Qdrant's healthcheck before starting, but if the container was manually restarted they may need a nudge:

```bash
podman compose restart memory-server dashboard
```
