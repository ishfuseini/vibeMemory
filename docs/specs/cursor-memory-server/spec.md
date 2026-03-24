## ADDED Requirements

### Requirement: Cursor memory service exposes MCP tools
The system SHALL provide a local MCP-compatible service named `vibeMemory` over streamable HTTP and SHALL expose `remember`, `recall`, `forget`, and `list_memories` tools for clients such as Cursor.

#### Scenario: Cursor connects to the memory service
- **WHEN** the memory server is running and Cursor is configured to use the MCP endpoint
- **THEN** Cursor can discover the `vibeMemory` service and its available tools

#### Scenario: Available tools are limited to the initial memory workflow
- **WHEN** a client inspects the server tool list
- **THEN** the server exposes `remember`, `recall`, `forget`, and `list_memories` as the supported memory operations for the initial release

### Requirement: Remember stores normalized semantic memories
The system SHALL accept memory text with an optional scope and optional tags, SHALL normalize the stored text before persistence, and SHALL write the memory as an embedding-backed record in Qdrant with metadata including scope, tags, source, and creation time.

#### Scenario: Memory is stored with default scope
- **WHEN** a client calls `remember` without providing a scope
- **THEN** the system stores the memory using the default scope and returns the persisted memory identifier and saved content summary

#### Scenario: Memory text is normalized before storage
- **WHEN** a client calls `remember` with text containing repeated whitespace or content longer than the supported stored length
- **THEN** the system stores a normalized, compact version of the text before generating embeddings and writing to Qdrant

### Requirement: Remember merges very similar memories within a scope
The system SHALL check for an existing memory with sufficiently high similarity in the requested scope before inserting a new record and SHALL update that record in place when the configured similarity threshold is met.

#### Scenario: Similar memory is merged instead of duplicated
- **WHEN** a client stores a memory whose embedded content is highly similar to an existing memory in the same scope
- **THEN** the system updates the existing memory record and returns a response indicating the write was merged

#### Scenario: Similar memory in a different scope is not merged
- **WHEN** a client stores a memory similar to one in another scope
- **THEN** the system creates or updates records only within the requested scope and does not merge across scopes

### Requirement: Recall returns scoped semantic matches
The system SHALL embed the recall query, search Qdrant for semantic matches filtered by scope, and return ranked results with identifiers, scores, text, scope, tags, and creation time.

#### Scenario: Recall returns relevant memories from the requested scope
- **WHEN** a client calls `recall` with a query and scope that has matching stored memories
- **THEN** the system returns a ranked list of matching memories from that scope

#### Scenario: Recall excludes memories from other scopes
- **WHEN** a client calls `recall` for a scope that differs from other stored memories
- **THEN** the system excludes memories outside the requested scope from the result set

### Requirement: Memory management tools support browse and delete workflows
The system SHALL allow clients to browse stored memories for a scope without semantic search and SHALL allow clients to delete a stored memory by identifier.

#### Scenario: Client lists memories for a scope
- **WHEN** a client calls `list_memories` with a scope and limit
- **THEN** the system returns stored memory records for that scope with identifiers and payload fields suitable for browsing

#### Scenario: Client deletes a memory by identifier
- **WHEN** a client calls `forget` with a stored memory identifier
- **THEN** the system deletes that memory record and returns a deletion result for the requested identifier

### Requirement: Memory service exposes a health endpoint
The system SHALL provide an HTTP health endpoint for local readiness checks.

#### Scenario: Health endpoint is queried
- **WHEN** a developer sends an HTTP request to the health endpoint while the memory server is running
- **THEN** the system returns a successful readiness response

### Requirement: Local deployment is reproducible with project artifacts
The system SHALL provide source-controlled project artifacts for the server application, Python dependencies, container image build, and Cursor MCP client configuration so a developer can build, run, and verify the local stack.

#### Scenario: Developer builds and runs the local stack
- **WHEN** a developer follows the project setup using the provided project artifacts and Podman commands
- **THEN** the developer can start Qdrant, build the server image, run the memory server, and reach the MCP endpoint locally

#### Scenario: Developer configures Cursor for the MCP endpoint
- **WHEN** a developer adds the provided `.cursor/mcp.json` configuration
- **THEN** Cursor points to the local MCP endpoint and can attempt tool discovery against the running server
