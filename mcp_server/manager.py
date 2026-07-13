from mcp_server.client import MCPClient


class MCPManager:

    def __init__(self):
        self.client = MCPClient()
        self.tools = []

    async def initialize(self):
        await self.client.connect()
        self.tools = await self.client.list_tools()

    async def shutdown(self):
        await self.client.disconnect()

    def is_connected(self):
        return self.client.is_connected()

    def get_tools(self):
        return self.tools

    async def call_tool(self, name, arguments=None):
        return await self.client.call_tool(name, arguments)