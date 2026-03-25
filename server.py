"""vibeMemory — FastMCP memory server with Qdrant + FastEmbed + LangGraph."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "memories")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
VECTOR_SIZE = 384  # bge-small-en-v1.5 output dim
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "2000"))
QDRANT_RETRY_ATTEMPTS = 5
QDRANT_RETRY_DELAY = 2.0

# ---------------------------------------------------------------------------
# Qdrant client — initialized lazily with retry at startup
# ---------------------------------------------------------------------------

_qdrant: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        raise RuntimeError("Qdrant not initialized")
    return _qdrant


def _init_qdrant() -> None:
    """Connect to Qdrant and ensure the memories collection exists."""
    global _qdrant
    for attempt in range(1, QDRANT_RETRY_ATTEMPTS + 1):
        try:
            client = QdrantClient(url=QDRANT_URL)
            # Ping by listing collections
            client.get_collections()
            _qdrant = client
            break
        except Exception as exc:
            if attempt == QDRANT_RETRY_ATTEMPTS:
                raise RuntimeError(
                    f"Cannot connect to Qdrant at {QDRANT_URL} after "
                    f"{QDRANT_RETRY_ATTEMPTS} attempts: {exc}"
                ) from exc
            print(
                f"[vibeMemory] Qdrant not ready (attempt {attempt}), "
                f"retrying in {QDRANT_RETRY_DELAY}s…"
            )
            time.sleep(QDRANT_RETRY_DELAY)

    # Create collection if it doesn't exist
    existing = [c.name for c in _qdrant.get_collections().collections]
    if COLLECTION not in existing:
        _qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[vibeMemory] Created Qdrant collection '{COLLECTION}'")
    else:
        print(f"[vibeMemory] Using existing Qdrant collection '{COLLECTION}'")


# ---------------------------------------------------------------------------
# FastEmbed — initialized once at startup
# ---------------------------------------------------------------------------

_embedder: Any = None


def get_embedder() -> Any:
    global _embedder
    if _embedder is None:
        raise RuntimeError("Embedder not initialized")
    return _embedder


def _init_embedder() -> None:
    global _embedder
    from fastembed import TextEmbedding  # local import to defer heavy load

    print(f"[vibeMemory] Loading embedding model '{EMBED_MODEL}' (may take a moment on first run)…")
    _embedder = TextEmbedding(model_name=EMBED_MODEL)
    print("[vibeMemory] Embedding model ready.")


def embed_text(text: str) -> list[float]:
    embedder = get_embedder()
    vectors = list(embedder.embed([text]))
    return vectors[0].tolist()


# ---------------------------------------------------------------------------
# LangGraph normalization workflow
# ---------------------------------------------------------------------------

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class NormState(TypedDict):
    text: str


def _trim_whitespace(state: NormState) -> NormState:
    return {"text": " ".join(state["text"].split())}


def _truncate(state: NormState) -> NormState:
    text = state["text"]
    return {"text": text[:MAX_TEXT_LEN] if len(text) > MAX_TEXT_LEN else text}


def _lowercase(state: NormState) -> NormState:
    return {"text": state["text"].lower()}


_norm_graph = StateGraph(NormState)
_norm_graph.add_node("trim", _trim_whitespace)
_norm_graph.add_node("truncate", _truncate)
_norm_graph.add_node("lowercase", _lowercase)
_norm_graph.add_edge(START, "trim")
_norm_graph.add_edge("trim", "truncate")
_norm_graph.add_edge("truncate", "lowercase")
_norm_graph.add_edge("lowercase", END)
_norm_workflow = _norm_graph.compile()


def normalize_text(text: str) -> str:
    result = _norm_workflow.invoke({"text": text})
    return result["text"]


# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP("vibeMemory")


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
    normalized = normalize_text(text)
    vector = embed_text(normalized)
    qdrant = get_qdrant()

    # Search for highly similar existing memory within this scope
    results = qdrant.search(
        collection_name=COLLECTION,
        query_vector=vector,
        query_filter=Filter(
            must=[FieldCondition(key="scope", match=MatchValue(value=scope))]
        ),
        limit=1,
        with_payload=True,
    )

    if results and results[0].score >= SIMILARITY_THRESHOLD:
        # Merge: update payload of the existing point
        existing = results[0]
        point_id = existing.id
        payload = existing.payload or {}
        # Preserve original created_at, update text and metadata
        payload["text"] = normalized
        payload["tags"] = tags or payload.get("tags", [])
        payload["source"] = source or payload.get("source")
        qdrant.set_payload(
            collection_name=COLLECTION,
            payload=payload,
            points=[point_id],
        )
        return {
            "id": str(point_id),
            "text": normalized,
            "scope": scope,
            "tags": payload["tags"],
            "source": payload["source"],
            "created_at": payload.get("created_at"),
            "merged": True,
            "similarity": results[0].score,
        }

    # Insert new point
    point_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "text": normalized,
        "scope": scope,
        "tags": tags or [],
        "source": source,
        "created_at": created_at,
    }
    qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )
    return {
        "id": point_id,
        "text": normalized,
        "scope": scope,
        "tags": tags or [],
        "source": source,
        "created_at": created_at,
        "merged": False,
    }


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
    normalized = normalize_text(query)
    vector = embed_text(normalized)
    qdrant = get_qdrant()

    results = qdrant.search(
        collection_name=COLLECTION,
        query_vector=vector,
        query_filter=Filter(
            must=[FieldCondition(key="scope", match=MatchValue(value=scope))]
        ),
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "id": str(r.id),
            "score": round(r.score, 4),
            "text": r.payload.get("text", "") if r.payload else "",
            "scope": r.payload.get("scope", scope) if r.payload else scope,
            "tags": r.payload.get("tags", []) if r.payload else [],
            "source": r.payload.get("source") if r.payload else None,
            "created_at": r.payload.get("created_at") if r.payload else None,
        }
        for r in results
    ]


@mcp.tool
def forget(id: str) -> dict[str, Any]:
    """Delete a memory by its UUID.

    Args:
        id: The UUID of the memory to delete.

    Returns:
        dict with keys: id, deleted (bool).
    """
    qdrant = get_qdrant()
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=PointIdsList(points=[id]),
    )
    return {"id": id, "deleted": True}


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
    qdrant = get_qdrant()
    results, _next = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="scope", match=MatchValue(value=scope))]
        ),
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "id": str(r.id),
            "text": r.payload.get("text", "") if r.payload else "",
            "scope": r.payload.get("scope", scope) if r.payload else scope,
            "tags": r.payload.get("tags", []) if r.payload else [],
            "source": r.payload.get("source") if r.payload else None,
            "created_at": r.payload.get("created_at") if r.payload else None,
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# HTTP health endpoint — registered directly on the MCP app
# ---------------------------------------------------------------------------

from starlette.requests import Request
from starlette.responses import JSONResponse


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    try:
        qdrant = get_qdrant()
        collections = [c.name for c in qdrant.get_collections().collections]
        collection_ok = COLLECTION in collections
    except Exception as exc:
        return JSONResponse(
            {"status": "unhealthy", "error": str(exc)}, status_code=503
        )
    return JSONResponse(
        {
            "status": "ok",
            "qdrant": QDRANT_URL,
            "collection": COLLECTION,
            "collection_exists": collection_ok,
        }
    )


# ---------------------------------------------------------------------------
# Startup + entry point
# ---------------------------------------------------------------------------

def _on_startup() -> None:
    _init_embedder()
    _init_qdrant()


if __name__ == "__main__":
    import uvicorn

    _on_startup()
    app = mcp.http_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
