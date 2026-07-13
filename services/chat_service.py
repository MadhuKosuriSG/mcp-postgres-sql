"""Chat service: sends the user's chat message to the LLM along with the
PostgreSQL MCP server's tools, executes any tool call the model requests,
and returns the model's final text reply.
"""

import json
import logging
from typing import Any, Optional

from mcp_server.manager import MCPManager
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ChatServiceError(RuntimeError):
    """Raised when a chat message cannot be executed against MCP."""


def _extract_json_content(tool_result: Any) -> Optional[Any]:
    """Pull the first JSON-parseable text block out of an MCP tool result."""
    for item in getattr(tool_result, "content", None) or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            continue
    return None


class ChatService:
    """Answers chat messages using the LLM, with tool access to the active MCP session."""

    def __init__(self, mcp_manager: MCPManager) -> None:
        self._mcp_manager = mcp_manager
        self.llm_service = LLMService()

    async def send_message(self, user_message: str) -> tuple[str, Optional[Any]]:
        """Send the message to the LLM, executing any MCP tool calls it requests.

        Returns (reply_text, data), where data is the structured JSON payload
        from the last tool call that returned one (e.g. execute_sql rows), so
        callers get real query results instead of the model's paraphrase of them.
        """
        if not self._mcp_manager.is_connected():
            raise ChatServiceError("MCP session is not connected")

        messages = [
            {
                "role": "user",
                "content": user_message,
            }
        ]
        mcp_tools = self._mcp_manager.get_tools()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description,
                    "parameters": mcp_tool.inputSchema,
                },
            }
            for mcp_tool in mcp_tools
        ]

        last_data: Optional[Any] = None

        try:
            result = await self.llm_service.chat(messages=messages, tools=tools)
            message = result.choices[0].message

            while message.tool_calls:
                messages.append(message.model_dump(exclude_unset=True))
                for tool_call in message.tool_calls:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    print("#################")
                    print(arguments)
                    tool_result = await self._mcp_manager.call_tool(
                        tool_call.function.name, arguments
                    )
                    data = _extract_json_content(tool_result)
                    if data is not None:
                        last_data = data
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_result),
                        }
                    )
                result = await self.llm_service.chat(messages=messages, tools=tools)
                message = result.choices[0].message
        except Exception as exc:
            logger.exception("Chat completion with MCP tool call failed")
            raise ChatServiceError("Failed to execute query against MCP") from exc

        return message.content or "", last_data
