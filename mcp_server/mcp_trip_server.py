"""旅游 MCP 服务。

架构：Agent -> a2a_server.trip_server -> 本 MCP 服务（stdio 子进程）
运行：python -m mcp_server.mcp_trip_server

工具：
- 查询：租车/保险读取 MySQL travel_rag；旅游团走 Milvus 向量检索（DashScope text-embedding-v3）
- 预定（保持 print 模拟）：book_car_rental / book_tour_group / book_insurance

数据库连接通过 MYSQL_* 环境变量配置；
可用环境变量 MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE 覆盖。
Milvus：127.0.0.1:19531（edu_agent 实例），collection tour_groups；向量由 DashScope qwen3.7-text-embedding 生成（1024 维），
API Key 从环境变量 DASHSCOPE_API_KEY 读取；Milvus 地址可用 MILVUS_HOST / MILVUS_PORT 覆盖。
"""

import os

import pymysql
import requests
from mcp.server.fastmcp import FastMCP
from pymysql.cursors import DictCursor

mcp = FastMCP("trip-mcp")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "travel_rag"),
    "charset": "utf8mb4",
    "connect_timeout": 5,
}

MILVUS_BASE = (
    f"http://{os.getenv('MILVUS_HOST', '127.0.0.1')}:"
    f"{int(os.getenv('MILVUS_PORT', '19531'))}/v2/vectordb"
)
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "tour_groups")

EMBEDDING_URL = os.getenv(
    "EMBEDDING_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3.7-text-embedding")
EMBEDDING_DIM = 1024

CAR_RENTAL_SQL = """
SELECT company, car_type, car_model, price_per_day, total_available,
       transmission, seats, deposit
FROM car_rentals
WHERE pickup_city = %s AND pickup_date = %s
ORDER BY price_per_day, company, car_model
"""

INSURANCE_SQL = """
SELECT name, company, insurance_type, price, duration_days, coverage, max_coverage
FROM insurances
WHERE insurance_type IN ({placeholders}) AND duration_days >= %s
ORDER BY price
"""

# 保险类型智能映射：库内类型 -> 常见输入
INSURANCE_TYPES = ("综合型", "意外型", "医疗型", "境外型")


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
    """金额格式化：千分位，整数不带小数，非整数保留小数。"""
    text = f"{float(price):,.2f}"
    return text[:-3] if text.endswith(".00") else text


