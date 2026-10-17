# -*- coding: utf-8 -*-
"""合并研究数据 + ground truth，并施加老板拍板的三条口径。

## 本次口径（2026-10-16 老板拍板）

1. **截止 1644 年 3 月北京城陷落，不做南明**。
   崇祯十七年三月十九日（1644-04-25）李自成入京，此后弘光朝任命一律排除。
2. **月份字段保留**（可为 null）。CBDB 月份不可用（实测填充率 1.2% 且多为 0），
   月度可靠来源是中研院明實錄，属后续工作；现在**不臆造月份**。
3. **扩展职官**：仍以《明史》年表为主（年份连续性好），CBDB 留待引入校勘。

## 为什么在南明处"切"而不是"标"

上一版把 1644 年的南明任命降置信度保留。老板要求不做南明 —— 那就**排除**，
不是标注。理由：降置信度仍会画进图里，而它们在时间轴上会让 1644 年虚高，
使用者难以分辨。**宁可少画，不可误导。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]

#: 截止点：崇祯十七年三月（1644-04）。此月及其后的任命一律排除。
CUTOFF_YEAR = 1644
CUTOFF_MONTH = 3

OFFICE_ORDER = [
    "內閣首輔", "內閣閣臣", "吏部尚書", "戶部尚書", "禮部尚書",
    "兵部尚書", "刑部尚書", "工部尚書", "都察院左都御史",
]
DEPARTMENT = {
    "內閣首輔": "內閣", "內閣閣臣": "內閣",
    "吏部尚書": "吏部", "戶部尚書": "戶部", "禮部尚書": "禮部",
    "兵部尚書": "兵部", "刑部尚書": "刑部", "工部尚書": "工部",
    "都察院左都御史": "都察院",
}

#: 明确的南明（弘光朝）任命 —— 逐条列出而非靠年份判断，
#: 因为有些 1644 年的任命确属北京崇祯朝（如 3 月前的任免）。
NANMING_PERSONS = {
    "張慎言", "張有譽", "顧錫疇", "解學龍", "程註", "何應瑞", "李沾",
    "劉宗周", "吳履中", "王鐸",
}


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def database_ground_truth() -> dict:
    """从 mingoff.sqlite 直接取兵部尚书记录（张德信年表口径）。

    返回与 `export_demo.export()` 相同的结构，便于复用同一段合并逻辑。
    这样即使 `web/demo-data.json` 被覆盖，ground truth 也永远取自权威源。
    """
    import sqlite3

    db = ROOT / "data" / "mingoff.sqlite"
    if not db.is_file():
        raise FileNotFoundError(
            f"数据库不存在: {db}（先跑 mingoff init && mingoff seed）"
        )
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT t.start_year, t.end_year, t.start_month, t.end_month,
                   t.tenure_type, t.leave_reason, t.confidence,
                   o.office_chn AS office, p.name_chn AS person,
                   (SELECT GROUP_CONCAT(s.source_name, '、')
                      FROM tenure_source ts JOIN source s ON s.source_id = ts.source_id
                     WHERE ts.tenure_id = t.tenure_id) AS sources
              FROM tenure t
              JOIN office o ON o.office_id = t.office_id
              JOIN person p ON p.person_id = t.person_id
             ORDER BY (t.start_year IS NULL), t.start_year, t.tenure_id
            """
        ).fetchall()
    finally:
        conn.close()
    return {
        "tenures": [
            {
                "office": r["office"], "person": r["person"],
                "start": r["start_year"], "end": r["end_year"],
                "start_month": r["start_month"], "end_month": r["end_month"],
                "type": r["tenure_type"], "leave": r["leave_reason"] or "",
                "confidence": r["confidence"], "source": r["sources"] or "",
                "note": "",
            }
            for r in rows
        ]
    }


