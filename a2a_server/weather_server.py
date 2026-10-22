"""A2A 天气服务层：通过 MCP 客户端调用 mcp_server.mcp_weather_server。

对外保持 query_weather 函数签名与 TOOLS 导出不变，
chat_service.py 无需改动。
"""

from a2a_server._mcp_client import call_mcp

MCP_SERVER = "mcp_server.mcp_weather_server"


def query_weather(city: str, date: str = "") -> str:
    """查询指定城市、指定日期的真实天气（和风天气 API）。

    Args:
        city: 城市名称，如 "北京"、"上海"、"南京"
        date: 查询日期，支持 "YYYY-MM-DD"、"今天"、"明天"、"后天"，留空表示今天
    """
    return call_mcp(MCP_SERVER, "query_weather", {"city": city, "date": date})


TOOLS = [query_weather]
