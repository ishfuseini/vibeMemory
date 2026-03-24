# vibeMemory — Implementation Plan

## Requirements

Build a self-hosted local memory stack consisting of:

1. **Memory MCP Server** (`server.py`): FastMCP Python server exposing `remember`, `recall`, `forget`, and `list_memories` tools over streamable HTTP on port 8000. Uses Qdrant for vector storage, FastEmbed for local embeddings, and LangGraph for text normalization. Supports scope-based filtering and merge-on-similarity for writes. **IDE-agnostic** — any MCP-compatible editor (Cursor, VS Code + extensions, Windsurf, Zed, etc.) can connect.

2. **Memory Dashboard** (`dashboard/`): FastAPI-backed web app on port 8080 that proxies browser-safe REST endpoints to the memory server. UI uses shared `ui.css` daisyUI theme and Chart.js for score distribution visualizations. Supports scope switching, semantic search, browse-all, and per-memory deletion.

3. **Containerization**: `Containerfile` for both services, `compose.yaml` for full-stack orchestration with Qdrant on a shared pod network.

4. **MCP Configuration**: Provide a `mcp.json` at the project root with the streamable HTTP transport endpoint `http://localhost:8000/mcp`. Users copy or reference this file in their IDE's MCP config location (e.g., `.cursor/mcp.json`, `.vscode/settings.json`, etc.).

---

## Implementation Phases

### Phase 1: Project Scaffolding & Dependencies

**Goal**: Establish file structure, dependencies, and configuration files.

- **Step 1.1** — Populate `requirements.txt` (root)
  - File: `requirements.txt`
  - Add: `fastmcp`, `qdrant-client`, `fastembed`, `langgraph`, `langchain-core`, `uvicorn`, `httpx`

- **Step 1.2** — Populate dashboard `requirements.txt`
  - File: `dashboard/requirements.txt`
  - Add: `fastapi`, `uvicorn`, `httpx`

- **Step 1.3** — Create `mcp.json` (IDE-agnostic MCP config)
  - File: `mcp.json` (project root)
  - Define streamable HTTP transport: `http://localhost:8000/mcp`
  - Document how users adapt this to their IDE:
    - Cursor: copy to `.cursor/mcp.json`
    - VS Code (MCP extension): reference in settings
    - Windsurf/Zed: paste into their MCP config panel

- **Step 1.4** — Copy `ui.css` into dashboard static assets
  - Copy `/Users/ifuseini/Code/spec/ui.css` → `dashboard/static/ui.css`

---

### Phase 2: Memory Server Implementation

**Goal**: Implement the full MCP server with Qdrant persistence and all four tools.

- **Step 2.1** — FastMCP server bootstrap
  - File: `server.py`
  - Create FastMCP app named `vibeMemory`
  - Configure streamable HTTP transport on port 8000
  - Add `/health` endpoint returning readiness status
  - Initialize Qdrant client connection (default `localhost:6333`)
  - Create `memories` collection with vector config on startup

- **Step 2.2** — Embedding & normalization setup
  - File: `server.py`
  - Initialize FastEmbed model (e.g., `BAAI/bge-small-en-v1.5` for CPU-friendliness)
  - Implement LangGraph normalization workflow: trim whitespace, truncate to max length, lowercase
  - Create helper functions: `normalize_text()`, `embed_text()`

- **Step 2.3** — Implement `remember` tool
  - File: `server.py`
  - Accept: `text` (required), `scope` (default `"default"`), `tags` (optional list), `source` (optional)
  - Normalize text via LangGraph workflow
  - Generate embedding
  - Query Qdrant within scope for similarity above configurable threshold (e.g., 0.92)
  - If match found: update existing point payload, return `{merged: true, id, ...}`
  - If no match: insert new point with payload `{text, scope, tags, source, created_at}`, return `{merged: false, id, ...}`

- **Step 2.4** — Implement `recall` tool
  - File: `server.py`
  - Accept: `query` (required), `scope` (default `"default"`), `limit` (default 5)
  - Embed query text
  - Search Qdrant with scope filter, return ranked results with: `id`, `score`, `text`, `scope`, `tags`, `created_at`

- **Step 2.5** — Implement `forget` and `list_memories` tools
  - File: `server.py`
  - `forget(id)`: Delete point by UUID from Qdrant, return deletion confirmation
  - `list_memories(scope, limit)`: Scroll Qdrant by scope filter, return all matching records without semantic ranking

---

### Phase 3: Dashboard Implementation

**Goal**: Build the FastAPI proxy and browser UI.

- **Step 3.1** — Dashboard FastAPI shim
  - File: `dashboard/app.py`
  - Create FastAPI app on port 8080
  - Serve static files from `static/`
  - Implement `GET /api/memories?scope=&limit=` → proxy to memory server `list_memories`
  - Implement `POST /api/recall` with body `{query, scope, limit}` → proxy to memory server `recall`
  - Implement `DELETE /api/memories/{id}` → proxy to memory server `forget`
  - Implement `GET /api/scopes` → extract unique scopes from list_memories results
  - Memory server URL: configurable via env var `MEMORY_SERVER_URL` (default `http://localhost:8000`)

