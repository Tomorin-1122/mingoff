# -*- coding: utf-8 -*-
"""命令行入口：`mingoff <command>`。

一期只做数据层能证明的东西 —— 导入、查询、校勘队列。可视化留到后面
（PRD 阶段① 的验收标准里，时间轴是最后一项）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import db as D
from . import repo as R
from . import seed as S


def _out(msg: str = "") -> None:
    print(msg)


# ---------------------------------------------------------------- 建库


def cmd_init(args: argparse.Namespace) -> int:
    path = D.init_db(args.db)
    _out(f"[完成] 已建库: {path}")
    conn = D.connect(path)
    try:
        tables = D.table_names(conn)
    finally:
        conn.close()
    _out(f"       表: {', '.join(tables)}")
    _out("       下一步: mingoff seed    # 导入 MVP 种子数据")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """导入崇祯朝兵部尚书种子数据（幂等）。"""
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init")
        return 2

    conn = D.connect(args.db)
    try:
        # 官职：先建兵部衙门，再建兵部尚書（挂在它下面，形成官职树）
        bingbu_id = R.add_office(conn, S.office_bingbu())
        shangshu = S.office_bingbu_shangshu()
        shangshu.parent_office_id = bingbu_id
        shangshu_id = R.add_office(conn, shangshu)

        # 史料来源
        src_zd = R.add_source(conn, S.SOURCE_ZHANGDEXIN)
        src_ms = R.add_source(conn, S.SOURCE_MINGSHI)

        # 人物 + 任职
        person_ids = [R.add_person(conn, p) for p in S.persons()]
        tenures = S.tenures(person_ids, shangshu_id)
        for t in tenures:
            R.add_tenure(conn, t, source_ids=[src_zd])

        counts = D.count_rows(conn)
    finally:
        conn.close()

    _out(f"[完成] 已导入崇祯朝兵部尚书 {len(tenures)} 任")
    _out(f"       人物={counts['person']} 官职={counts['office']}"
         f" 任职={counts['tenure']} 来源={counts['source']}")
    _out("       查询: mingoff list-bingbu")
    return 0


# ---------------------------------------------------------------- 查询


def cmd_list_bingbu(args: argparse.Namespace) -> int:
    """列出兵部尚书历任 —— MVP 的核心验收场景。"""
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init && mingoff seed")
        return 2

    conn = D.connect(args.db, readonly=True)
    try:
        office = conn.execute(
            "SELECT office_id FROM office WHERE office_chn='兵部尚書' LIMIT 1"
        ).fetchone()
        if office is None:
            _out("[错误] 库里没有「兵部尚書」，先跑: mingoff seed")
            return 2
        office_id = office[0]
        tenures = R.tenures_of_office(conn, office_id)

        if not tenures:
            _out("(无记录)")
            return 0

        _out(f"兵部尚书历任（共 {len(tenures)} 任）")
        _out("")
        _out(f"{'#':<3} {'姓名':<8} {'任期':<12} {'类型':<5} {'离任':<6} 置信度")
        _out("-" * 56)
        for i, t in enumerate(tenures, 1):
            person = R.get_person(conn, t.person_id)
            name = person.name_chn if person else f"(id={t.person_id})"
            conf = f"{t.confidence:.1f}" if t.confidence is not None else "?"
            _out(
                f"{i:<3} {name:<8} {t.year_span:<12} {t.tenure_type:<5}"
                f" {t.leave_reason or '-':<6} {conf}"
            )
        _out("")
        _out("注: 任期用 ? 表示史料未载（不是 0）。")
        _out("    袁崇焕/孙传庭/卢象升为「兵部尚书衔」，不属京中兵部尚书，未计入。")
    finally:
        conn.close()
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """某年在任快照。"""
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init && mingoff seed")
        return 2

    conn = D.connect(args.db, readonly=True)
    try:
        tenures = R.snapshot_at_year(conn, args.year)
        if not tenures:
            _out(f"({args.year} 年无在任记录)")
            return 0
        _out(f"{args.year} 年在任（{len(tenures)} 条）")
        for t in tenures:
            person = R.get_person(conn, t.person_id)
            office = R.get_office(conn, t.office_id)
            _out(
                f"  {person.name_chn if person else '?'}"
                f"  {office.office_chn if office else '?'}"
                f"  [{t.tenure_type}]  {t.year_span}"
            )
    finally:
        conn.close()
    return 0


def cmd_person(args: argparse.Namespace) -> int:
    """某人的仕途流转。"""
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init && mingoff seed")
        return 2

    conn = D.connect(args.db, readonly=True)
    try:
        people = R.find_person_by_name(conn, args.name)
        if not people:
            _out(f"(库中没有「{args.name}」)")
            return 0
        for p in people:
            _out(f"{p.name_chn}  (person_id={p.person_id})")
            if p.bio:
                _out(f"  著作/说明: {p.bio}")
            tenures = R.tenures_of_person(conn, p.person_id)
            if not tenures:
                _out("  (无任职记录)")
                continue
            for t in tenures:
                office = R.get_office(conn, t.office_id)
                srcs = [
                    R.get_source(conn, sid) for sid in t.source_ids
                ]
                src_names = "、".join(
                    s.source_name for s in srcs if s
                ) or "（无来源）"
                _out(
                    f"  {t.year_span:<12} {office.office_chn if office else '?':<10}"
                    f" [{t.tenure_type}]  来源: {src_names}"
                )
    finally:
        conn.close()
    return 0


def cmd_todo(args: argparse.Namespace) -> int:
    """待校勘队列。"""
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init && mingoff seed")
        return 2

    conn = D.connect(args.db, readonly=True)
    try:
        items = R.list_discrepancies(conn, status=args.status)
        if not items:
            _out(f"(无「{args.status}」的异文记录)")
            return 0
        _out(f"异文记录（status={args.status}，共 {len(items)} 条）")
        for d in items:
            _out(
                f"  #{d.discrepancy_id} tenure={d.tenure_id} field={d.field}"
                f"  [{d.status}]"
            )
            _out(f"     A: {d.value_a}")
            _out(f"     B: {d.value_b}")
    finally:
        conn.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    if not D.is_initialized(args.db):
        _out("[错误] 数据库未初始化，先跑: mingoff init && mingoff seed")
        return 2
    conn = D.connect(args.db, readonly=True)
    try:
        counts = D.count_rows(conn)
        version = D.get_meta(conn, "schema_version")
    finally:
        conn.close()

    _out(f"数据库: {Path(args.db) if args.db else D.DEFAULT_DB}")
    _out(f"schema_version: {version}")
    for name, n in counts.items():
        _out(f"  {name:<16} {n:>8,}")
    return 0


# ---------------------------------------------------------------- 装配


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mingoff",
        description="MingOff —— 明代职官数据库：结构化任职 + 史料溯源 + 校勘",
    )
    ap.add_argument("--version", action="version", version=f"mingoff {__version__}")
    ap.add_argument("--db", help="数据库路径（默认 data/mingoff.sqlite）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="建库")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("seed", help="导入崇祯朝兵部尚书种子数据")
    p.set_defaults(fn=cmd_seed)

    p = sub.add_parser("list-bingbu", help="列出兵部尚书历任")
    p.set_defaults(fn=cmd_list_bingbu)

    p = sub.add_parser("snapshot", help="某年在任快照")
    p.add_argument("year", type=int)
    p.set_defaults(fn=cmd_snapshot)

    p = sub.add_parser("person", help="某人的仕途流转")
    p.add_argument("name")
    p.set_defaults(fn=cmd_person)

    p = sub.add_parser("todo", help="待校勘队列")
    p.add_argument("--status", default="待校", choices=["待校", "已校", "存疑"])
    p.set_defaults(fn=cmd_todo)

    p = sub.add_parser("stats", help="库内计数")
    p.set_defaults(fn=cmd_stats)

    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = build_parser()
    args = ap.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
