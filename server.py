"""vibeMemory — FastMCP server. Core logic lives in memory.py."""

from __future__ import annotations

import hmac
import os
from typing import Any

import memory as mem
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("vibeMemory")

_MAX_LIMIT = 200

_API_KEY = os.getenv("VIBEMEMORY_API_KEY")


class _APIKeyMiddleware:
    """Pure ASGI middleware — safe for SSE/streaming responses."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and _API_KEY and scope.get("path") != "/health":
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            if not hmac.compare_digest(auth.encode(), f"Bearer {_API_KEY}".encode()):
                response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
def remember(
    text: str,
    scope: str = "default",
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Store a memory. Merges with an existing memory if highly similar within the scope.

    Args:
        text: The content to remember.
        scope: Logical namespace for isolation (default: "default").
        tags: Optional list of tags for categorization.
        source: Optional provenance string (e.g. "user", "assistant", "file:foo.py").

    Returns:
        dict with keys: id, text, scope, tags, source, created_at, merged (bool).
    """
    return mem.remember(text, scope=scope, tags=tags, source=source)


@mcp.tool
def recall(
    query: str,
    scope: str = "default",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve memories semantically similar to the query within a scope.

    Args:
        query: Natural language search query.
        scope: Logical namespace to search within (default: "default").
        limit: Maximum number of results to return (default: 5).

    Returns:
        List of memory dicts ordered by relevance score (descending).
    """
    return mem.recall(query, scope=scope, limit=min(max(1, limit), _MAX_LIMIT))


@mcp.tool
def forget(id: str) -> dict[str, Any]:
    """Delete a memory by its UUID.

    Args:
        id: The UUID of the memory to delete.

    Returns:
        dict with keys: id, deleted (bool).
    """
    return mem.forget(id)


@mcp.tool
def list_memories(
    scope: str = "default",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Browse all memories in a scope (no semantic ranking).

    Args:
        scope: Logical namespace to list (default: "default").
        limit: Maximum records to return (default: 50).

    Returns:
        List of memory dicts.
    """
    return mem.list_memories(scope=scope, limit=min(max(1, limit), _MAX_LIMIT))


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    try:
        qdrant = mem.get_qdrant()
        collections = [c.name for c in qdrant.get_collections().collections]
        collection_ok = mem.COLLECTION in collections
    except Exception as exc:
        return JSONResponse({"status": "unhealthy", "error": str(exc)}, status_code=503)
    return JSONResponse(
        {
            "status": "ok",
            "qdrant": mem.QDRANT_URL,
            "collection": mem.COLLECTION,
            "collection_exists": collection_ok,
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn

    mem.init()
    uvicorn.run(_APIKeyMiddleware(mcp.http_app()), host="0.0.0.0", port=8000)
