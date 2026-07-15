# API Contracts

No authentication/authorization is implemented on any endpoint.

## `POST /chat`

Defined in [api/chat.py](../api/chat.py).

**Request**
```json
{ "message": "string" }
```

**Response** (`200`)
```json
{ "reply": "string", "data": null }
```
- `data` is the structured JSON payload extracted from the **last** MCP tool call that returned parseable JSON (e.g. `execute_sql` rows), or `null` if none did.

**Error** — `502` with `{"detail": "..."}` on `ChatServiceError` (e.g. MCP session not connected, or the tool-calling loop raised).

**Flow:** message → `ChatService.send_message` → `LLMService.chat` (OpenAI, with the current MCP tool list passed as `tools=`) → if the model requests tool calls, each is executed via `MCPManager.call_tool`, appended back into the message history as a `tool` role message, and the LLM is called again — looping until the model responds without further tool calls.

## `POST /mcp/call`

Defined in [api/mcp.py](../api/mcp.py). Bypasses the LLM — calls an MCP tool directly.

**Request**
```json
{ "tool": "string", "arguments": { "...": "..." } }
```

**Response** (`200`)
```json
{
  "is_error": false,
  "content": [ /* MCP content blocks, each via block.model_dump(mode="json") */ ],
  "structured_content": null
}
```

**Error** — `502` with `{"detail": "..."}` on `MCPClientError` (e.g. not connected, or the underlying `call_tool` raised).

## `GET /health`

Defined in [main.py](../main.py). No request body.

**Response** (`200`)
```json
{ "status": "healthy", "mcp_connected": true, "tool_count": 0 }
```

## `GET /`

Defined in [main.py](../main.py). Basic liveness check, returns `{"message": "FastAPI MCP Server is running"}`.

## Available MCP Tools

The actual set of callable `tool` names for `/mcp/call` (and what the LLM can invoke via `/chat`) is **not fixed in this codebase** — it's whatever `postgres-mcp` reports via `list_tools()` at connect time (e.g. tools like `execute_sql`, based on usage in `services/chat_service.py`). Query `GET /health` for `tool_count`, or inspect `MCPManager.get_tools()` at runtime, for the live list.
