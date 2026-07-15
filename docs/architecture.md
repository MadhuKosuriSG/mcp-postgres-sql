# Architecture: mcp-tool-calling

## Executive Summary

A single-process FastAPI backend that lets an LLM (via OpenAI's chat-completions tool-calling) invoke tools exposed by an external MCP server (`postgres-mcp`, launched as a subprocess via `uvx`). The app owns one long-lived MCP session for its whole lifetime, connecting on startup and disconnecting on shutdown. Two HTTP entry points exist: a chat endpoint that lets the LLM decide which MCP tools to call, and a direct MCP-call endpoint that bypasses the LLM entirely.

## Technology Stack

| Category      | Technology                   | Version         | Justification |
|----------------|-------------------------------|------------------|----------------|
| Web framework  | FastAPI                       | 0.119.1          | ASGI, async-native, pairs naturally with async MCP client |
| ASGI server    | Uvicorn                        | 0.35.0           | Standard FastAPI dev/prod server |
| MCP SDK        | `mcp` (official Python SDK)    | 1.28.1           | stdio client/session for talking to MCP servers |
| LLM client     | `openai` (AsyncOpenAI)         | >=1.0.0,<2.0.0   | Chat completions with `tools=` for tool-calling |
| Config         | python-dotenv                  | 1.1.1            | Loads `.env` into process env |
| External process | `postgres-mcp` via `uvx`      | n/a              | Provides DB-inspection/query MCP tools; run out-of-process, not a Python dependency of this repo |

**Architecture Pattern:** Layered / service-oriented — HTTP routers → services → MCP client — typical for a small async Python backend, not a full hexagonal/clean-architecture split (no explicit domain layer; `core/` is reserved but empty).

## Data Architecture

There is **no in-repo data layer** — no ORM models, no migrations, no local database schema. Data access to PostgreSQL happens entirely through the external `postgres-mcp` server's tools (e.g. `execute_sql`), invoked over MCP. The FastAPI app only holds connection configuration (`DATABASE_URI` / `PG_*` env vars) and passes it to the MCP server subprocess — it never talks to Postgres directly. See [data-models.md](./data-models.md).

## API Design

Two REST-ish JSON endpoints (no auth layer present). See [api-contracts.md](./api-contracts.md) for full request/response shapes:
- `POST /chat` — LLM-mediated: user message in, LLM decides whether to call MCP tools, final text (+ optional structured data from the last tool call) out.
- `POST /mcp/call` — direct: caller names an MCP tool and arguments explicitly.
- `GET /health`, `GET /` — liveness/status, not part of the MCP flow.

## Component Overview

- **`api/`** — FastAPI routers; pure HTTP boundary, delegates to services via `Depends`, translating service errors (`ChatServiceError`, `MCPClientError`) into `HTTPException(502)`.
- **`services/chat_service.py`** — the tool-calling loop: sends messages + tool schemas to the LLM, executes any requested MCP tool calls, appends results back into the message history, and repeats until the LLM stops requesting tools.
- **`services/llm_service.py`** — thin wrapper around `AsyncOpenAI.chat.completions.create`.
- **`mcp_server/manager.py`** — app-lifetime singleton holding one `MCPClient` and the cached tool list (fetched once on connect).
- **`mcp_server/client.py`** — owns the actual MCP `ClientSession` lifecycle (connect/disconnect/list_tools/call_tool) against `postgres-mcp`, launched via `uvx` over stdio.
- **`core/`** — empty; no components yet.

## Source Tree

See [source-tree-analysis.md](./source-tree-analysis.md).

## Development Workflow

See [development-guide.md](./development-guide.md).

## Deployment Architecture

No deployment configuration was found in this repository (no Dockerfile, docker-compose, CI/CD workflows, or IaC). Deployment approach is undocumented — _(To be generated)_ once a deployment method is chosen.

## Testing Strategy

No automated test suite exists. `services/test_llm.py` is a manual script that calls `LLMService.chat()` directly (note: it calls `chat()` with no `messages` argument, which does not match `LLMService.chat`'s signature — likely stale/broken). There are no `pytest`/`unittest` entries in `requirements.txt` and no `tests/` directory.
