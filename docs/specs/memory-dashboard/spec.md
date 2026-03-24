## ADDED Requirements

### Requirement: Dashboard exposes browser-safe memory APIs
The system SHALL provide a local dashboard service that exposes REST endpoints for listing memories, recalling memories, and deleting memories by calling the memory server over the shared pod network.

#### Scenario: Dashboard lists memories through the backend API
- **WHEN** a browser requests `GET /api/memories` with a scope and limit
- **THEN** the dashboard service returns memory records produced by the memory server's browse workflow

#### Scenario: Dashboard recalls memories through the backend API
- **WHEN** a browser sends `POST /api/recall` with a query, scope, and limit
- **THEN** the dashboard service returns scored recall results produced by the memory server

#### Scenario: Dashboard deletes a memory through the backend API
- **WHEN** a browser sends `DELETE /api/memories/{id}`
- **THEN** the dashboard service calls the memory server delete workflow and returns the deletion result

### Requirement: Dashboard provides themed memory visualizations
The system SHALL provide a browser UI that uses the repository `ui.css` daisyUI theme and Chart.js to visualize memory statistics and search results.

#### Scenario: Dashboard shows summary cards and chart
- **WHEN** a user opens the dashboard
- **THEN** the UI displays memory metrics and a score distribution chart derived from the current memory dataset

#### Scenario: Dashboard uses the shared theme
- **WHEN** the dashboard renders its UI
- **THEN** it uses the shared styling defined in `ui.css` for the daisyUI-based visual theme

### Requirement: Dashboard supports scope-based browsing and management
The system SHALL allow users to switch scopes, browse the current scope, run semantic search, reset to browse-all, and delete individual memories from the dashboard.

#### Scenario: Switching scopes refreshes the memory list
- **WHEN** a user selects a different scope in the dashboard
- **THEN** the dashboard reloads the memory list and metrics for the selected scope

#### Scenario: Search and browse modes can be toggled
- **WHEN** a user runs a search and then chooses to browse all memories again
- **THEN** the dashboard switches between recall results and list results without reloading the application shell