- **Step 3.2** — Dashboard HTML/JS UI
  - File: `dashboard/static/index.html`
  - Single-page HTML with inline JS (vanilla, no framework)
  - Link `ui.css` daisyUI theme and Chart.js CDN
  - Layout: header, scope selector dropdown, search bar, memory cards list, score distribution chart
  - Implement fetch calls to `/api/memories`, `/api/recall`, `/api/scopes`, `DELETE /api/memories/{id}`
  - Implement scope switching: dropdown onChange → reload memories + chart
  - Implement search: input + button → POST `/api/recall` → display results
  - Implement browse reset: "Browse All" button → GET `/api/memories`
  - Implement delete: per-card delete button → DELETE → remove from DOM + refresh chart
  - Chart.js: bar chart of score distribution from recall results

---

### Phase 4: Containerization & Compose

**Goal**: Make the stack reproducible with containers.

- **Step 4.1** — Server Containerfile
  - File: `Containerfile`
  - Base: `python:3.12-slim`
  - Copy `requirements.txt`, install deps
  - Copy `server.py`
  - Expose port 8000
  - CMD: `uvicorn server:app --host 0.0.0.0 --port 8000`

- **Step 4.2** — Dashboard Containerfile
  - File: `dashboard/Containerfile`
  - Base: `python:3.12-slim`
  - Copy `requirements.txt`, install deps
  - Copy `app.py` and `static/`
  - Expose port 8080
  - CMD: `uvicorn app:app --host 0.0.0.0 --port 8080`

- **Step 4.3** — Compose file
  - File: `compose.yaml`
  - Services: `qdrant` (image: `qdrant/qdrant`, port 6333 internal), `memory-server` (build `.`, port 8000), `dashboard` (build `dashboard/`, port 8080)
  - Shared network
  - Environment: `MEMORY_SERVER_URL=http://memory-server:8000` for dashboard, `QDRANT_URL=http://qdrant:6333` for server
  - Volumes: `qdrant_data` for persistence

---

### Phase 5: Verification & Integration Testing

**Goal**: Validate the full stack works end-to-end.

- **Step 5.1** — Server health & collection init
  - Start stack, verify `GET http://localhost:8000/health` returns 200
  - Verify Qdrant `memories` collection exists

- **Step 5.2** — Tool verification via MCP or direct HTTP
  - `remember("Test memory", scope="test")` → verify stored in Qdrant
  - `remember("Test memorie", scope="test")` → verify merge occurs (similar text)
  - `remember("Different scope memory", scope="other")` → verify scope isolation
  - `recall("test", scope="test")` → verify ranked results
  - `list_memories(scope="test")` → verify browse results
  - `forget(id)` → verify deletion

- **Step 5.3** — Dashboard verification
  - Open `http://localhost:8080`, verify UI renders with daisyUI theme
  - Verify scope dropdown populates
  - Verify search returns results
  - Verify delete removes memory
  - Verify Chart.js renders score distribution

- **Step 5.4** — MCP integration (IDE-agnostic)
  - Verify `mcp.json` transport config is correct
  - Verify any MCP-compatible client can discover `vibeMemory` service and its four tools via `http://localhost:8000/mcp`

---

## Dependencies

| Dependency                     | Purpose                        | Source                             |
| ------------------------------ | ------------------------------ | ---------------------------------- |
| `fastmcp`                      | MCP server framework           | PyPI                               |
| `qdrant-client`                | Qdrant vector DB client        | PyPI                               |
| `fastembed`                    | Local embedding generation     | PyPI                               |
| `langgraph` / `langchain-core` | Normalization workflow         | PyPI                               |
| `fastapi` / `uvicorn`          | Dashboard HTTP server          | PyPI                               |
| `httpx`                        | Async HTTP client for proxying | PyPI                               |
| `qdrant/qdrant` image          | Vector database                | Docker Hub                         |
| `ui.css`                       | daisyUI theme                  | `/Users/ifuseini/Code/spec/ui.css` |
| Chart.js (CDN)                 | Score distribution charts      | CDN                                |
| Podman / Docker                | Container runtime              | Local install                      |

---

## Risks

- **HIGH**: FastEmbed model download on first run — may be slow, document warm-up behavior
- **HIGH**: Merge threshold tuning — too low causes unintended merges, too high defeats purpose; make configurable
- **MEDIUM**: Qdrant connection on startup — server must handle Qdrant not being ready yet (retry logic)
- **MEDIUM**: Port conflicts — 8000, 8080, 6333 may already be in use on developer machines
- **LOW**: `ui.css` not in repo — external dependency at `/Users/ifuseini/Code/spec/ui.css`, must copy into project
- **LOW**: FastMCP transport specifics — streamable HTTP transport may have different config than assumed; verify against latest docs

---

## Estimated Complexity

**MEDIUM-HIGH** — Approximately 4-6 hours of focused implementation:

| Phase                     | Estimate    |
| ------------------------- | ----------- |
| Phase 1: Scaffolding      | 15-20 min   |
| Phase 2: Memory Server    | 2-3 hours   |
| Phase 3: Dashboard        | 1.5-2 hours |
| Phase 4: Containerization | 30-45 min   |
| Phase 5: Verification     | 30-45 min   |

---

## Success Criteria

- [ ] Server starts on port 8000, `/health` returns 200
- [ ] `remember` stores and merges memories correctly within scope
- [ ] `recall` returns scoped, ranked semantic results
- [ ] `forget` and `list_memories` work as specified
- [ ] Dashboard renders with daisyUI theme and Chart.js
- [ ] Dashboard can list, search, and delete memories
- [ ] `compose.yaml` brings up full stack (Qdrant + server + dashboard)
- [ ] MCP client discovers `vibeMemory` service via `http://localhost:8000/mcp`