def _embed(text: str) -> list:
    """调用 DashScope 生成查询向量（qwen3.7-text-embedding，1024 维）。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未设置")
    payload = {
        "model": EMBEDDING_MODEL,
        "input": [text],
        "dimensions": EMBEDDING_DIM,
    }
    resp = requests.post(
        EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    result = resp.json()
    if resp.status_code != 200 or "data" not in result:
        msg = result.get("error", {}).get("message", resp.text)
        raise RuntimeError(f"DashScope embedding 失败（HTTP {resp.status_code}）：{msg}")
    return result["data"][0]["embedding"]


def _milvus_post(path: str, payload: dict) -> dict:
    """调用 Milvus REST 接口，成功返回 JSON（code 0/200 视为成功）。"""
    resp = requests.post(f"{MILVUS_BASE}{path}", json=payload, timeout=30)
    result = resp.json()
    if resp.status_code != 200 or result.get("code") not in (0, 200):
        raise RuntimeError(
            f"Milvus {path} 失败：{result.get('code')} {result.get('message', resp.text)}"
        )
    return result


def _search_tour_groups(vector: list, expr: str = None, limit: int = 3) -> list:
    """在 tour_groups 集合中做向量检索，返回命中列表（含 entity 与 distance）。"""
    _milvus_post("/collections/load", {"collectionName": MILVUS_COLLECTION})
    payload = {
        "collectionName": MILVUS_COLLECTION,
        "data": [vector],
        "annsField": "embedding",
        "limit": limit,
        "outputFields": [
            "tour_id",
            "tour_name",
            "city",
            "days",
            "price",
            "total_seats",
            "remaining_seats",
            "agency",
            "rating",
            "departure_dates",
            "highlights",
        ],
    }
    if expr:
        payload["filter"] = expr
    result = _milvus_post("/entities/search", payload)
    return result.get("data", []) or []


@mcp.tool()
def query_car_rental(city: str, date: str) -> str:
    """查询指定城市在指定日期的租车信息。

    Args:
        city: 租车城市，如 "成都"
        date: 用车日期，格式 YYYY-MM-DD
    """
    try:
        rows = _fetchall(CAR_RENTAL_SQL, (city, date))
    except Exception as exc:  # noqa: BLE001
        return f"【租车查询失败】数据库连接失败：{type(exc).__name__}: {exc}"
    if not rows:
        return f"【租车】{city} {date} 暂无租车信息。"

    lines = [f"【租车】{city} {date} 共{len(rows)}辆可租："]
    for idx, r in enumerate(rows, 1):
        lines.append(
            f"{idx}. {r['car_type']} {r['car_model']}（{r['company']}）"
            f"¥{_fmt_price(r['price_per_day'])}/天 可租{r['total_available']}辆 "
            f"{r['transmission']} {r['seats']}座 押金¥{_fmt_price(r['deposit'])}"
        )
    return "\n".join(lines)


@mcp.tool()
def query_tour_group(city: str, days: int) -> str:
    """查询指定城市、天数的旅游团线路（Milvus 向量检索）。

    Args:
        city: 目的地城市，如 "成都"
        days: 行程天数，如 5
    """
    try:
        vector = _embed(f"{city} {days}日游")
    except Exception as exc:  # noqa: BLE001
        return f"【旅游团查询失败】向量生成失败：{type(exc).__name__}: {exc}"
    try:
        hits = _search_tour_groups(vector, expr=f'city == "{city}"')
        if not hits:
            hits = _search_tour_groups(vector)
    except Exception as exc:  # noqa: BLE001
        return f"【旅游团查询失败】Milvus 检索失败：{type(exc).__name__}: {exc}"
    if not hits:
        return f"【旅游团】{city} {days}日游 暂无匹配线路。"

    lines = [f"【旅游团】{city} {days}日游 推荐线路："]
    for idx, hit in enumerate(hits, 1):
        e = hit.get("entity") if isinstance(hit.get("entity"), dict) else hit
        score = hit.get("distance", 0)
        lines.append(
            f"{idx}. [{e.get('tour_id')}] {e.get('tour_name')}"
            f"（{e.get('city')} {e.get('days')}天）"
            f"¥{_fmt_price(e.get('price') or 0)} 评分{e.get('rating')} "
            f"旅行社:{e.get('agency')} 出发日期:{e.get('departure_dates')} "
            f"余{e.get('remaining_seats')}位 相似度{score:.3f}\n"
            f"   亮点：{e.get('highlights')}"
        )
    return "\n".join(lines)


@mcp.tool()
def query_insurance(insurance_type: str, days: int) -> str:
    """查询旅行保险产品信息。

    Args:
        insurance_type: 保险类型，如 "境外旅行险"、"境内旅行险"，或库内类型名
            （综合型/意外型/医疗型/境外型）
        days: 保障天数需求，产品按 duration_days >= days 过滤
    """
    t = (insurance_type or "").strip()
    if t in INSURANCE_TYPES:
        types = [t]
    elif "境外" in t:
        types = ["境外型"]
    else:
        types = ["综合型", "意外型", "医疗型"]

    placeholders = ", ".join(["%s"] * len(types))
    sql = INSURANCE_SQL.format(placeholders=placeholders)
    try:
        rows = _fetchall(sql, tuple(types) + (days,))
    except Exception as exc:  # noqa: BLE001
        return f"【保险查询失败】数据库连接失败：{type(exc).__name__}: {exc}"
    if not rows:
        return f"【保险】{insurance_type}（保障≥{days}天）暂无保险产品。"

    lines = [
        f"【保险】{insurance_type}（保障≥{days}天）共{len(rows)}款："
    ]
    for idx, r in enumerate(rows, 1):
        lines.append(
            f"{idx}. {r['name']}（{r['insurance_type']}）{r['company']} "
            f"¥{_fmt_price(r['price'])}/份 保障{r['duration_days']}天 "
            f"最高赔付¥{_fmt_price(r['max_coverage'])}\n"
            f"   保障范围：{r['coverage']}"
        )
    return "\n".join(lines)


@mcp.tool()
def book_car_rental(car_type: str, city: str, date: str, passenger: str) -> str:
    """预定指定城市的租车服务。

    Args:
        car_type: 车型，如 "SUV"
        city: 取车城市
        date: 取车日期，格式 YYYY-MM-DD
        passenger: 用车人姓名
    """
    return (
        f"【模拟】已为 {passenger} 预定 {city} {date} 的{car_type}，"
        "订单号 MOCK-CR-0001。"
    )


@mcp.tool()
def book_tour_group(tour_id: str, passenger: str) -> str:
    """预定旅游团线路。

    Args:
        tour_id: 旅游团编号，如 "YN001"
        passenger: 参团人姓名
    """
    return f"【模拟】已为 {passenger} 预定旅游团 {tour_id}，订单号 MOCK-TG-0001。"


@mcp.tool()
def book_insurance(insurance_type: str, days: int, passenger: str) -> str:
    """购买旅行保险。

    Args:
        insurance_type: 保险类型，如 "境内旅行险"
        days: 保障天数
        passenger: 被保人姓名
    """
    return (
        f"【模拟】已为 {passenger} 购买{insurance_type}（{days}天），"
        "保单号 MOCK-IN-0001。"
    )


if __name__ == "__main__":
    mcp.run()
