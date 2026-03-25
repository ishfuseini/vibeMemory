# vibeMemory — Phase 1 Loop Runbook

## Pattern: sequential | Mode: safe

## Branch Strategy
- Working on: `main`
- Commit after each step passes smoke test

## Stop Condition
Phase 1 complete when all 5 steps implemented and server starts cleanly.

## Loop Steps

| # | Task | File | Done? |
|---|------|------|-------|
| 2.1 | FastMCP bootstrap + Qdrant init + /health | server.py | [ ] |
| 2.2 | FastEmbed + LangGraph normalize/embed helpers | server.py | [ ] |
| 2.3 | `remember` tool | server.py | [ ] |
| 2.4 | `recall` tool | server.py | [ ] |
| 2.5 | `forget` + `list_memories` tools | server.py | [ ] |

## Key Decisions
- Python: 3.14 (as specified)
- Qdrant: localhost:6333, collection `memories`, 384-dim vectors (bge-small-en-v1.5)
- Merge threshold: env var `SIMILARITY_THRESHOLD`, default 0.92
- Qdrant URL: env var `QDRANT_URL`, default `http://localhost:6333`
- Retry: 5 attempts with 2s backoff on Qdrant startup

## Quality Gates (per iteration)
- No import errors
- /health returns 200 (step 2.1+)
- Each tool callable without crash (steps 2.3–2.5)
