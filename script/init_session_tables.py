"""初始化会话记忆表：sessions + session_messages（幂等，可重复执行）。

数据库连接通过 MYSQL_* 环境变量配置。
运行：python script/init_session_tables.py
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "travel_rag"),
    "charset": "utf8mb4",
    "connect_timeout": 5,
}

DDL = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        `session_id` varchar(64) NOT NULL COMMENT '会话ID',
        `title` varchar(200) NOT NULL COMMENT '会话标题（首条用户消息截断）',
        `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (`session_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话列表'
    """,
    """
    CREATE TABLE IF NOT EXISTS session_messages (
        `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
        `session_id` varchar(64) NOT NULL COMMENT '会话ID',
        `role` varchar(10) NOT NULL COMMENT '消息角色：user/assistant/system',
        `content` text NOT NULL COMMENT '消息内容',
        `steps_json` text NULL COMMENT '工具调用步骤JSON（assistant消息）',
        `message_order` int NOT NULL COMMENT '会话内消息顺序号',
        `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        PRIMARY KEY (`id`),
        KEY `idx_session_order` (`session_id`, `message_order`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话消息历史'
    """,
]


def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            for ddl in DDL:
                cur.execute(ddl)
            cur.execute("SHOW TABLES LIKE 'sessions'")
            has_sessions = cur.fetchone() is not None
            cur.execute("SHOW TABLES LIKE 'session_messages'")
            has_messages = cur.fetchone() is not None
        conn.commit()
    finally:
        conn.close()
    print(f"sessions={has_sessions}, session_messages={has_messages}")
    print("完成：会话记忆表已就绪（幂等，可重复执行）。")


if __name__ == "__main__":
    main()
