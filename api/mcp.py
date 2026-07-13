from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from mcp_server.client import MCPClientError
from mcp_server.manager import MCPManager

router = APIRouter()


class MCPCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


class MCPCallResponse(BaseModel):
    is_error: bool
    content: list[Any]
    structured_content: Optional[Any] = None


def get_mcp_manager(request: Request) -> MCPManager:
    return request.app.state.mcp_manager


@router.post("/mcp/call", response_model=MCPCallResponse)
async def call_mcp_tool(
    payload: MCPCallRequest,
    mcp_manager: MCPManager = Depends(get_mcp_manager),
) -> MCPCallResponse:
    try:
        result = await mcp_manager.call_tool(payload.tool, payload.arguments)
    except MCPClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MCPCallResponse(
        is_error=result.isError,
        content=[block.model_dump(mode="json") for block in result.content],
        structured_content=result.structuredContent,
    )
