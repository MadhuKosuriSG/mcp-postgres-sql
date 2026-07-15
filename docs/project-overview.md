# Project Overview: mcp-tool-calling

**Generated:** 2026-07-14 (initial scan, quick scan level)

## What This Project Is

A FastAPI backend that exposes a `/chat` endpoint backed by an LLM (OpenAI), where the LLM can call tools exposed by a running **MCP (Model Context Protocol) server**. The currently wired MCP server is `postgres-mcp`, giving the LLM the ability to inspect and query a PostgreSQL database as part of answering a chat message. A second `/mcp/call` endpoint allows calling an MCP tool directly, bypassing the LLM.

In short: it's a bridge between a chat-style HTTP API, an LLM tool-calling loop, and one or more MCP tool servers.

## Repository Structure

- **Type:** Monolith (single Python package, no separate client/server split)
- **Primary language:** Python
- **Framework:** FastAPI (ASGI), served via Uvicorn
- **Entry point:** [main.py](../main.py)

## Tech Stack Summary

| Category      | Technology              | Version        |
|----------------|--------------------------|----------------|
| Web framework  | FastAPI                 | 0.119.1        |
| ASGI server    | Uvicorn                 | 0.35.0         |
| MCP SDK        | `mcp` (official Python SDK) | 1.28.1     |
| LLM client     | `openai` (AsyncOpenAI)   | >=1.0.0,<2.0.0 |
| Config loading | python-dotenv            | 1.1.1          |
| External MCP server | `postgres-mcp` (via `uvx`) | n/a (subprocess) |

## Architecture Type

Layered service architecture:
- **`api/`** — FastAPI routers (HTTP boundary)
- **`services/`** — business logic (chat orchestration, LLM calls)
- **`mcp_server/`** — MCP protocol client and lifecycle manager
- **`core/`** — currently an empty placeholder package

See [architecture.md](./architecture.md) for details.

## Getting Started

1. Create/activate a virtualenv (a `venv/` already exists in the repo).
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` with: `OPENAI_API_KEY`, `OPENAI_MODEL`, `DATABASE_URI` (or the individual `PG_HOST`/`PG_PORT`/`PG_USER`/`PG_PASSWORD`/`PG_DATABASE` vars), `MCP_COMMAND`, `MCP_ARGS`.
4. Run the server: `uvicorn main:app --reload`
5. Check health: `GET /health`
6. Send a chat message: `POST /chat` with `{"message": "..."}`

See [development-guide.md](./development-guide.md) for more detail.

## Links

- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [API Contracts](./api-contracts.md)
- [Data Models](./data-models.md)
- [Development Guide](./development-guide.md)
- [Deployment Guide](./deployment-guide.md) _(To be generated)_
