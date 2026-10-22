"""天气 MCP 服务：通过和风天气 API 提供真实天气数据。

架构：Agent -> a2a_server.weather_server -> 本 MCP 服务（stdio 子进程）
运行：python -m mcp_server.mcp_weather_server

流程：
1. GeoAPI 城市搜索（geo/v2/city/lookup）：城市名 -> Location ID / 经纬度
2. 当天 -> 实时天气（/v7/weather/now）
   未来日期 -> 每日预报（/weather/v1/daily/{lat}/{lon}，最多未来 10 天）

域名与 Key 来自 config.py（weather_api_host / QWEATHER_API_KEY）。
"""

import datetime as dt

import requests
from config import Config
from mcp.server.fastmcp import FastMCP

_conf = Config()
mcp = FastMCP("weather-mcp")


def _host() -> str:
    host = _conf.weather_api_host
    if not host:
        raise ValueError("和风天气 API 域名未配置：请设置 QWEATHER_API_HOST 环境变量")
    return host


def _key() -> str:
    return _conf.weather_api_key


def _city_lookup(city: str) -> dict:
    """城市名 -> 位置信息（优先取 type=city 的结果）。"""
    key = _key()
    if not key:
        raise ValueError("和风天气 Key 未配置：请设置 QWEATHER_API_KEY 环境变量")
    url = f"https://{_host()}/geo/v2/city/lookup"
    resp = requests.get(url, params={"location": city, "key": key}, timeout=10)
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(
            f"和风天气接口返回非 JSON（HTTP {resp.status_code}）：{resp.text[:200]}"
        )
    error = data.get("error")
    if error or data.get("code") not in ("200", 200):
        detail = error.get("detail") if isinstance(error, dict) else data.get("code")
        raise ValueError(f"和风天气接口调用失败（HTTP {resp.status_code}）：{detail}")
    locations = data.get("location") or []
    if not locations:
        raise ValueError(f"未找到城市 [{city}]")
    best = next((loc for loc in locations if loc.get("type") == "city"), locations[0])
    return {
        "name": best.get("name", city),
        "id": best.get("id", ""),
        "lat": best.get("lat", ""),
        "lon": best.get("lon", ""),
    }


def _parse_date(date: str) -> dt.date:
    """解析用户输入的日期，支持 今天/明天/后天 与 YYYY-MM-DD，默认今天。"""
    today = dt.date.today()
    value = (date or "").strip()
    if value in ("", "今天", "today"):
        return today
    if value in ("明天", "tomorrow"):
        return today + dt.timedelta(days=1)
    if value in ("后天",):
        return today + dt.timedelta(days=2)
    return dt.date.fromisoformat(value)


def _format_now(city: str, now: dict) -> str:
    text = now.get("text", "未知")
    temp = now.get("temp", "-")
    feels_like = now.get("feelsLike", "-")
    wind_dir = now.get("windDir", "-")
    wind_scale = now.get("windScale", "-")
    humidity = now.get("humidity", "-")
    precip = now.get("precip", "0")
    return (
        f"{city}实时天气：{text}，气温 {temp}°C（体感 {feels_like}°C），"
        f"{wind_dir} {wind_scale} 级，相对湿度 {humidity}%，降水量 {precip}mm。"
    )


def _format_daily(city: str, date_str: str, day: dict) -> str:
    temp_max = day["temperatureMax"]["value"] if day.get("temperatureMax") else "-"
    temp_min = day["temperatureMin"]["value"] if day.get("temperatureMin") else "-"
    daytime = day.get("daytime") or {}
    nighttime = day.get("nighttime") or {}
    day_text = (daytime.get("condition") or {}).get("text", "未知")
    night_text = (nighttime.get("condition") or {}).get("text", "未知")
    humidity = daytime.get("humidity")
    precip_prob = (daytime.get("precipitation") or {}).get("probability")
    parts = [
        f"{city} {date_str} 天气预报：白天{day_text}，最高{temp_max}°C，"
        f"最低{temp_min}°C，夜间{night_text}"
    ]
    if humidity is not None:
        parts.append(f"白天平均湿度 {int(round(humidity * 100))}%")
    if precip_prob is not None:
        parts.append(f"降水概率 {int(round(precip_prob * 100))}%")
    return "，".join(parts) + "。"


@mcp.tool()
def query_weather(city: str, date: str = "") -> str:
    """查询指定城市、指定日期的真实天气（和风天气 API）。

    Args:
        city: 城市名称，如 "北京"、"上海"、"南京"
        date: 查询日期，支持 "YYYY-MM-DD"、"今天"、"明天"、"后天"，留空表示今天
    """
    try:
        target = _parse_date(date)
        loc = _city_lookup(city)

        # 当天：实时天气
        if target == dt.date.today():
            url = f"https://{_host()}/v7/weather/now"
            resp = requests.get(
                url, params={"location": loc["id"], "key": _key()}, timeout=10
            )
            data = resp.json()
            if data.get("code") != "200" or not data.get("now"):
                return f"天气查询失败：{city}（code={data.get('code')}）"
            return _format_now(loc["name"], data["now"])

        # 未来：每日预报
        delta_days = (target - dt.date.today()).days
        if delta_days < 0:
            return f"无法查询过去的天气（{city} {target.isoformat()}）。"
        if delta_days > 10:
            return f"只能查询未来 10 天内的天气预报（{city} {target.isoformat()}）。"

        url = f"https://{_host()}/weather/v1/daily/{loc['lat']}/{loc['lon']}"
        resp = requests.get(
            url,
            params={"days": delta_days + 1, "localTime": "true", "key": _key()},
            timeout=10,
        )
        data = resp.json()
        if not data.get("days"):
            return f"天气查询失败：{city}（响应：{str(data)[:200]}）"
        date_str = target.isoformat()
        for day in data["days"]:
            start = (day.get("forecastStartTime") or "")[:10]
            if start == date_str:
                return _format_daily(loc["name"], date_str, day)
        return f"未找到 {city} {date_str} 的预报数据。"
    except Exception as exc:  # noqa: BLE001
        return f"天气查询失败：{type(exc).__name__}: {exc}"


if __name__ == "__main__":
    mcp.run()
