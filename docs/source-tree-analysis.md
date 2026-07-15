# Source Tree Analysis

```
mcp-tool-calling/
├── main.py                  # Entry point: builds FastAPI app, wires lifespan (MCP connect/disconnect), mounts routers
├── config.py                 # Loads OPENAI_API_KEY / OPENAI_MODEL from .env
├── requirements.txt           # fastapi, uvicorn, mcp, python-dotenv, openai
├── .env                       # PG_*, DATABASE_URI, MCP_COMMAND, MCP_ARGS, OPENAI_API_KEY, OPENAI_MODEL (gitignored)
├── .mcp.json                  # Claude Code MCP config: registers the same postgres-mcp server for IDE/agent use
│
├── api/                       # HTTP boundary (FastAPI routers)
│   ├── chat.py                #   POST /chat → ChatService.send_message
│   └── mcp.py                 #   POST /mcp/call → MCPManager.call_tool (direct tool invocation, bypasses the LLM)
│
├── services/                  # Business logic
│   ├── chat_service.py        #   Orchestrates the LLM tool-calling loop against MCP tools
│   ├── llm_service.py         #   Thin wrapper around AsyncOpenAI chat.completions.create
│   └── test_llm.py            #   Ad-hoc manual script (not a pytest suite; calls LLMService directly)
│
├── mcp_server/                #   MCP protocol client + lifecycle
│   ├── manager.py             #   MCPManager: app-lifetime owner of one MCPClient + its tool list
│   ├── client.py              #   MCPClient: stdio session lifecycle against `postgres-mcp` via `uvx`
│   └── models.py              #   Empty (placeholder, no content yet)
│
├── core/                      # Empty placeholder package (__init__.py only, no other files)
│
├── docs/                      # This documentation (project_knowledge output)
├── _bmad/, _bmad-output/      # BMad Method tooling and generated planning/implementation artifacts
└── venv/                      # Local virtualenv (not part of source)
```

## Entry Point

[main.py](../main.py) is the single entry point. On startup it:
1. Loads `.env`
2. Constructs one `MCPManager` and one `ChatService` for the app's lifetime
3. Connects to the MCP server during FastAPI's `lifespan` startup, disconnects on shutdown
4. Mounts the `chat` and `mcp` routers

## Integration Points

- `api/chat.py` → `services/chat_service.py` → `mcp_server/manager.py` → `mcp_server/client.py` → external `postgres-mcp` subprocess (via `uvx`)
- `services/chat_service.py` → `services/llm_service.py` → OpenAI API
- `api/mcp.py` → `mcp_server/manager.py` directly (skips the LLM/chat layer)

## Notable Gaps

- `mcp_server/models.py` exists but is empty — no shared MCP-related types are defined there yet; request/response shaping for MCP calls currently lives inline in `api/mcp.py` (`MCPCallRequest`/`MCPCallResponse`).
- `core/` is an empty placeholder package with no code yet.
- No automated test suite (`services/test_llm.py` is a manual script, not pytest-based; no `pytest`/`unittest` in `requirements.txt`).
