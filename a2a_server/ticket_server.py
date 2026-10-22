"""A2A 票务服务层：通过 MCP 客户端调用 mcp_server.mcp_ticket_server。

对外保持函数签名与 TOOLS 导出不变，chat_service.py 无需改动。
"""

from a2a_server._mcp_client import call_mcp

MCP_SERVER = "mcp_server.mcp_ticket_server"


def query_flight(departure: str, arrival: str, date: str) -> str:
    """查询指定日期从出发地到目的地的航班信息。

    Args:
        departure: 出发城市，如 "上海"
        arrival: 目的城市，如 "北京"
        date: 出行日期，格式 YYYY-MM-DD，如 "2026-08-03"
    """
    return call_mcp(
        MCP_SERVER,
        "query_flight",
        {"departure": departure, "arrival": arrival, "date": date},
    )


def query_train(departure: str, arrival: str, date: str) -> str:
    """查询指定日期从出发地到目的地的火车票信息。

    Args:
        departure: 出发城市
        arrival: 目的城市
        date: 出行日期，格式 YYYY-MM-DD
    """
    return call_mcp(
        MCP_SERVER,
        "query_train",
        {"departure": departure, "arrival": arrival, "date": date},
    )


def query_concert(city: str, date: str) -> str:
    """查询指定城市在指定日期的演唱会门票信息。

    Args:
        city: 演唱会所在城市
        date: 演出日期，格式 YYYY-MM-DD
    """
    return call_mcp(MCP_SERVER, "query_concert", {"city": city, "date": date})


def book_flight(flight_no: str, passenger: str, date: str) -> str:
    """预定指定航班号的机票。

    Args:
        flight_no: 航班号，如 "CA1234"
        passenger: 乘机人姓名
        date: 出行日期，格式 YYYY-MM-DD
    """
    return call_mcp(
        MCP_SERVER,
        "book_flight",
        {"flight_no": flight_no, "passenger": passenger, "date": date},
    )


def book_train(train_no: str, passenger: str, date: str) -> str:
    """预定指定车次的火车票。

    Args:
        train_no: 车次号，如 "G102"
        passenger: 乘车人姓名
        date: 出行日期，格式 YYYY-MM-DD
    """
    return call_mcp(
        MCP_SERVER,
        "book_train",
        {"train_no": train_no, "passenger": passenger, "date": date},
    )


def book_concert(
    concert_name: str, city: str, date: str, ticket_count: int = 1, passenger: str = ""
) -> str:
    """预定演唱会门票。

    Args:
        concert_name: 演唱会名称，如 "周杰伦嘉年华演唱会"
        city: 演出城市
        date: 演出日期，格式 YYYY-MM-DD
        ticket_count: 购买张数，默认 1
        passenger: 购票人姓名
    """
    return call_mcp(
        MCP_SERVER,
        "book_concert",
        {
            "concert_name": concert_name,
            "city": city,
            "date": date,
            "ticket_count": ticket_count,
            "passenger": passenger,
        },
    )


TOOLS = [
    query_flight,
    query_train,
    query_concert,
    book_flight,
    book_train,
    book_concert,
]
