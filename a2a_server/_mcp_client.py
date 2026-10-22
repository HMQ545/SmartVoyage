"""MCP 客户端封装：A2A 服务层通过 stdio 调用 mcp_server 下的 MCP 服务。

每次调用启动一个到目标 MCP 服务的 stdio 子进程连接，执行完即关闭。
注意：Windows 上必须显式传递 env，否则子进程收不到环境变量
（如 QWEATHER_API_KEY）。
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _params(server_module: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", server_module],
        env={k: v for k, v in os.environ.items() if k != "PYTHONNOUSERSITE"},
        cwd=PROJECT_ROOT,
    )


async def _async_call(server_module: str, tool_name: str, arguments: dict) -> str:
    async with stdio_client(_params(server_module)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
    is_error = getattr(result, "isError", getattr(result, "is_error", False))
    if is_error:
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        return f"[MCP 调用失败] {tool_name}: {text}"
    return "".join(c.text for c in result.content if hasattr(c, "text"))


def call_mcp(server_module: str, tool_name: str, arguments: dict) -> str:
    """同步调用指定 MCP 服务的工具，返回工具执行结果字符串。"""
    try:
        return asyncio.run(_async_call(server_module, tool_name, arguments))
    except Exception as exc:  # noqa: BLE001
        return (
            f"[MCP 连接失败] {server_module}/{tool_name}: "
            f"{type(exc).__name__}: {exc}"
        )
