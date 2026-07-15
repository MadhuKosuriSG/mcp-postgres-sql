from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from api.auth import router as auth_router
from api.chat import router as chat_router
from api.mcp import router as mcp_router
from core.db import dispose_engine
from mcp_server.manager import MCPManager
from services.chat_service import ChatService

mcp_manager = MCPManager()
chat_service = ChatService(mcp_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await mcp_manager.initialize()

    yield

    # Shutdown
    await mcp_manager.shutdown()
    await dispose_engine()


app = FastAPI(
    title="FastAPI MCP",
    version="1.0.0",
    lifespan=lifespan,   # <-- This was missing
)
app.state.chat_service = chat_service
app.state.mcp_manager = mcp_manager
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(auth_router)


@app.get("/")
async def root():
    return {
        "message": "FastAPI MCP Server is running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mcp_connected": mcp_manager.is_connected(),
        "tool_count": len(mcp_manager.get_tools())
    }