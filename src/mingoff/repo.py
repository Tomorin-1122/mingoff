# -*- coding: utf-8 -*-
"""数据存取层：人物 / 官职 / 任职 / 来源 / 异文。

## 三条贯穿全层的规则

1. **NULL ≠ 0**。史料未载就是 `NULL`（生卒年、起止年、月份）。0 是"记载为零"，
   在历史数据里几乎无意义，却是最常见的误录。本层所有查询都把 NULL 当"未知"。
2. **一条任职可挂多个来源**。`tenure.source_ref` 这种单字段设计无法表达
   "《明实录》与 CBDB 都记了这条" —— 用 `tenure_source` 关联表。
3. **不确定性显式**。`confidence` 与 `discrepancy` 是一等公民，不是补丁。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .db import now


# ---------------------------------------------------------------- 数据类


@dataclass
class Person:
    person_id: int | None = None
    name_chn: str = ""
    name_proper: str = ""
    birth_year: int | None = None
    death_year: int | None = None
    native_addr: str = ""
    bio: str = ""
    cbdb_id: int | None = None
    note: str = ""


@dataclass
class Office:
    office_id: int | None = None
    office_chn: str = ""
    pinyin: str = ""
    office_type: str = ""
    parent_office_id: int | None = None
    department: str = ""
    note: str = ""


@dataclass
class Tenure:
    """一条任职。`source_ids` 与 `discrepancies` 是装配出来的，不是表字段。"""

    tenure_id: int | None = None
    person_id: int | None = None
    office_id: int | None = None
    start_year: int | None = None
    end_year: int | None = None
    start_month: int | None = None
    end_month: int | None = None
    tenure_type: str = "实授"
    leave_reason: str = ""
    confidence: float = 0.5
    note: str = ""
    #: 装配字段：关联的史料来源
    source_ids: list[int] = field(default_factory=list)

    @property
    def year_span(self) -> str:
        """给人看的任期串。未载用 `?`，不用 0。"""
        s = str(self.start_year) if self.start_year is not None else "?"
        e = str(self.end_year) if self.end_year is not None else "?"
        return f"{s}–{e}"


@dataclass
class Source:
    source_id: int | None = None
    source_name: str = ""
    citation: str = ""
    url: str = ""
    url_type: str = ""
    note: str = ""


@dataclass
class Discrepancy:
    discrepancy_id: int | None = None
    tenure_id: int | None = None
    source_a: int | None = None
    source_b: int | None = None
    field: str = ""
    value_a: str = ""
    value_b: str = ""
    status: str = "待校"
    note: str = ""


# ---------------------------------------------------------------- 人物


def add_person(conn: sqlite3.Connection, p: Person) -> int:
    """新增人物。返回 person_id。

    去重规则（两条，顺序重要）：
      1. 有 `cbdb_id` 且已存在 → 返回既有 id。反复导入 CBDB 快照是常态。
      2. 没有 cbdb_id 时，**按姓名 + 籍贯**去重。

    第 2 条是必要的：种子数据（张德信年表）里的人物没有 cbdb_id，若不去重，
    重复导入会把 14 人变成 28 人。但**不能只按姓名去重** —— 明代同名者众，
    同名不同人是常态，误合并比留两份更糟。所以加上籍贯作为区分维度：
    两者都相同才视为同一人（籍贯为空时视为同人，这是可接受的宽松）。
    """
    if p.cbdb_id is not None:
        row = conn.execute(
            "SELECT person_id FROM person WHERE cbdb_id=?", (p.cbdb_id,)
        ).fetchone()
        if row:
            return row[0]
    else:
        row = conn.execute(
            "SELECT person_id FROM person WHERE name_chn=?"
            " AND COALESCE(native_addr,'')=COALESCE(?,'')",
            (p.name_chn, p.native_addr or ""),
        ).fetchone()
        if row:
            return row[0]

    ts = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO person(name_chn, name_proper, birth_year, death_year,"
            " native_addr, bio, cbdb_id, note, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                p.name_chn, p.name_proper, p.birth_year, p.death_year,
                p.native_addr, p.bio, p.cbdb_id, p.note, ts, ts,
            ),
        )
    return int(cur.lastrowid)


def get_person(conn: sqlite3.Connection, person_id: int) -> Person | None:
    row = conn.execute("SELECT * FROM person WHERE person_id=?", (person_id,)).fetchone()
    if row is None:
        return None
    return Person(
        person_id=row["person_id"], name_chn=row["name_chn"] or "",
        name_proper=row["name_proper"] or "", birth_year=row["birth_year"],
        death_year=row["death_year"], native_addr=row["native_addr"] or "",
        bio=row["bio"] or "", cbdb_id=row["cbdb_id"], note=row["note"] or "",
    )


def find_person_by_name(conn: sqlite3.Connection, name: str) -> list[Person]:
    rows = conn.execute(
        "SELECT person_id FROM person WHERE name_chn=? ORDER BY person_id", (name,)
    ).fetchall()
    out = []
    for r in rows:
        p = get_person(conn, r[0])
        if p:
            out.append(p)
    return out


# ---------------------------------------------------------------- 官职


def add_office(conn: sqlite3.Connection, o: Office) -> int:
    """新增官职。同衙门+同官职名视为同一个（避免重复建树）。"""
    row = conn.execute(
        "SELECT office_id FROM office WHERE office_chn=? AND"
        " COALESCE(department,'')=COALESCE(?,'')",
        (o.office_chn, o.department or ""),
    ).fetchone()
    if row:
        return row[0]

    ts = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO office(office_chn, pinyin, office_type, parent_office_id,"
            " department, note, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                o.office_chn, o.pinyin, o.office_type, o.parent_office_id,
                o.department, o.note, ts, ts,
            ),
        )
    return int(cur.lastrowid)


def get_office(conn: sqlite3.Connection, office_id: int) -> Office | None:
    row = conn.execute("SELECT * FROM office WHERE office_id=?", (office_id,)).fetchone()
    if row is None:
        return None
    return Office(
        office_id=row["office_id"], office_chn=row["office_chn"] or "",
        pinyin=row["pinyin"] or "", office_type=row["office_type"] or "",
        parent_office_id=row["parent_office_id"], department=row["department"] or "",
        note=row["note"] or "",
    )


def office_tree(conn: sqlite3.Connection, root_id: int | None = None) -> list[tuple[Office, int]]:
    """官职树，返回 (office, depth)。root_id 为 None 时列出全部（按父子关系排）。

    用递归 CTE 而不是在 Python 里拼 —— 树是数据问题，交给数据库。
    """
    if root_id is None:
        sql = (
            "WITH RECURSIVE tree(office_id, depth) AS ("
            "  SELECT office_id, 0 FROM office WHERE parent_office_id IS NULL"
            "  UNION ALL"
            "  SELECT o.office_id, t.depth+1 FROM office o"
            "    JOIN tree t ON o.parent_office_id = t.office_id"
            ") SELECT office_id, depth FROM tree ORDER BY depth, office_id"
        )
        rows = conn.execute(sql).fetchall()
    else:
        sql = (
            "WITH RECURSIVE tree(office_id, depth) AS ("
            "  SELECT office_id, 0 FROM office WHERE office_id = ?"
            "  UNION ALL"
            "  SELECT o.office_id, t.depth+1 FROM office o"
            "    JOIN tree t ON o.parent_office_id = t.office_id"
            ") SELECT office_id, depth FROM tree ORDER BY depth, office_id"
        )
        rows = conn.execute(sql, (root_id,)).fetchall()

    out: list[tuple[Office, int]] = []
    for office_id, depth in rows:
        o = get_office(conn, office_id)
        if o:
            out.append((o, depth))
    return out


# ---------------------------------------------------------------- 来源


def add_source(conn: sqlite3.Connection, s: Source) -> int:
    """新增史料来源。同 source_name + citation + url 视为同一条。"""
    row = conn.execute(
        "SELECT source_id FROM source WHERE source_name=?"
        " AND COALESCE(citation,'')=COALESCE(?,'')"
        " AND COALESCE(url,'')=COALESCE(?,'')",
        (s.source_name, s.citation or "", s.url or ""),
    ).fetchone()
    if row:
        return row[0]

    with conn:
        cur = conn.execute(
            "INSERT INTO source(source_name, citation, url, url_type, note)"
            " VALUES(?,?,?,?,?)",
            (s.source_name, s.citation, s.url, s.url_type, s.note),
        )
    return int(cur.lastrowid)


def get_source(conn: sqlite3.Connection, source_id: int) -> Source | None:
    row = conn.execute("SELECT * FROM source WHERE source_id=?", (source_id,)).fetchone()
    if row is None:
        return None
    return Source(
        source_id=row["source_id"], source_name=row["source_name"] or "",
        citation=row["citation"] or "", url=row["url"] or "",
        url_type=row["url_type"] or "", note=row["note"] or "",
    )


# ---------------------------------------------------------------- 任职


def add_tenure(
    conn: sqlite3.Connection, t: Tenure, *, source_ids: list[int] | None = None
) -> int:
    """新增任职，并关联史料来源。返回 tenure_id。

    这是本项目最重要的写入口 —— 每条任职都应当带来源，否则"可溯源"无从谈起。
    但**不强制**有来源：人工录入时可能先记下来再补，硬性拒绝会挡住真实工作流。
    用 `mandatory_source=False` 的调用方（如 CLI 的 `--strict`）自行校验。

    ## 去重

    (person, office, start_year, end_year, tenure_type) 完全相同则视为同一条，
    返回既有 id。理由：重复导入同一年表快照是常态操作，不该让历任表翻倍；
    而"同一人同一职同一时期同类型"在史料里本就是同一条任命。
    注意 `end_year` 参与比较 —— 期限不同的两任**不是**重复。
    """
    row = conn.execute(
        "SELECT tenure_id FROM tenure WHERE person_id=? AND office_id=?"
        " AND COALESCE(start_year,-1)=COALESCE(?,-1)"
        " AND COALESCE(end_year,-1)=COALESCE(?,-1)"
        " AND tenure_type=?",
        (
            t.person_id, t.office_id, t.start_year, t.end_year, t.tenure_type,
        ),
    ).fetchone()
    if row:
        existing = int(row[0])
        for sid in source_ids or t.source_ids:
            link_source(conn, existing, sid)
        return existing

    ts = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO tenure(person_id, office_id, start_year, end_year,"
            " start_month, end_month, tenure_type, leave_reason, confidence, note,"
            " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                t.person_id, t.office_id, t.start_year, t.end_year,
                t.start_month, t.end_month, t.tenure_type,
                t.leave_reason or None, t.confidence, t.note, ts, ts,
            ),
        )
        tenure_id = int(cur.lastrowid)
        for sid in source_ids or t.source_ids:
            conn.execute(
                "INSERT OR IGNORE INTO tenure_source(tenure_id, source_id)"
                " VALUES(?,?)",
                (tenure_id, sid),
            )
    return tenure_id


def get_tenure(conn: sqlite3.Connection, tenure_id: int) -> Tenure | None:
    row = conn.execute("SELECT * FROM tenure WHERE tenure_id=?", (tenure_id,)).fetchone()
    if row is None:
        return None
    srcs = [
        r[0]
        for r in conn.execute(
            "SELECT source_id FROM tenure_source WHERE tenure_id=?", (tenure_id,)
        ).fetchall()
    ]
    return Tenure(
        tenure_id=row["tenure_id"], person_id=row["person_id"],
        office_id=row["office_id"], start_year=row["start_year"],
        end_year=row["end_year"], start_month=row["start_month"],
        end_month=row["end_month"], tenure_type=row["tenure_type"] or "实授",
        leave_reason=row["leave_reason"] or "", confidence=row["confidence"],
        note=row["note"] or "", source_ids=srcs,
    )


def link_source(conn: sqlite3.Connection, tenure_id: int, source_id: int) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO tenure_source(tenure_id, source_id) VALUES(?,?)",
            (tenure_id, source_id),
        )


# ---------------------------------------------------------------- 异文


def add_discrepancy(conn: sqlite3.Connection, d: Discrepancy) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO discrepancy(tenure_id, source_a, source_b, field,"
            " value_a, value_b, status, note) VALUES(?,?,?,?,?,?,?,?)",
            (
                d.tenure_id, d.source_a, d.source_b, d.field,
                d.value_a, d.value_b, d.status, d.note,
            ),
        )
    return int(cur.lastrowid)


def list_discrepancies(
    conn: sqlite3.Connection, *, status: str | None = None
) -> list[Discrepancy]:
    sql = "SELECT * FROM discrepancy"
    params: list[Any] = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY discrepancy_id"
    rows = conn.execute(sql, params).fetchall()
    return [
        Discrepancy(
            discrepancy_id=r["discrepancy_id"], tenure_id=r["tenure_id"],
            source_a=r["source_a"], source_b=r["source_b"], field=r["field"] or "",
            value_a=r["value_a"] or "", value_b=r["value_b"] or "",
            status=r["status"] or "待校", note=r["note"] or "",
        )
        for r in rows
    ]


def resolve_discrepancy(
    conn: sqlite3.Connection, discrepancy_id: int, *, status: str, note: str = ""
) -> None:
    """标记异文已处理。status ∈ {待校, 已校, 存疑} —— 由 schema 的 CHECK 兜底。"""
    with conn:
        conn.execute(
            "UPDATE discrepancy SET status=?, note=? WHERE discrepancy_id=?",
            (status, note, discrepancy_id),
        )


# ---------------------------------------------------------------- 查询


def tenures_of_office(
    conn: sqlite3.Connection, office_id: int, *, order: str = "start_year"
) -> list[Tenure]:
    """某官职的历任记录 —— 即"查历任兵部尚书"这一核心场景。

    排序默认按 start_year，**NULL（史料未载起始年）排最后**，避免未知年份
    冒到最前面把历任顺序打乱。
    """
    if order not in {"start_year", "end_year", "tenure_id"}:
        raise ValueError(f"不支持的排序: {order}")
    sql = (
        f"SELECT tenure_id FROM tenure WHERE office_id=?"
        f" ORDER BY ({order} IS NULL), {order}, tenure_id"
    )
    rows = conn.execute(sql, (office_id,)).fetchall()
    out = []
    for r in rows:
        t = get_tenure(conn, r[0])
        if t:
            out.append(t)
    return out


def tenures_of_person(conn: sqlite3.Connection, person_id: int) -> list[Tenure]:
    """某人的全部任职 —— "追踪人物仕途流转"场景。"""
    rows = conn.execute(
        "SELECT tenure_id FROM tenure WHERE person_id=?"
        " ORDER BY (start_year IS NULL), start_year, tenure_id",
        (person_id,),
    ).fetchall()
    out = []
    for r in rows:
        t = get_tenure(conn, r[0])
        if t:
            out.append(t)
    return out


def snapshot_at_year(conn: sqlite3.Connection, year: int) -> list[Tenure]:
    """某一年的在任记录 —— "朝堂快照"场景。

    某条任职在 `year` 年在任的判定（对 NULL 的处理是关键）：
      * start_year 为 NULL 或 <= year
      * end_year   为 NULL 或 >= year
    即"未载起始年"视为可能已在任、"未载离任年"视为可能仍在任 —— 这样快照
    **宁可多列也不漏**。历史数据缺载是常态，漏掉记录比多列一条更难发现。
    """
    rows = conn.execute(
        "SELECT tenure_id FROM tenure"
        " WHERE (start_year IS NULL OR start_year <= ?)"
        "   AND (end_year IS NULL OR end_year >= ?)"
        " ORDER BY (start_year IS NULL), start_year, tenure_id",
        (year, year),
    ).fetchall()
    out = []
    for r in rows:
        t = get_tenure(conn, r[0])
        if t:
            out.append(t)
    return out
