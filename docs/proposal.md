## Why

Cursor can connect to MCP servers, but this project does not yet provide a local memory service that stores and retrieves semantic memories for a developer's workspace. Adding a self-hosted memory stack now gives the project a concrete, reproducible path for persistent recall using Podman, Qdrant, and a small Python MCP server.

## What Changes

- Add a local `vibeMemory` MCP service that exposes `remember`, `recall`, `forget`, and `list_memories` tools over streamable HTTP.
- Add a Qdrant-backed persistence layer for semantic memory storage with scope-based filtering, metadata payloads, and merge-on-similarity behavior for writes.
- Add a lightweight dashboard served from a companion web app that uses the existing [ui.css](/Users/ifuseini/Code/spec/ui.css) daisyUI theme and Chart.js visualizations to browse, search, and delete memories.
- Add container and dependency definitions so the memory server, dashboard, and Qdrant can run locally in Podman or Compose.
- Add project configuration for Cursor to connect to the MCP endpoint through `.cursor/mcp.json`.
- Add operational guidance for building, running, and testing the local memory stack.

## Capabilities

### New Capabilities
- `cursor-memory-server`: Provides the local `vibeMemory` MCP-compatible memory service for storing, retrieving, listing, and deleting scoped semantic memories backed by Qdrant.
- `memory-dashboard`: Provides a local dashboard for browsing memory state, viewing score-based summaries, and managing memories through the MCP-backed API.

### Modified Capabilities

## Impact

- Adds new project files such as `server.py`, `requirements.txt`, `Containerfile`, `.cursor/mcp.json`, `compose.yaml`, and dashboard application files under `dashboard/`.
- Introduces runtime dependencies on FastMCP, LangGraph, FastEmbed, Qdrant, FastAPI, httpx, daisyUI theme assets from `ui.css`, and Chart.js.
- Requires local container runtime support through Podman and a reachable Qdrant instance on the shared pod network.
- Defines the user-facing contract for four MCP tools plus a local dashboard API and browser UI.
