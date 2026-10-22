"""初始化票务模拟数据：为上海、南京 2026 年 8 月写入机票、火车票、演唱会票数据。

数据库连接通过 MYSQL_* 环境变量配置。
特点：
- 幂等：INSERT ... ON DUPLICATE KEY UPDATE，可重复执行不产生重复数据
- 追加式：不影响已有数据（如 2026-08-01 上海→南京、成都演唱会等）
运行：python script/init_ticket_mock_data.py
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

# ==================== 机票：上海 ↔ 南京，2026-08 多日期 ====================
FLIGHT_DATES = [
    "2026-08-03",
    "2026-08-05",
    "2026-08-08",
    "2026-08-15",
    "2026-08-22",
    "2026-08-29",
]

# (方向) -> [(航班号, 出发时刻, 到达时刻, [(舱位, 票价, 总座, 余票), ...]), ...]
FLIGHT_SCHEDULE = {
    ("上海", "南京"): [
        ("MU5101", "07:30", "08:55", [
            ("经济舱", 720, 200, 52),
            ("商务舱", 1680, 40, 11),
        ]),
        ("CA1857", "10:20", "11:45", [
            ("经济舱", 690, 220, 63),
            ("商务舱", 1620, 40, 14),
            ("头等舱", 2680, 16, 4),
        ]),
        ("3U8881", "18:40", "20:05", [
            ("经济舱", 640, 180, 77),
            ("商务舱", 1550, 32, 18),
        ]),
    ],
    ("南京", "上海"): [
        ("MU5102", "08:10", "09:35", [
            ("经济舱", 710, 200, 48),
            ("商务舱", 1660, 40, 9),
        ]),
        ("CZ3556", "11:40", "13:05", [
            ("经济舱", 680, 210, 71),
            ("商务舱", 1600, 42, 16),
            ("头等舱", 2650, 16, 5),
        ]),
        ("3U8897", "16:30", "17:55", [
            ("经济舱", 660, 180, 59),
            ("商务舱", 1580, 32, 12),
        ]),
    ],
}

# ==================== 火车票：上海 ↔ 南京，2026-08 多日期 ====================
TRAIN_DATES = FLIGHT_DATES

# (方向) -> [(车次, 出发时刻, 到达时刻, [(席别, 票价, 总座, 余票), ...]), ...]
TRAIN_SCHEDULE = {
    ("上海", "南京"): [
        ("G7011", "07:00", "08:42", [
            ("二等座", 155.5, 1000, 320),
            ("一等座", 258.5, 400, 76),
            ("商务座", 486.5, 50, 14),
        ]),
        ("D2281", "13:35", "15:58", [
            ("二等座", 128.0, 800, 210),
            ("一等卧", 328.0, 400, 58),
        ]),
        ("G7097", "17:20", "19:02", [
            ("二等座", 155.5, 1000, 265),
            ("一等座", 258.5, 400, 63),
            ("商务座", 486.5, 50, 9),
        ]),
    ],
    ("南京", "上海"): [
        ("G7002", "06:45", "08:27", [
            ("二等座", 155.5, 1000, 298),
            ("一等座", 258.5, 400, 82),
            ("商务座", 486.5, 50, 16),
        ]),
        ("D2285", "12:40", "15:03", [
            ("二等座", 128.0, 800, 186),
            ("一等卧", 328.0, 400, 47),
        ]),
        ("G7102", "16:10", "17:52", [
            ("二等座", 155.5, 1000, 233),
            ("一等座", 258.5, 400, 70),
            ("商务座", 486.5, 50, 12),
        ]),
    ],
}

# ==================== 演唱会：上海、南京 2026-08 ====================
# (艺人, 城市, 场馆, 开始时间, 结束时间, [(票型, 票价, 总座, 余票), ...])
CONCERTS = [
    ("周杰伦", "上海", "上海体育场", "2026-08-08 19:00:00", "2026-08-08 22:00:00", [
        ("看台C区", 380, 12000, 3456),
        ("看台B区", 580, 15000, 2345),
        ("看台A区", 780, 15000, 1234),
        ("内场B区", 1280, 8000, 456),
        ("内场A区", 1680, 8000, 234),
        ("VIP内场", 2180, 6000, 89),
    ]),
    ("林俊杰", "上海", "梅赛德斯-奔驰文化中心", "2026-08-08 19:30:00", "2026-08-08 22:30:00", [
        ("看台", 480, 8000, 2100),
        ("内场", 1280, 5000, 380),
        ("VIP", 1980, 3000, 55),
    ]),
    ("薛之谦", "上海", "上海体育场", "2026-08-15 19:00:00", "2026-08-15 22:00:00", [
        ("看台C区", 380, 12000, 4321),
        ("看台B区", 580, 15000, 2890),
        ("看台A区", 780, 15000, 1500),
        ("内场B区", 1280, 8000, 520),
        ("内场A区", 1680, 8000, 260),
        ("VIP内场", 2180, 6000, 95),
    ]),
    ("五月天", "上海", "虹口足球场", "2026-08-22 18:30:00", "2026-08-22 22:00:00", [
        ("看台", 480, 9000, 2600),
        ("看台前排", 880, 3000, 420),
        ("内场", 1380, 6000, 310),
        ("VIP", 2080, 4000, 66),
    ]),
    ("张杰", "上海", "上海体育场", "2026-08-29 19:30:00", "2026-08-29 22:30:00", [
        ("看台C区", 380, 12000, 3800),
        ("看台B区", 580, 15000, 2200),
        ("看台A区", 780, 15000, 1100),
        ("内场B区", 1280, 8000, 430),
        ("内场A区", 1680, 8000, 180),
    ]),
    ("陈奕迅", "南京", "南京青奥体育公园体育馆", "2026-08-03 19:30:00", "2026-08-03 22:30:00", [
        ("看台", 480, 8000, 1900),
        ("看台前排", 880, 3000, 350),
        ("内场", 1380, 5000, 280),
        ("VIP", 2080, 3000, 48),
    ]),
    ("薛之谦", "南京", "南京奥体中心体育场", "2026-08-10 19:00:00", "2026-08-10 22:00:00", [
        ("看台C区", 380, 12000, 4100),
        ("看台B区", 580, 15000, 2600),
        ("看台A区", 780, 15000, 1300),
        ("内场B区", 1280, 8000, 470),
        ("内场A区", 1680, 8000, 220),
        ("VIP内场", 2180, 6000, 78),
    ]),
    ("张杰", "南京", "南京奥体中心体育场", "2026-08-17 19:30:00", "2026-08-17 22:30:00", [
        ("看台C区", 380, 12000, 3500),
        ("看台B区", 580, 15000, 2100),
        ("看台A区", 780, 15000, 980),
        ("内场B区", 1280, 8000, 390),
        ("内场A区", 1680, 8000, 160),
    ]),
    ("毛不易", "南京", "南京青奥体育公园体育馆", "2026-08-24 19:30:00", "2026-08-24 22:00:00", [
        ("看台", 380, 8000, 2300),
        ("看台前排", 680, 3000, 480),
        ("内场", 1180, 5000, 320),
        ("VIP", 1780, 3000, 72),
    ]),
    ("周深", "南京", "南京奥体中心体育场", "2026-08-30 19:30:00", "2026-08-30 22:30:00", [
        ("看台C区", 380, 12000, 4200),
        ("看台B区", 580, 15000, 2700),
        ("看台A区", 780, 15000, 1400),
        ("内场B区", 1280, 8000, 510),
        ("内场A区", 1680, 8000, 240),
    ]),
]


def build_flight_rows():
    rows = []
    for (dep, arr), schedule in FLIGHT_SCHEDULE.items():
        for date in FLIGHT_DATES:
            for flight_no, dep_time, arr_time, cabins in schedule:
                for cabin, price, total, remaining in cabins:
                    rows.append({
                        "departure_city": dep,
                        "arrival_city": arr,
                        "departure_time": f"{date} {dep_time}:00",
                        "arrival_time": f"{date} {arr_time}:00",
                        "flight_number": flight_no,
                        "cabin_type": cabin,
                        "total_seats": total,
                        "remaining_seats": remaining,
                        "price": price,
                    })
    return rows


def build_train_rows():
    rows = []
    for (dep, arr), schedule in TRAIN_SCHEDULE.items():
        for date in TRAIN_DATES:
            for train_no, dep_time, arr_time, seats in schedule:
                for seat, price, total, remaining in seats:
                    rows.append({
                        "departure_city": dep,
                        "arrival_city": arr,
                        "departure_time": f"{date} {dep_time}:00",
                        "arrival_time": f"{date} {arr_time}:00",
                        "train_number": train_no,
                        "seat_type": seat,
                        "total_seats": total,
                        "remaining_seats": remaining,
                        "price": price,
                    })
    return rows


def build_concert_rows():
    rows = []
    for artist, city, venue, start, end, tickets in CONCERTS:
        for ticket_type, price, total, remaining in tickets:
            rows.append({
                "artist": artist,
                "city": city,
                "venue": venue,
                "start_time": start,
                "end_time": end,
                "ticket_type": ticket_type,
                "total_seats": total,
                "remaining_seats": remaining,
                "price": price,
            })
    return rows


def upsert(conn, table, rows):
    """幂等写入：存在唯一键冲突时更新，否则插入。"""
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
    flight_rows = build_flight_rows()
    train_rows = build_train_rows()
    concert_rows = build_concert_rows()

    conn = pymysql.connect(**DB_CONFIG)
    try:
        before = {
            "flight_tickets": count_rows(conn, "flight_tickets"),
            "train_tickets": count_rows(conn, "train_tickets"),
            "concert_tickets": count_rows(conn, "concert_tickets"),
        }
        n_flight = upsert(conn, "flight_tickets", flight_rows)
        n_train = upsert(conn, "train_tickets", train_rows)
        n_concert = upsert(conn, "concert_tickets", concert_rows)
        conn.commit()

        after = {
            "flight_tickets": count_rows(conn, "flight_tickets"),
            "train_tickets": count_rows(conn, "train_tickets"),
            "concert_tickets": count_rows(conn, "concert_tickets"),
        }
    finally:
        conn.close()

    print(
        f"机票：写入 {n_flight} 条，表内总数 "
        f"{before['flight_tickets']} -> {after['flight_tickets']}"
    )
    print(
        f"火车票：写入 {n_train} 条，表内总数 "
        f"{before['train_tickets']} -> {after['train_tickets']}"
    )
    print(
        f"演唱会票：写入 {n_concert} 条，表内总数 "
        f"{before['concert_tickets']} -> {after['concert_tickets']}"
    )
    print("完成：上海/南京 2026-08 模拟数据已就绪（幂等，可重复执行）。")


if __name__ == "__main__":
    main()
