# Project Documentation Index

**Generated:** 2026-07-14 · Scan level: quick · Focus: MCP integration (`mcp_server/`, Postgres MCP wiring)

## Project Overview

- **Type:** Monolith (single part)
- **Primary Language:** Python
- **Architecture:** Layered service architecture (FastAPI routers → services → MCP client)

## Quick Reference

- **Tech Stack:** FastAPI, Uvicorn, `mcp` SDK, OpenAI (`AsyncOpenAI`), python-dotenv
- **Entry Point:** [main.py](../main.py)
- **Architecture Pattern:** Layered / service-oriented, no local data layer (DB access delegated to external `postgres-mcp` MCP server)

## Generated Documentation

- [Project Overview](./project-overview.md)
- [Architecture](./architecture.md)
- [Source Tree Analysis](./source-tree-analysis.md)
- [Development Guide](./development-guide.md)
- [API Contracts](./api-contracts.md)
- [Data Models](./data-models.md)
- [Deployment Guide](./deployment-guide.md) _(To be generated)_

## Existing Documentation

None found — `README.md` is empty and no `ARCHITECTURE.md`/`CONTRIBUTING.md`/`docs/` content existed prior to this scan.

## Known Issues Found During Scan

- `services/test_llm.py` calls `LLMService.chat()` with no arguments, which doesn't match its signature (`chat(messages, tools=None)`) — likely stale.
- `.env` defines `MCP_COMMAND`/`MCP_ARGS`/`PG_HOST`/`PG_PORT`/`PG_USER`/`PG_PASSWORD`/`PG_DATABASE`, none of which are currently read by `mcp_server/client.py` (it hardcodes `command="uvx"` and reads only `DATABASE_URI`) — worth confirming these are dead config or wiring them up.
- `mcp_server/models.py` and `core/` are empty placeholders with no content yet.

## Getting Started

1. `pip install -r requirements.txt`
2. Fill in `.env` (see [development-guide.md](./development-guide.md))
3. `uvicorn main:app --reload`
4. `POST /chat` with `{"message": "..."}` to try the LLM + MCP tool-calling flow

## Next Steps

- **Brownfield PRD:** point the PRD workflow at this `docs/index.md` as project context.
- Consider generating a **deployment guide** once a deployment approach (Docker, cloud target, etc.) is chosen.
- Consider adding an automated test suite — none currently exists.
