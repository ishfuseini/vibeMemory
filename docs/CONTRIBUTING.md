# Contributing

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (package manager)
- [Podman Desktop](https://podman-desktop.io/) (container runtime)

## Development Setup

```bash
# Clone and enter the repo
git clone <repo-url>
cd vibeMemory

# Install dependencies
uv sync

# Copy environment config
cp .env.example .env
```

## Running Locally

```bash
# Start Qdrant (required)
podman run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Start memory server
uv run python server.py

# Start dashboard (separate terminal)
uv run uvicorn dashboard.app:app --port 8080 --reload
```

## Available Commands

<!-- AUTO-GENERATED from pyproject.toml -->

| Command | Description |
|---------|-------------|
| `uv run python server.py` | Start the FastMCP memory server on port 8000 |
| `uv run uvicorn dashboard.app:app --port 8080` | Start the dashboard on port 8080 |
| `podman compose up -d` | Start the full stack (Qdrant + server + dashboard) |
| `podman compose down` | Stop the full stack |
| `podman compose logs -f` | Tail logs from all services |

<!-- END AUTO-GENERATED -->

## Code Style

- Follow PEP 8; use type annotations throughout
- Keep functions small (<50 lines)
- No hardcoded values — use env vars or module-level constants
- All new tools must have a docstring describing args and return value

## Testing

Run the smoke test after any changes to `server.py`:

```bash
# Syntax + import check (no Qdrant needed)
uv run python -c "import ast; ast.parse(open('server.py').read()); print('OK')"

# Integration test (Qdrant must be running)
curl -s http://localhost:8000/health | python -m json.tool
```

## Pull Request Checklist

- [ ] `uv run python -c "import ast; ast.parse(open('server.py').read())"` passes
- [ ] `/health` returns `{"status": "ok"}` against a live Qdrant
- [ ] All four MCP tools callable without error
- [ ] `.env.example` updated if new env vars added
- [ ] README env var table updated to match
