"""会话记忆与上下文管理（仅使用新表 sessions / session_messages，不读写任何现有表）。

- sessions：会话列表（标题/时间）
- session_messages：会话消息历史（role/content/steps_json/message_order）
- 上下文画像不再持久化：每轮从会话历史 + 当前消息规则抽取（城市/日期/意图）

数据库连接通过 MYSQL_* 环境变量配置。
"""

import json
import os
import re
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "travel_rag"),
    "charset": "utf8mb4",
    "connect_timeout": 5,
}

# 常见城市/目的地（用于上下文抽取）
KNOWN_CITIES = [
    "北京", "上海", "南京", "成都", "广州", "深圳", "杭州", "苏州", "重庆",
    "厦门", "青岛", "大连", "武汉", "长沙", "西安", "桂林", "昆明", "丽江",
    "西双版纳", "三亚", "海口", "拉萨", "乌鲁木齐", "哈尔滨", "天津",
]

# 意图关键词 -> intent key（与 config.intent 对齐）
INTENT_KEYWORDS = [
    ("天气", "weather"),
    ("机票", "flight"), ("航班", "flight"),
    ("火车", "train"), ("高铁", "train"),
    ("演唱会", "concert"),
    ("租车", "car_rental"),
    ("旅游团", "tour_group"), ("线路", "tour_group"),
    ("保险", "insurance"),
]

CTX_CAP = 3  # 每个维度最多保留条数


def _connect():
    return pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)


class SessionStore:
    """会话与消息的 MySQL 持久化（仅使用 sessions / session_messages 新表）。"""

    def ensure_session(self, session_id: str, first_text: str) -> None:
        """会话不存在则创建，标题取首条消息（截断 50 字）。"""
        title = (first_text or "").strip().replace("\n", " ")[:50] or "新会话"
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT IGNORE INTO sessions (session_id, title) VALUES (%s, %s)",
                    (session_id, title),
                )
            conn.commit()
        finally:
            conn.close()

    def append_message(self, session_id: str, role: str, content: str,
                       steps: list = None) -> None:
        """追加一条消息，message_order 自动递增；steps 存 JSON。"""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(MAX(message_order), 0) + 1 AS nxt "
                    "FROM session_messages WHERE session_id = %s",
                    (session_id,),
                )
                nxt = cur.fetchone()["nxt"]
                steps_json = json.dumps(steps, ensure_ascii=False) if steps else None
                cur.execute(
                    "INSERT INTO session_messages "
                    "(session_id, role, content, steps_json, message_order) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (session_id, role, content, steps_json, nxt),
                )
            conn.commit()
        finally:
            conn.close()

    def load_messages(self, session_id: str, limit: int = 20) -> list:
        """加载最近 N 条消息（升序）。"""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role, content FROM session_messages "
                    "WHERE session_id = %s ORDER BY message_order DESC LIMIT %s",
                    (session_id, limit),
                )
                rows = cur.fetchall()
            return list(reversed(rows))
        finally:
            conn.close()

    def get_session(self, session_id: str) -> list:
        """返回会话全部消息（含 steps_json 解析）。"""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role, content, steps_json, message_order, created_at "
                    "FROM session_messages WHERE session_id = %s ORDER BY message_order",
                    (session_id,),
                )
                rows = cur.fetchall()
            for r in rows:
                r["steps"] = json.loads(r.pop("steps_json")) if r.get("steps_json") else []
            return rows
        finally:
            conn.close()

    def list_sessions(self) -> list:
        """会话列表（按更新时间倒序，含消息条数）。"""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT s.session_id, s.title, s.updated_at, "
                    "COUNT(m.id) AS message_count "
                    "FROM sessions s LEFT JOIN session_messages m "
                    "ON m.session_id = s.session_id "
                    "GROUP BY s.session_id, s.title, s.updated_at "
                    "ORDER BY s.updated_at DESC"
                )
                rows = cur.fetchall()
            for r in rows:
                r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M:%S") \
                    if r["updated_at"] else None
            return rows
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> None:
        """删除会话及其消息。"""
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM session_messages WHERE session_id = %s", (session_id,)
                )
                cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            conn.commit()
        finally:
            conn.close()


class ContextExtractor:
    """规则型上下文抽取（无状态）：城市 / 日期 / 意图。"""

    @staticmethod
    def _dedup_cap(items: list, cap: int = CTX_CAP) -> list:
        seen, out = set(), []
        for it in items:
            if it and it not in seen:
                seen.add(it)
                out.append(it)
            if len(out) >= cap:
                break
        return out

    @staticmethod
    def extract_cities(text: str) -> list:
        return [c for c in KNOWN_CITIES if c in text]

    @staticmethod
    def extract_dates(text: str) -> list:
        dates = []
        for m in re.finditer(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
            dates.append(f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
        year = datetime.now().year
        for m in re.finditer(r"(\d{1,2})月(\d{1,2})日", text):
            dates.append(f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}")
        return ContextExtractor._dedup_cap(dates)

    @staticmethod
    def detect_intent(text: str) -> str:
        for kw, intent in INTENT_KEYWORDS:
            if kw in text:
                return intent
        return "chat"

    @classmethod
    def extract(cls, text: str) -> dict:
        return {
            "cities": cls._dedup_cap(cls.extract_cities(text)),
            "dates": cls.extract_dates(text),
            "intents": cls._dedup_cap([cls.detect_intent(text)]),
        }

    @classmethod
    def extract_from_history(cls, history: list, current_text: str) -> dict:
        """从历史消息 + 当前消息抽取合并上下文（不落库）。"""
        texts = [h["content"] for h in history if h.get("content")] + [current_text]
        cities = []
        dates = []
        intents = []
        for t in texts:
            cities += cls.extract_cities(t)
            dates += cls.extract_dates(t)
            intents.append(cls.detect_intent(t))
        return {
            "cities": cls._dedup_cap(cities),
            "dates": cls._dedup_cap(dates),
            "intents": cls._dedup_cap(intents),
        }


def format_context(ctx: dict) -> str:
    """把上下文画像格式化为注入用文本。"""
    parts = []
    if ctx.get("cities"):
        parts.append("城市=" + "/".join(ctx["cities"]))
    if ctx.get("dates"):
        parts.append("日期=" + "/".join(ctx["dates"]))
    if ctx.get("intents"):
        parts.append("最近意图=" + "/".join(ctx["intents"]))
    return "；".join(parts)
