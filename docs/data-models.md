# Data Models

## Summary

This repository defines **no local data models, ORM schema, or migrations**. There is no `models/`, `schemas/`, `migrations/`, or ORM (SQLAlchemy/Prisma/etc.) dependency in `requirements.txt`.

All database interaction is delegated to the external `postgres-mcp` MCP server (launched as a subprocess by `mcp_server/client.py`). That server owns the actual schema introspection and SQL execution; this repo only:
- Supplies connection info (`DATABASE_URI`, and/or `PG_HOST`/`PG_PORT`/`PG_USER`/`PG_PASSWORD`/`PG_DATABASE` from `.env`)
- Receives tool results back as MCP `content` blocks / `structuredContent`, parsed opportunistically as JSON in `services/chat_service.py::_extract_json_content`

## In-Repo "Models" (Pydantic request/response, not persistence)

These are HTTP-layer shapes only, not database models:

- `api/chat.py`: `ChatRequest { message: str }`, `ChatResponse { reply: str, data: Optional[Any] }`
- `api/mcp.py`: `MCPCallRequest { tool: str, arguments: dict }`, `MCPCallResponse { is_error: bool, content: list, structured_content: Optional[Any] }`

`mcp_server/models.py` exists as a placeholder for MCP-related types but is currently empty — these Pydantic classes could be candidates to move there if they grow.

## Database Schema

Not documented here — schema lives in whatever PostgreSQL database `DATABASE_URI` points to, and is introspectable at runtime via `postgres-mcp`'s tools (e.g. `execute_sql` against `information_schema`), not via static files in this repo.
