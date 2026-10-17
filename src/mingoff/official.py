# -*- coding: utf-8 -*-
"""正式版数据管线（D21）：从年表源提取物重建任职段，不复用 demo 数据。

输入（源提取物，位于 src/mingoff/data/）：
  * neige_entries_aligned.json —— 年表条目 + CBDB 对齐（parse_neige + align 产出）
  * neige_events.json          —— 条目注文的月日事件（parse_events 产出）

输出（正式数据资产）：
  * src/mingoff/data/official_cabinet.json —— 内阁任职段（版本化导出，含 meta）

与 demo 的关系（D21）：demo 的 merge 产物一律不进入本管线。本模块与
build_tenures.py 共享装配**思路**（年在位体 → 连续年合并段 → 边界事件定月），
但独立实现并附完整溯源，保证正式数据可独立审计。

三条纪律在此管线的落实：
  * NULL ≠ 0（D4）：年表未载月 → month = None
  * 不臆造（D20 精神）：同一年份边界有多个互斥月份 → 不取，交由人工校勘
  * 溯源（D21）：每段记录 enter/leave_verbs 与年表原文 note
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA = Path(__file__).resolve().parent / "data"

# ── 事件动词分类（与 build_tenures.py 同一实测结论，独立维护） ──────────
ENTER = {"入", "入朝", "入直", "任", "起", "起復", "召", "復官", "還朝", "視事", "至京"}
LEAVE = {"罷", "卒", "致仕", "削籍", "革職", "下獄", "論死", "正法", "自盡",
         "被執", "戍", "謫", "丁憂", "丁父憂", "丁母憂", "憂去", "乞歸", "乞休",
         "養病", "杜門", "卒于", "調別任", "免", "回籍", "致仕歸"}
# 入职定式：年表注文的授官多不带动词（'禮尚兼東閣大學士入'），须联合判定
import re

ENTER_PAT = re.compile(
    r"(大學士入|入閣|入直|入朝|兼東閣大學士|兼文淵閣大學士|兼武英殿大學士|"
    r"兼文華殿大學士|兼建極殿大學士|兼中極殿大學士|兼謹身殿大學士|兼華蓋殿大學士|"
    r"遷禮尚兼|遷禮尚|任[;；。]?$|起用|召|至京|視事|掌翰林院事)")


def norm_verb(verb: str, chunk: str = "") -> str:
    """动词 + chunk 定式联合判定：enter / leave / other。"""
    if chunk and ENTER_PAT.search(chunk):
        return "enter"
    for s in ENTER:
        if verb.startswith(s):
            return "enter"
    for s in LEAVE:
        if verb.startswith(s):
            return "leave"
    return "other"


def canon_section(sec: str) -> str | None:
    """正式版只取『內閣』；殿閣/翰林院是台阶官，阶段②另做（D21 范围纪律）。"""
    return "內閣" if sec == "內閣" else None


def load_sources() -> tuple[list[dict], dict[tuple[str, int], list[dict]]]:
    """读两份源提取物；返回（内阁条目列表, (person, year)->events 索引）。"""
    entries = json.loads((DATA / "neige_entries_aligned.json").read_text(encoding="utf-8"))
    events_doc = json.loads((DATA / "neige_events.json").read_text(encoding="utf-8"))

    by_py: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for e in events_doc:
        if e.get("section") != "內閣":
            continue
        for v in e.get("events", []):
            by_py[(e["person"], e["year"])].append(v)
    return [e for e in entries if e.get("section") == "內閣"], by_py


def _pick_month(cands: list[dict]) -> int | None:
    """同一边界年有多个带月事件：月份唯一才取（D20 不臆造），否则 None。"""
    months = {v["month"] for v in cands if v.get("month")}
    return months.pop() if len(months) == 1 else None


def build_cabinet_tenures() -> list[dict]:
    """年表内阁条目 → 任职段。装配逻辑与 build_tenures.py 同源（年在位体）。"""
    entries, by_py = load_sources()

    # (person) -> 在任年集合（正式版 section 已固定为 內閣）
    presence: dict[str, set[int]] = defaultdict(set)
    cbdb_of: dict[str, int | None] = {}
    note_of: dict[tuple[str, int], str] = {}
    for e in entries:
        presence[e["person"]].add(e["year"])
        # CBDB id：任一条目对上即取（对齐时按人唯一）
        if e["person"] not in cbdb_of or e["cbdb_id"]:
            cbdb_of[e["person"]] = e["cbdb_id"]
        note_of[(e["person"], e["year"])] = e["note"]

    tenures: list[dict] = []
    for person in sorted(presence):
        years = sorted(presence[person])
        # 切连续段
        segs, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                segs.append(cur)
                cur = [y]
        segs.append(cur)

        for seg in segs:
            s_y, e_y = seg[0], seg[-1]
            s_evs = by_py.get((person, s_y), [])
            e_evs = by_py.get((person, e_y), [])
            s_enter = [v for v in s_evs if norm_verb(v["verb"], v.get("raw", "")) == "enter"]
            e_leave = [v for v in e_evs if norm_verb(v["verb"], v.get("raw", "")) == "leave"]

            start_month = _pick_month(s_enter)
            end_month = _pick_month(e_leave)

            # 单年段同年入离（年表并格）：月份倒挂不调换不丢弃，留标记（D4）
            month_conflict = bool(
                s_y == e_y and start_month and end_month and start_month > end_month)

            conf = 0.5
            if s_enter and e_leave:
                conf = 0.8
            elif s_enter or e_leave:
                conf = 0.7
            elif len(seg) >= 2:
                conf = 0.6
            if month_conflict:
                conf = min(conf, 0.5)

            tenures.append({
                "person": person,
                "cbdb_id": cbdb_of.get(person),
                "office": "內閣",
                "start_year": s_y,
                "start_month": start_month,
                "end_year": e_y,
                "end_month": end_month,
                "month_conflict": month_conflict,
                "confidence": conf,
                "enter_verbs": sorted({v["verb"] for v in s_enter if v["verb"]}),
                "leave_verbs": sorted({v["verb"] for v in e_leave if v["verb"]}),
                "note": note_of.get((person, s_y), ""),
                "years": seg,
            })
    return tenures


def export_official(out_path: Path | None = None) -> dict:
    """产出正式版 cabinet.json（含溯源 meta）。返回导出对象（供测试）。"""
    tenures = build_cabinet_tenures()
    doc = {
        "meta": {
            "dataset": "mingoff-cabinet",
            "version": 1,
            "source": "张德信《明代职官年表》册1·內閣大臣年表（MinerU OCR 提取，"
                      "条目与事件见 src/mingoff/data/neige_*.json）",
            "pipeline": "mingoff.official",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": {
                "tenures": len(tenures),
                "persons": len({t["person"] for t in tenures}),
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "with_start_month": sum(1 for t in tenures if t["start_month"]),
                "with_end_month": sum(1 for t in tenures if t["end_month"]),
                "cbdb_aligned": sum(1 for t in tenures if t["cbdb_id"]),
            },
        },
        "tenures": tenures,
    }
    if out_path is None:
        out_path = DATA / "official_cabinet.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


if __name__ == "__main__":
    doc = export_official()
    s = doc["meta"]["stats"]
    print(f"内阁任职段 {s['tenures']}（{s['persons']} 人，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}）")
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"CBDB 对齐 {s['cbdb_aligned']}")
    from collections import Counter
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
