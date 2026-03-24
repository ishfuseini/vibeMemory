## Context

This change introduces a new local memory stack for Cursor built from several moving parts: a Python MCP server, Qdrant for vector storage, FastEmbed for local embeddings, LangGraph for a lightweight normalization workflow, a lightweight dashboard web app, Podman for local orchestration, and Cursor MCP client configuration. The current repository contains guides plus a shared [ui.css](/Users/ifuseini/Code/spec/ui.css) daisyUI theme file, so the design needs to translate that material into a concrete implementation plan with clear boundaries between backend service code, dashboard code, container setup, and developer configuration.

## Goals / Non-Goals

**Goals:**
- Provide a local MCP service named `vibeMemory` with `remember`, `recall`, `forget`, and `list_memories` tools over streamable HTTP.
- Persist semantic memories in Qdrant with enough payload metadata to support scoped recall.
- Support merge-on-similarity so closely matching memories update in place instead of duplicating data.
- Provide a browser dashboard that uses the shared daisyUI theme from `ui.css` and Chart.js to inspect and manage memory data.
- Keep the stack self-hosted and CPU-friendly so it runs on a typical local development machine.
- Make local setup reproducible with source-controlled application files and documented Podman commands.

**Non-Goals:**
- Multi-user authentication, access control, or hosted deployment.
- Advanced memory curation beyond the initial similarity merge, such as summarization or multi-step consolidation workflows.
- Rich operational automation such as Compose files, Kubernetes manifests, or CI/CD deployment flows.
- Building a highly interactive SPA framework frontend; the dashboard can remain a lightweight server-rendered or static HTML app.

## Decisions

### Use Qdrant as the persistent memory store
Qdrant is the backing store because it supports vector similarity search and payload filtering, which directly matches the need for semantic recall scoped by fields such as `scope` and `tags`. This keeps the first implementation simple while leaving room for richer metadata-based retrieval later.

Alternative considered: storing vectors in a local SQLite-based store. That would reduce dependencies, but it would also weaken semantic search ergonomics and make metadata filtering less straightforward.

### Expose memory operations through a FastMCP HTTP server
The memory server will be implemented in Python with FastMCP and served over streamable HTTP on port `8000`. This aligns with Cursor's MCP integration model and keeps the tool contract explicit for the `vibeMemory` service: `remember` writes or merges a normalized memory entry, `recall` returns ranked matches, `forget` deletes a memory by ID, and `list_memories` exposes browse-oriented access without semantic search.

Alternative considered: building a custom HTTP API first and adding MCP later. That would create unnecessary translation work and delay Cursor integration.

### Use LangGraph only for a lightweight normalization workflow
LangGraph will be used for a small pre-write workflow that normalizes and truncates incoming memory text before embedding and storage. This gives the implementation a clear place to expand later without over-designing the first version.

Alternative considered: direct inline normalization in the tool handler. That is simpler initially, but it makes future workflow expansion less clean.

### Merge very similar memories within a scope
The write path will perform a similarity check inside the requested scope before inserting a new point. If the top match is above a configurable threshold, the server will update that record in place and return metadata indicating a merge occurred.

Alternative considered: always inserting a new memory. That is easier to implement, but it would quickly create duplicate facts and make recall less useful.

### Add a small dashboard shim instead of exposing Qdrant directly to the browser
The dashboard will run as a separate web app on port `8080` and call the memory server over the shared pod network. A small FastAPI shim will expose browser-safe REST endpoints for listing memories, recalling memories, and deleting by ID while leaving Qdrant internal to the pod.

Alternative considered: calling Qdrant directly from the browser or building the dashboard into the MCP server. Direct browser access would widen the security surface, and folding the dashboard into the MCP service would mix concerns.

### Reuse the existing daisyUI theme and Chart.js for the dashboard
The dashboard UI will consume the repository's `ui.css` theme for visual consistency and use Chart.js for score distribution visuals. This keeps the frontend aligned with the user's chosen theme direction while avoiding bespoke chart rendering code.

Alternative considered: building a plain unthemed HTML page or hand-rolled SVG charts. That would be faster short term, but it would ignore the provided styling direction and create more frontend work.

### Run Qdrant and the MCP server in a shared Podman pod
The local deployment model will use a Podman pod so the server can reach Qdrant at `http://localhost:6333` while exposing the MCP server on `8000` and dashboard on `8080`. Qdrant will remain internal to the pod by default, with optional host exposure only for debugging.

Alternative considered: independent containers on a user-managed bridge network. That works, but it increases the setup burden and makes the guide less approachable.

### Source-control the server and local client configuration
The repository will include `server.py`, `requirements.txt`, `Containerfile`, `.cursor/mcp.json`, optional `compose.yaml`, and dashboard source files as first-class project files. Treating these as source artifacts makes the setup reproducible and gives the implementation a stable place for future changes.

Alternative considered: keeping configuration only in documentation. That would leave too much manual setup outside the repo and make drift more likely.

## Risks / Trade-offs

- [First-run startup is slow because embedding models may download on first use] → Mitigation: document the warm-up behavior and choose a CPU-friendly default model.
- [Local container networking may fail if Podman is not installed or ports are already occupied] → Mitigation: provide explicit setup, port, and troubleshooting guidance.
- [Similarity merging can overwrite distinct memories if the threshold is too low] → Mitigation: make the threshold configurable and limit merge checks to the current scope.
- [Unbounded memory growth can still reduce recall quality over time] → Mitigation: keep the initial schema simple and document follow-up work for richer curation strategies.
- [Dashboard and MCP server can drift if their payload contracts are not kept aligned] → Mitigation: define explicit REST-to-tool mappings and verify them in integration checks.
- [Cursor MCP behavior can vary with local client configuration] → Mitigation: include a concrete `.cursor/mcp.json` example and a manual verification flow.

## Migration Plan

This is a new capability set, so no in-place migration is required. Implementation should land the backend files first, then the dashboard files, then validate local startup in a clean environment. Rollback is low risk: remove the new project files, stop the containers, and delete the local Qdrant volume if a clean reset is needed.

## Open Questions

- Should the first dashboard version use plain static HTML plus vanilla JS, or a minimal frontend framework if the UI grows?
- Should `recall` or `list_memories` support optional tag filtering in the first iteration, or only scope-based filtering?
- Should Compose support the dashboard from the first commit, or remain an optional follow-up after the Podman flow works?
