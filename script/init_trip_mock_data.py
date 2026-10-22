"""初始化租车模拟数据：为南京、上海 2026 年 8 月写入租车数据。

数据库连接通过 MYSQL_* 环境变量配置。
特点：
- 幂等：INSERT ... ON DUPLICATE KEY UPDATE，可重复执行不产生重复数据
- 追加式：不影响已有数据（成都 2026-08-01 等）
运行：python script/init_trip_mock_data.py
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

# 南京与上海的日期错开，避免与成都 08-01 及互相撞唯一键(company, car_model, pickup_date)
CITY_DATES = {
    "南京": ["2026-08-01", "2026-08-08", "2026-08-15", "2026-08-22", "2026-08-29"],
    "上海": ["2026-08-03", "2026-08-05", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-30"],
}

# (公司, 车型, 具体车型, 日租金, 可租数, 变速箱, 座位数, 押金)
FLEET = [
    ("神州租车", "经济型", "大众宝来", 148, 18, "自动挡", 5, 3000),
    ("神州租车", "经济型", "日产轩逸", 158, 15, "自动挡", 5, 3000),
    ("神州租车", "SUV", "大众途观L", 328, 9, "自动挡", 5, 5500),
    ("神州租车", "豪华型", "奥迪A4L", 538, 4, "自动挡", 5, 10000),
    ("神州租车", "MPV", "本田奥德赛", 468, 6, "自动挡", 7, 8000),
    ("一嗨租车", "经济型", "丰田雷凌", 138, 20, "自动挡", 5, 2500),
    ("一嗨租车", "经济型", "别克英朗", 128, 22, "自动挡", 5, 2500),
    ("一嗨租车", "SUV", "本田CR-V", 308, 11, "自动挡", 5, 5000),
    ("一嗨租车", "豪华型", "凯迪拉克CT5", 498, 3, "自动挡", 5, 9000),
    ("一嗨租车", "MPV", "腾势D9", 448, 7, "自动挡", 7, 7500),
    ("携程租车", "经济型", "现代伊兰特", 118, 25, "手动挡", 5, 2000),
    ("携程租车", "经济型", "雪佛兰科鲁泽", 108, 26, "手动挡", 5, 2000),
    ("携程租车", "SUV", "奇瑞瑞虎8", 288, 12, "自动挡", 5, 5000),
    ("携程租车", "豪华型", "雷克萨斯ES", 588, 2, "自动挡", 5, 12000),
    ("携程租车", "MPV", "上汽大通G10", 428, 8, "自动挡", 7, 7000),
]


def build_rows():
    rows = []
    for city, dates in CITY_DATES.items():
        for date in dates:
            for company, car_type, model, price, available, transmission, seats, deposit in FLEET:
                rows.append({
                    "company": company,
                    "pickup_city": city,
                    "return_city": city,
                    "pickup_date": date,
                    "car_type": car_type,
                    "car_model": model,
                    "price_per_day": price,
                    "total_available": available,
                    "transmission": transmission,
                    "seats": seats,
                    "deposit": deposit,
                })
    return rows


def upsert(conn, table, rows):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"`{c}` = new.`{c}`" for c in cols)
    sql = (
        f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders}) AS new "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    with conn.cursor() as cur:
        for i in range(0, len(rows), 500):
            batch = rows[i:i + 500]
            cur.executemany(sql, [tuple(r[c] for c in cols) for r in batch])
    return len(rows)


def count_rows(conn, table):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        return cur.fetchone()[0]


def main():
    rows = build_rows()
    conn = pymysql.connect(**DB_CONFIG)
    try:
        before = count_rows(conn, "car_rentals")
        n = upsert(conn, "car_rentals", rows)
        conn.commit()
        after = count_rows(conn, "car_rentals")
    finally:
        conn.close()
    print(f"租车：写入 {n} 条，表内总数 {before} -> {after}")
    print("完成：南京/上海 2026-08 租车模拟数据已就绪（幂等，可重复执行）。")


if __name__ == "__main__":
    main()
