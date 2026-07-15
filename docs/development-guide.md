# Development Guide

## Prerequisites

- Python (a `venv/` targeting a recent CPython is already present in the repo; `mcp_server/client.py` defaults to launching subprocesses with Python 3.12)
- `uvx` available on `PATH` (used to launch `postgres-mcp` as a subprocess)
- A reachable PostgreSQL instance for `postgres-mcp` to connect to
- An OpenAI API key

## Environment Setup

Create a `.env` file (already gitignored) with:

```
PG_HOST=
PG_PORT=
PG_USER=
PG_PASSWORD=
PG_DATABASE=
DATABASE_URI=
MCP_COMMAND=
MCP_ARGS=
OPENAI_API_KEY=
OPENAI_MODEL=
```

Notes:
- `mcp_server/client.py` reads `DATABASE_URI` directly (falls back to the `database_uri` constructor arg). The individual `PG_*` vars are present in `.env` but not read anywhere in the current code — confirm whether `DATABASE_URI` alone is sufficient or whether the `PG_*` vars are wired elsewhere (e.g. by `postgres-mcp` itself).
- `MCP_COMMAND` / `MCP_ARGS` are defined in `.env` but `MCPClient` currently hardcodes `command="uvx"` and its own args — these env vars don't appear to be consumed yet.
- `.mcp.json` at the repo root configures the same `postgres-mcp` server for use by Claude Code / MCP-aware IDEs, separate from the app's own `mcp_server/client.py` wiring.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

- `GET /` — basic liveness message
- `GET /health` — reports `mcp_connected` and `tool_count`
- `POST /chat` — `{"message": "..."}` → LLM + MCP tool-calling loop
- `POST /mcp/call` — `{"tool": "...", "arguments": {...}}` → direct MCP tool invocation

## Testing

No automated test suite is configured. `services/test_llm.py` is a manual script (`python -m services.test_llm` or similar), not a pytest test — and as noted in [architecture.md](./architecture.md), it currently calls `LLMService.chat()` with no arguments, which doesn't match the method's signature.

## Common Development Tasks

- **Add a new MCP-backed capability:** extend `mcp_server/manager.py`/`client.py` if a new MCP server needs to be connected, or just rely on `MCPManager.get_tools()` picking up new tools automatically from the existing `postgres-mcp` session.
- **Add a new HTTP endpoint:** create a router in `api/`, wire any new service in `services/`, and `app.include_router(...)` it in `main.py`.
