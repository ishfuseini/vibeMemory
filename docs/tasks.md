## 1. Project Scaffolding

- [ ] 1.1 Create the project structure for the local memory stack, including the server source location, dashboard directories, and project-root MCP configuration file.
- [ ] 1.2 Add the dependency manifests and container build files needed to run the MCP server and dashboard locally.

## 2. Memory Server Implementation

- [ ] 2.1 Implement the FastMCP server bootstrap with the `vibeMemory` service name and streamable HTTP transport on port `8000`.
- [ ] 2.2 Implement the LangGraph normalization workflow and Qdrant collection initialization used before storing memory entries.
- [ ] 2.3 Implement the `remember` tool so it normalizes input, merges highly similar memories within a scope when appropriate, writes the payload to Qdrant, and returns the stored memory metadata.
- [ ] 2.4 Implement the `recall` tool so it embeds the query, filters by scope, queries Qdrant, and returns ranked memory results with the required fields.
- [ ] 2.5 Implement the `forget` and `list_memories` tools plus the `/health` endpoint needed for dashboard and readiness checks.

## 3. Dashboard Implementation

- [ ] 3.1 Implement the dashboard FastAPI shim with `GET /api/memories`, `POST /api/recall`, and `DELETE /api/memories/{id}` backed by the memory server.
- [ ] 3.2 Implement the dashboard UI using the shared `ui.css` daisyUI theme and Chart.js for memory metrics and score distribution.
- [ ] 3.3 Implement scope switching, search, browse-all reset, and per-memory deletion flows in the dashboard UI.

## 4. Local Runtime Integration

- [ ] 4.1 Add the IDE-agnostic `mcp.json` configuration that points to the local `http://localhost:8000/mcp` endpoint, with documentation on adapting it for Cursor, VS Code, Windsurf, and other MCP-compatible editors.
- [ ] 4.2 Document or script the Podman workflow for creating the pod, starting Qdrant, building both images, and running the memory server and dashboard.
- [ ] 4.3 Add optional Compose support for bringing up the local stack with environment wiring for internal service discovery.

## 5. Verification

- [ ] 5.1 Verify the server starts successfully, exposes `/health`, and can create or reuse the configured Qdrant collection.
- [ ] 5.2 Verify `remember` stores normalized content, merges highly similar memories within a scope, and preserves scope isolation.
- [ ] 5.3 Verify `recall`, `list_memories`, and `forget` return the expected data and deletion behavior.
- [ ] 5.4 Verify the dashboard API can list, search, and delete memories through the memory server.
- [ ] 5.5 Verify the dashboard renders with `ui.css`, loads Chart.js visualizations, and updates when the active scope changes.
- [ ] 5.6 Verify MCP clients can discover the `vibeMemory` server and its four tools via the streamable HTTP endpoint.
