# vibeMemory

A self-hosted local memory stack for MCP-compatible editors (Cursor, VS Code, Windsurf, Zed, etc.).

Stores, searches, and manages semantic memories backed by Qdrant vector storage — accessible via any MCP client or the included browser dashboard.

## Architecture

```
┌─────────────────────┐     MCP (streamable HTTP)      ┌──────────────────┐
│  IDE / MCP Client   │ ──────────────────────────────► │  server.py :8000 │
│  (Cursor, VS Code…) │                                 │  FastMCP tools   │
└─────────────────────┘                                 └────────┬─────────┘
                                                                 │ Qdrant client
┌─────────────────────┐     REST (browser-safe)                  ▼
│  Dashboard :8080    │ ──────────────────────────────► ┌──────────────────┐
│  FastAPI + HTML/JS  │                                 │  Qdrant :6333    │
└─────────────────────┘                                 │  (vector store)  │
                                                        └──────────────────┘
```

## Quick Start (Podman Desktop)

### 1. Start Qdrant

```bash
podman run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env if you need non-default values
```

### 3. Start the memory server

```bash
uv run python server.py
```

### 4. Verify

```bash
curl http://localhost:8000/health
```

### Full stack with Podman Compose

```bash
podman compose up -d
```

## MCP Client Setup

Copy `mcp.json` from the project root to your IDE's config location:

| Editor | Config location |
|--------|----------------|
| Cursor | `.cursor/mcp.json` |
| VS Code (MCP ext) | `.vscode/settings.json` → `"mcp.servers"` |
| Windsurf | MCP config panel |
| Zed | `~/.config/zed/settings.json` |

The endpoint is always `http://localhost:8000/mcp`.

## MCP Tools

<!-- AUTO-GENERATED from server.py -->

| Tool | Description | Required Args | Optional Args |
|------|-------------|---------------|---------------|
| `remember` | Store a memory; merges with an existing one if cosine similarity >= threshold | `text` | `scope`, `tags`, `source` |
| `recall` | Retrieve memories semantically ranked by similarity to a query | `query` | `scope`, `limit` |
| `forget` | Delete a memory by UUID | `id` | — |
| `list_memories` | Browse all memories in a scope (no semantic ranking) | — | `scope`, `limit` |

<!-- END AUTO-GENERATED -->

## Environment Variables

<!-- AUTO-GENERATED from .env.example -->

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QDRANT_URL` | No | `http://localhost:6333` | URL of the Qdrant instance |
| `QDRANT_COLLECTION` | No | `memories` | Qdrant collection name |
| `EMBED_MODEL` | No | `BAAI/bge-small-en-v1.5` | FastEmbed model (384-dim, CPU-friendly) |
| `SIMILARITY_THRESHOLD` | No | `0.92` | Cosine similarity above which memories are merged |
| `MAX_TEXT_LEN` | No | `2000` | Characters to store per memory (text is truncated) |
| `MEMORY_SERVER_URL` | No | `http://localhost:8000` | Dashboard -> memory server URL |
| `HF_TOKEN` | No | (unset) | Hugging Face token (avoids download rate limits) |

<!-- END AUTO-GENERATED -->

## Dashboard

Open `http://localhost:8080` after starting the stack. Features:

- Scope selector — switch between memory namespaces
- Semantic search — query memories by meaning
- Browse all — list all memories in a scope
- Per-memory delete — remove individual entries
- Score distribution chart (Chart.js)

## Project Structure

```
vibeMemory/
├── server.py              # FastMCP memory server (port 8000)
├── dashboard/
│   ├── app.py             # FastAPI dashboard shim (port 8080)
│   └── static/
│       ├── index.html     # Dashboard UI
│       └── ui.css         # daisyUI theme
├── Containerfile          # Memory server container image
├── dashboard/Containerfile
├── compose.yaml           # Podman Compose — full stack
├── mcp.json               # IDE-agnostic MCP client config
├── .env.example           # Environment variable reference
├── pyproject.toml         # Python project + dependencies
└── docs/                  # Design docs, specs, implementation plan
```

## Notes

- **First run**: FastEmbed downloads the embedding model (~67 MB). Subsequent starts are fast.
- **Merge threshold**: Lower `SIMILARITY_THRESHOLD` to merge more aggressively; raise it to preserve distinct memories.
- **Scope isolation**: Each `scope` value is an independent namespace — memories in `"work"` are never returned when searching `"personal"`.
