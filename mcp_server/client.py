"""MCP client for the PostgreSQL MCP server (postgres-mcp), built on the official Python MCP SDK.

All MCP protocol details (transport, session lifecycle, handshake) are contained here.
Callers (e.g. MCPManager) only see connect / disconnect / list_tools / is_connected.
"""

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool

logger = logging.getLogger(__name__)


class MCPClientError(RuntimeError):
    """Raised when the MCP session cannot be established, torn down, or queried."""


class MCPClient:
    """Owns a single MCP ClientSession against the PostgreSQL MCP server.

    Launches `postgres-mcp` via `uvx` as a subprocess, performs the MCP
    initialize handshake over stdio, and keeps the resulting session open
    for reuse across multiple calls (e.g. list_tools, future call_tool).
    """

    def __init__(
        self,
        database_uri: Optional[str] = None,
        command: str = "uvx",
        python_version: str = "3.12",
    ) -> None:
        self._database_uri = database_uri or os.environ.get("DATABASE_URI")
        self._command = command
        self._python_version = python_version

        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Launch postgres-mcp via uvx and establish an initialized MCP session."""
        async with self._lock:
            if self._connected:
                logger.warning("connect() called while already connected; ignoring")
                return

            if not self._database_uri:
                raise MCPClientError(
                    "DATABASE_URI is not set. Configure it in the environment before connecting."
                )

            server_params = StdioServerParameters(
                command=self._command,
                args=["--python", self._python_version, "postgres-mcp", self._database_uri],
            )

            exit_stack = AsyncExitStack()
            try:
                read_stream, write_stream = await exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                session = await exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
            except Exception as exc:
                await exit_stack.aclose()
                logger.exception("Failed to establish MCP session with postgres-mcp")
                raise MCPClientError("Failed to connect to the PostgreSQL MCP server") from exc

            self._exit_stack = exit_stack
            self._session = session
            self._connected = True
            logger.info("MCP session established with postgres-mcp (command=%s)", self._command)

    async def disconnect(self) -> None:
        """Close the ClientSession and stop the postgres-mcp process gracefully."""
        async with self._lock:
            if not self._connected or self._exit_stack is None:
                logger.debug("disconnect() called while not connected; ignoring")
                return

            try:
                await self._exit_stack.aclose()
                logger.info("MCP session closed and postgres-mcp process stopped")
            except Exception as exc:
                logger.exception("Error while closing MCP session/process")
                raise MCPClientError(
                    "Failed to disconnect cleanly from the PostgreSQL MCP server"
                ) from exc
            finally:
                self._session = None
                self._exit_stack = None
                self._connected = False

    async def list_tools(self) -> list[Tool]:
        """Return the tools discovered from the MCP server."""
        if not self._connected or self._session is None:
            raise MCPClientError("Cannot list tools: MCP session is not connected")

        try:
            result = await self._session.list_tools()
        except Exception as exc:
            logger.exception("Failed to list tools from the MCP server")
            raise MCPClientError("Failed to retrieve tool list from the MCP server") from exc

        return result.tools

    async def call_tool(
        self, name: str, arguments: Optional[dict] = None
    ) -> CallToolResult:
        """Invoke a tool on the MCP server, reusing the existing session, and return its result."""
        if not self._connected or self._session is None:
            raise MCPClientError(f"Cannot call tool '{name}': MCP session is not connected")

        try:
            return await self._session.call_tool(name, arguments)
        except Exception as exc:
            logger.exception("Failed to call tool %r", name)
            raise MCPClientError(f"Failed to call tool '{name}'") from exc

    def is_connected(self) -> bool:
        """Return the current connection status."""
        return self._connected
