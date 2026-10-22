"""票务 MCP 服务。

架构：Agent -> a2a_server.ticket_server -> 本 MCP 服务（stdio 子进程）
运行：python -m mcp_server.mcp_ticket_server

工具：
- 查询（读取 MySQL travel_rag 数据库）：机票 query_flight、火车票 query_train、演唱会票 query_concert
- 预定（保持 print 模拟）：book_flight / book_train / book_concert

数据库连接通过 MYSQL_* 环境变量配置；
可用环境变量 MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE 覆盖。
"""

import os

import pymysql
from mcp.server.fastmcp import FastMCP
from pymysql.cursors import DictCursor

mcp = FastMCP("ticket-mcp")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "travel_rag"),
    "charset": "utf8mb4",
    "connect_timeout": 5,
}

_FLIGHT_SQL = """
SELECT flight_number, departure_time, arrival_time, cabin_type, remaining_seats, price
FROM flight_tickets
WHERE departure_city = %s AND arrival_city = %s AND DATE(departure_time) = %s
ORDER BY departure_time, flight_number,
         FIELD(cabin_type, '经济舱', '商务舱', '头等舱')
"""

_TRAIN_SQL = """
SELECT train_number, departure_time, arrival_time, seat_type, remaining_seats, price
FROM train_tickets
WHERE departure_city = %s AND arrival_city = %s AND DATE(departure_time) = %s
ORDER BY departure_time, train_number,
         FIELD(seat_type, '二等座', '一等座', '商务座', '一等卧')
"""

_CONCERT_SQL = """
SELECT artist, venue, start_time, end_time, ticket_type, remaining_seats, price
FROM concert_tickets
WHERE city = %s AND DATE(start_time) = %s
ORDER BY start_time, artist, price DESC
"""


def _fetchall(sql: str, params: tuple) -> list:
    """执行查询并返回全部行（dict 列表），连接用完即关闭。"""
    conn = pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def _fmt_price(price) -> str:
    """票价格式化：整数不带小数，非整数保留小数。"""
    return f"{float(price):g}"


@mcp.tool()
def query_flight(departure: str, arrival: str, date: str) -> str:
    """查询指定日期从出发地到目的地的航班信息。

    Args:
        departure: 出发城市，如 "上海"
        arrival: 目的城市，如 "南京"
        date: 出行日期，格式 YYYY-MM-DD，如 "2026-08-03"
    """
    try:
        rows = _fetchall(_FLIGHT_SQL, (departure, arrival, date))
    except Exception as exc:  # noqa: BLE001
        return f"【机票查询失败】数据库连接失败：{type(exc).__name__}: {exc}"
    if not rows:
        return f"【机票】{date} {departure}→{arrival} 暂无航班信息。"

    flights = {}
    for row in rows:
        flights.setdefault(row["flight_number"], []).append(row)

    lines = [f"【机票】{date} {departure}→{arrival} 共{len(flights)}个航班："]
    for idx, (flight_no, items) in enumerate(flights.items(), 1):
        first = items[0]
        cabins = "；".join(
            f"{it['cabin_type']} ¥{_fmt_price(it['price'])} 余{it['remaining_seats']}张"
            for it in items
        )
        lines.append(
            f"{idx}. {flight_no} {first['departure_time']:%H:%M}-"
            f"{first['arrival_time']:%H:%M} {cabins}"
        )
    return "\n".join(lines)


@mcp.tool()
def query_train(departure: str, arrival: str, date: str) -> str:
    """查询指定日期从出发地到目的地的火车票信息。

    Args:
        departure: 出发城市，如 "上海"
        arrival: 目的城市，如 "南京"
        date: 出行日期，格式 YYYY-MM-DD，如 "2026-08-03"
    """
    try:
        rows = _fetchall(_TRAIN_SQL, (departure, arrival, date))
    except Exception as exc:  # noqa: BLE001
        return f"【火车票查询失败】数据库连接失败：{type(exc).__name__}: {exc}"
    if not rows:
        return f"【火车票】{date} {departure}→{arrival} 暂无车次信息。"

    trains = {}
    for row in rows:
        trains.setdefault(row["train_number"], []).append(row)

    lines = [f"【火车票】{date} {departure}→{arrival} 共{len(trains)}个车次："]
    for idx, (train_no, items) in enumerate(trains.items(), 1):
        first = items[0]
        seats = "；".join(
            f"{it['seat_type']} ¥{_fmt_price(it['price'])} 余{it['remaining_seats']}张"
            for it in items
        )
        lines.append(
            f"{idx}. {train_no} {first['departure_time']:%H:%M}-"
            f"{first['arrival_time']:%H:%M} {seats}"
        )
    return "\n".join(lines)


@mcp.tool()
def query_concert(city: str, date: str) -> str:
    """查询指定城市在指定日期的演唱会门票信息。

    Args:
        city: 演唱会所在城市，如 "上海"
        date: 演出日期，格式 YYYY-MM-DD，如 "2026-08-08"
    """
    try:
        rows = _fetchall(_CONCERT_SQL, (city, date))
    except Exception as exc:  # noqa: BLE001
        return f"【演唱会查询失败】数据库连接失败：{type(exc).__name__}: {exc}"
    if not rows:
        return f"【演唱会】{city} {date} 暂无演唱会信息。"

    shows = {}
    for row in rows:
        key = (row["artist"], row["venue"], row["start_time"])
        shows.setdefault(key, []).append(row)

    lines = [f"【演唱会】{city} {date} 共{len(shows)}场："]
    for idx, ((artist, venue, start_time), items) in enumerate(shows.items(), 1):
        end_time = items[0]["end_time"]
        ticket_types = "；".join(
            f"{it['ticket_type']} ¥{_fmt_price(it['price'])} 余{it['remaining_seats']}张"
            for it in items
        )
        lines.append(
            f"{idx}. {artist} @ {venue} {start_time:%H:%M}-{end_time:%H:%M}\n"
            f"   {ticket_types}"
        )
    return "\n".join(lines)


@mcp.tool()
def book_flight(flight_no: str, passenger: str, date: str) -> str:
    """预定指定航班号的机票。

    Args:
        flight_no: 航班号，如 "CA1234"
        passenger: 乘机人姓名
        date: 出行日期，格式 YYYY-MM-DD
    """
    return (
        f"【模拟】已为乘客 {passenger} 预定 {date} 航班 {flight_no} 的机票，"
        "订单号 MOCK-FL-0001。"
    )


@mcp.tool()
def book_train(train_no: str, passenger: str, date: str) -> str:
    """预定指定车次的火车票。

    Args:
        train_no: 车次号，如 "G102"
        passenger: 乘车人姓名
        date: 出行日期，格式 YYYY-MM-DD
    """
    return (
        f"【模拟】已为乘客 {passenger} 预定 {date} 车次 {train_no} 的火车票，"
        "订单号 MOCK-TR-0001。"
    )


@mcp.tool()
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
    return (
        f"【模拟】已为 {passenger} 预定 {city} {date} {concert_name} "
        f"门票 {ticket_count} 张，订单号 MOCK-CN-0001。"
    )


if __name__ == "__main__":
    mcp.run()
