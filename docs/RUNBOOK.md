# Runbook

## Starting the Stack

### Option A: Podman Compose (recommended)

```bash
podman compose up -d
```

Services started:
- `qdrant` — vector database on port 6333 (internal)
- `memory-server` — FastMCP server on port 8000
- `dashboard` — web UI on port 8080

### Option B: Manual (development)

```bash
# 1. Qdrant
podman run -d --name qdrant -p 6333:6333 \
  -v qdrant_data:/qdrant/storage qdrant/qdrant

# 2. Memory server
uv run python server.py

# 3. Dashboard (separate terminal)
uv run uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```

## Health Checks

| Service | Endpoint | Expected |
|---------|----------|----------|
| Memory server | `GET http://localhost:8000/health` | `{"status":"ok"}` |
| Qdrant | `GET http://localhost:6333/` | `{"title":"qdrant"}` |
| Dashboard | `GET http://localhost:8080/` | HTML 200 |

```bash
# Quick health sweep
curl -s http://localhost:8000/health | python -m json.tool
curl -s http://localhost:6333/ | python -m json.tool
```

## Common Issues

### Qdrant connection refused

```
RuntimeError: Cannot connect to Qdrant at http://localhost:6333 after 5 attempts
```

**Fix:** Qdrant is not running. Start it:
```bash
podman run -d --name qdrant -p 6333:6333 qdrant/qdrant
# or
podman compose up -d qdrant
```

### Embedding model download slow / rate-limited

**Fix:** Set a Hugging Face token to get higher rate limits:
```bash
export HF_TOKEN=hf_your_token_here
uv run python server.py
```

### Port already in use

```
ERROR: [Errno 48] Address already in use
```

**Fix:** Find and stop the conflicting process:
```bash
lsof -i :8000   # or :8080, :6333
kill <PID>
```

### Pydantic V1 warning on Python 3.14

```
UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14
```

**This is a warning only** — it comes from `langchain-core` internals and does not affect functionality. Safe to ignore.

## Stopping the Stack

```bash
# Compose
podman compose down

# Manual
podman stop qdrant && podman rm qdrant
```

## Wiping Memory Data

```bash
# Remove Qdrant volume (deletes all stored memories)
podman compose down -v
# or
podman volume rm qdrant_data
```

## Logs

```bash
# Compose
podman compose logs -f memory-server
podman compose logs -f dashboard

# Manual (server logs to stdout)
```

## MCP Integration Verification

After the server is running, verify tool discovery:

```bash
# List available tools via MCP
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python -m json.tool
```

Expected: four tools listed — `remember`, `recall`, `forget`, `list_memories`.
