# -*- coding: utf-8 -*-
"""数据库连接与建库。

用 SQLite：PRD 建议 PostgreSQL，但 MVP 阶段单人开发用 SQLite 省掉部署成本，
且本模块的 SQL 都是标准的（除了 `CREATE INDEX ... WHERE` 部分索引，SQLite 与
PG 都支持），迁移时换连接层即可。

**为什么不用 ORM**：本项目的表少（6 张）、查询以只读统计为主，schema 用原生
SQL 写反而更容易看出"哪些字段是史料未载（NULL）"这件事 —— 而 NULL 语义正是
本项目最需要小心的地方（见 schema.py 注释）。
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .schema import SCHEMA, SCHEMA_VERSION

#: 仓库根：src/mingoff/db.py → 上溯三层
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "mingoff.sqlite"


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path: Path | str | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    """打开数据库。

    Args:
        readonly: 以只读方式打开（查询/报表用）。防手滑写坏数据。
    """
    path = Path(db_path) if db_path else DEFAULT_DB
    if readonly:
        if not path.is_file():
            raise FileNotFoundError(f"数据库不存在: {path}（先跑 `mingoff init`）")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=1")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str | None = None) -> Path:
    """建库（幂等）。返回数据库路径。"""
    path = Path(db_path) if db_path else DEFAULT_DB
    conn = connect(path)
    try:
        with conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES(?, ?)",
                ("created_at", now()),
            )
    finally:
        conn.close()
    return path


def table_names(conn: sqlite3.Connection) -> list[str]:
    """列出业务表（排除 SQLite 内部表）。"""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]


def count_rows(conn: sqlite3.Connection) -> dict[str, int]:
    """各表行数 —— 体检用。"""
    out: dict[str, int] = {}
    for name in table_names(conn):
        out[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return out


def is_initialized(db_path: Path | str | None = None) -> bool:
    path = Path(db_path) if db_path else DEFAULT_DB
    if not path.is_file():
        return False
    try:
        conn = connect(path, readonly=True)
    except (FileNotFoundError, sqlite3.Error):
        return False
    try:
        return "tenure" in table_names(conn)
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value)
        )
