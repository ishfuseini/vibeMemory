"""vibeMemory — shared core: Qdrant, FastEmbed, and memory operations."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from qdrant_client import QdrantClient
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
# Qdrant client
# ---------------------------------------------------------------------------

_qdrant: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    if _qdrant is None:
        raise RuntimeError("Qdrant not initialized — call init() first")
    return _qdrant


def _init_qdrant() -> None:
    global _qdrant
    for attempt in range(1, QDRANT_RETRY_ATTEMPTS + 1):
        try:
            client = QdrantClient(url=QDRANT_URL)
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
# FastEmbed
# ---------------------------------------------------------------------------

_embedder: Any = None


def get_embedder() -> Any:
    if _embedder is None:
        raise RuntimeError("Embedder not initialized — call init() first")
    return _embedder


def _init_embedder() -> None:
    global _embedder
    from fastembed import TextEmbedding

    print(f"[vibeMemory] Loading embedding model '{EMBED_MODEL}' (may take a moment on first run)…")
    _embedder = TextEmbedding(model_name=EMBED_MODEL)
    print("[vibeMemory] Embedding model ready.")


def embed_text(text: str) -> list[float]:
    vectors = list(get_embedder().embed([text]))
    return vectors[0].tolist()


# ---------------------------------------------------------------------------
# Normalization — LangGraph pipeline
# ---------------------------------------------------------------------------


class _NormState(TypedDict):
    text: str


def _trim(state: _NormState) -> _NormState:
    return {"text": " ".join(state["text"].split())}


def _truncate(state: _NormState) -> _NormState:
    return {"text": state["text"][:MAX_TEXT_LEN]}


def _lowercase(state: _NormState) -> _NormState:
    return {"text": state["text"].lower()}


_norm_graph = StateGraph(_NormState)
_norm_graph.add_node("trim", RunnableLambda(_trim))
_norm_graph.add_node("truncate", RunnableLambda(_truncate))
_norm_graph.add_node("lowercase", RunnableLambda(_lowercase))
_norm_graph.set_entry_point("trim")
_norm_graph.add_edge("trim", "truncate")
_norm_graph.add_edge("truncate", "lowercase")
_norm_graph.add_edge("lowercase", END)
_normalizer = _norm_graph.compile()


def normalize_text(text: str) -> str:
    """Run text through the LangGraph trim → truncate → lowercase pipeline."""
    return _normalizer.invoke({"text": text})["text"]


# ---------------------------------------------------------------------------
# Memory operations
# ---------------------------------------------------------------------------


def remember(
    text: str,
    scope: str = "default",
    tags: list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Store a memory. Merges with an existing one if cosine similarity >= threshold."""
    normalized = normalize_text(text)
    vector = embed_text(normalized)
    qdrant = get_qdrant()

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
        existing = results[0]
        point_id = existing.id
        payload = existing.payload or {}
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
            "similarity": round(results[0].score, 4),
        }

    point_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    payload = {
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


def recall(
    query: str,
    scope: str = "default",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve memories semantically ranked by similarity to the query."""
    vector = embed_text(normalize_text(query))
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


def forget(memory_id: str) -> dict[str, Any]:
    """Delete a memory by UUID."""
    get_qdrant().delete(
        collection_name=COLLECTION,
        points_selector=PointIdsList(points=[memory_id]),
    )
    return {"id": memory_id, "deleted": True}


def list_memories(
    scope: str = "default",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Browse all memories in a scope without semantic ranking."""
    qdrant = get_qdrant()
    results, _ = qdrant.scroll(
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


def list_scopes() -> list[str]:
    """Return all distinct scope values present in the collection."""
    qdrant = get_qdrant()
    all_records, _ = qdrant.scroll(
        collection_name=COLLECTION,
        limit=1000,
        with_payload=["scope"],
    )
    seen: set[str] = set()
    for r in all_records:
        if r.payload and (s := r.payload.get("scope")):
            seen.add(s)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


def init() -> None:
    """Initialize embedder and Qdrant. Call once at process startup."""
    _init_embedder()
    _init_qdrant()
