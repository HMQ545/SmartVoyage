"""A2A 旅游服务层：通过 MCP 客户端调用 mcp_server.mcp_trip_server。

对外保持函数签名与 TOOLS 导出不变，chat_service.py 无需改动。
"""

from a2a_server._mcp_client import call_mcp

MCP_SERVER = "mcp_server.mcp_trip_server"


def query_car_rental(city: str, date: str) -> str:
    """查询指定城市在指定日期的租车信息。

    Args:
        city: 租车城市
        date: 用车日期，格式 YYYY-MM-DD
    """
    return call_mcp(MCP_SERVER, "query_car_rental", {"city": city, "date": date})


def query_tour_group(city: str, days: int) -> str:
    """查询指定城市、天数的旅游团线路。

    Args:
        city: 目的地城市
        days: 行程天数
    """
    return call_mcp(MCP_SERVER, "query_tour_group", {"city": city, "days": days})


def query_insurance(insurance_type: str, days: int) -> str:
    """查询旅行保险产品信息。

    Args:
        insurance_type: 保险类型，如 "境内旅行险"、"境外旅行险"
        days: 保障天数
    """
    return call_mcp(
        MCP_SERVER, "query_insurance", {"insurance_type": insurance_type, "days": days}
    )


def book_car_rental(car_type: str, city: str, date: str, passenger: str) -> str:
    """预定指定城市的租车服务。

    Args:
        car_type: 车型，如 "SUV"
        city: 取车城市
        date: 取车日期，格式 YYYY-MM-DD
        passenger: 用车人姓名
    """
    return call_mcp(
        MCP_SERVER,
        "book_car_rental",
        {"car_type": car_type, "city": city, "date": date, "passenger": passenger},
    )


def book_tour_group(tour_id: str, passenger: str) -> str:
    """预定旅游团线路。

    Args:
        tour_id: 旅游团编号，如 "YN001"
        passenger: 参团人姓名
    """
    return call_mcp(
        MCP_SERVER, "book_tour_group", {"tour_id": tour_id, "passenger": passenger}
    )


def book_insurance(insurance_type: str, days: int, passenger: str) -> str:
    """购买旅行保险。

    Args:
        insurance_type: 保险类型，如 "境内旅行险"
        days: 保障天数
        passenger: 被保人姓名
    """
    return call_mcp(
        MCP_SERVER,
        "book_insurance",
        {"insurance_type": insurance_type, "days": days, "passenger": passenger},
    )


TOOLS = [
    query_car_rental,
    query_tour_group,
    query_insurance,
    book_car_rental,
    book_tour_group,
    book_insurance,
]