def main() -> int:
    research = load(ROOT / "src/mingoff/data/chongzhen_offices.json")
    # 兵部尚书 ground truth **直接查数据库**，不从 web/demo-data.json 读。
    #
    # 踩过的坑：demo-data.json 既是 export_demo 的输出、又被 merge 当输入，
    # 于是"合并 → 写 demo-data.json → 下次再合并"会把同一批数据反复并入，
    # 实测兵部尚书从 14 条涨到 152 条。**输入与输出必须分属不同文件。**
    gt = database_ground_truth()

    tenures: list[dict] = []
    dropped: list[str] = []

    def cut(t: dict) -> bool:
        """是否应排除整条：南明人 或 起点晚于截止月。"""
        if t.get("person") in NANMING_PERSONS:
            dropped.append(t.get("person", "?"))
            return True
        sy, sm = t.get("start"), t.get("start_month")
        if sy is not None and (sy > CUTOFF_YEAR
                               or (sy == CUTOFF_YEAR and sm and sm > CUTOFF_MONTH)):
            dropped.append(f"{t.get('person')}({sy})")
            return True
        return False

    def clamp(rec: dict) -> dict:
        """把超过断限的**终年**截到 1644 年 3 月。

        老板要求："截止时间是 1644 年 3 月……直接写 1644 年 3 月，截断一下
        就好了后面都不要了。"所以 end 一律不超过 1644-03 ——
        包括崇祯本人（他 1644 年 3 月死，之后不可能还在位）。

        注意：`end_month` 原来多为 None（史料只到年）。截断时若年份 > 1644，
        就把 end 设为 1644、end_month 设为 3，让它在图上正好止于断限。

        截断时打上 `end_clamped=True`，**区分"史料记为 3 月"与"因断限截到 3 月"**。
        不区分的话，前端会把 clamp 产物当成"史料精确到月" —— 那是虚报精度。
        """
        ey, em = rec.get("end"), rec.get("end_month")
        if ey is None:
            return rec
        if ey > CUTOFF_YEAR or (ey == CUTOFF_YEAR and (em or 0) > CUTOFF_MONTH):
            rec["end"] = CUTOFF_YEAR
            rec["end_month"] = CUTOFF_MONTH
            rec["end_clamped"] = True
        elif ey == CUTOFF_YEAR and em is None:
            # 1644 年只写道"年"——因断限在 3 月，按 3 月算，同样标记为截断
            rec["end_month"] = CUTOFF_MONTH
            rec["end_clamped"] = True
        return rec

    # ---- 研究数据（《明史》年表）----
    for t in research["tenures"]:
        rec = {
            "office": t["office"],
            "department": DEPARTMENT.get(t["office"], ""),
            "person": t["person"],
            "start": t.get("start_year"),
            "end": t.get("end_year"),
            "start_month": t.get("start_month"),
            "end_month": t.get("end_month"),
            "type": t.get("tenure_type") or "实授",
            "leave": t.get("leave_reason") or "",
            "confidence": t.get("confidence"),
            "source": t.get("source") or "",
            "note": t.get("note") or "",
            "tradition": "《明史》年表",
        }
        if not cut(rec):
            tenures.append(clamp(rec))

    # ---- ground truth（兵部尚书，张德信年表）----
    for t in gt["tenures"]:
        rec = {
            "office": "兵部尚書",
            "department": "兵部",
            "person": t["person"],
            "start": t["start"],
            "end": t["end"],
            "start_month": t.get("start_month"),
            "end_month": t.get("end_month"),
            "type": t["type"],
            "leave": t["leave"],
            "confidence": t["confidence"],
            "source": t["source"],
            "note": t["note"],
            "tradition": "张德信年表",
        }
        if not cut(rec):
            tenures.append(clamp(rec))

    # 职位顺序
    used = {t["office"] for t in tenures}
    offices = [
        {"name": o, "department": DEPARTMENT.get(o, ""), "order": i}
        for i, o in enumerate(OFFICE_ORDER) if o in used
    ]

    years = [t["start"] for t in tenures if t["start"]] + \
            [t["end"] for t in tenures if t["end"]]
    y0, y1 = min(years), max(years)

    out = {
        "meta": {
            "title": "明代职官数据库",
            "scope": f"崇祯朝 {y0}–{y1}",
            "year_min": y0,
            "year_max": y1,
            "count": len(tenures),
            "emperor": "朱由檢",
            "emperor_temple": "明思宗",
            "era": "崇禎",
            "cutoff_note": "截止崇祯十七年三月（1644-04）北京城陷落；不含南明",
            "source_note": "《明史》卷110 宰辅年表、卷112 七卿年表（点校本）；"
                           "兵部尚书据张德信《明代职官年表》",
            "caveat": "缺载处留空，不作填补；月份未载者不臆造",
            "traditions": ["《明史》年表", "张德信年表"],
        },
        "offices": offices,
        "tenures": tenures,
    }

    target = ROOT / "web" / "demo-data-merged.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    print(f"[合并完成] {len(tenures)} 条任职，{len(offices)} 个官职，{y0}–{y1}")
    print(f"           排除南明/越界 {len(dropped)} 条")
    if dropped:
        print(f"           排除名单: {'、'.join(dict.fromkeys(dropped))}")
    print()
    for o, n in Counter(t["office"] for t in tenures).most_common():
        print(f"    {o:<16} {n} 条")
    print(f"\n→ {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
