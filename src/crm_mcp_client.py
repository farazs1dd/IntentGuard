"""A real MCP client; administration tools never enter the model's tool catalog."""
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.sandbox_crm import ARGUMENTS


class CRMConnector:
    async def __aenter__(self):
        self.stack = AsyncExitStack()
        await self.stack.__aenter__()
        try:
            root = str(Path(__file__).resolve().parents[1])
            # The connector requires no credentials. Don't forward LLM/AIRS keys.
            env = {k: v for k, v in os.environ.items()
                   if k in {"PATH", "HOME", "SYSTEMROOT", "TMPDIR"}}
            env["PYTHONPATH"] = root
            params = StdioServerParameters(
                command=sys.executable, args=["-m", "src.crm_mcp_server"],
                cwd=root, env=env,
            )
            read, write = await self.stack.enter_async_context(stdio_client(params))
            self.client = await self.stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(self.client.initialize(), 15)
            catalog = await asyncio.wait_for(self.client.list_tools(), 15)
            self.tools = [
                {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
                for t in catalog.tools if t.name in ARGUMENTS
            ]
            if {t["name"] for t in self.tools} != set(ARGUMENTS):
                raise ValueError("Sandbox MCP tool discovery failed")
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        await self.stack.__aexit__(*args)

    async def invoke(self, tool, arguments):
        result = await asyncio.wait_for(self.client.call_tool(tool, arguments), 15)
        if result.isError:
            raise ValueError("Sandbox MCP returned a tool error")
        texts = [c.text for c in result.content if c.type == "text"]
        return json.loads("\n".join(texts))

    async def execute(self, state, tool, arguments):
        await self.invoke("sandbox_restore", {"snapshot": json.dumps(state)})
        result = await self.invoke(tool, arguments)
        updated = await self.invoke("sandbox_snapshot", {})
        return result, updated
