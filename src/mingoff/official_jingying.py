# -*- coding: utf-8 -*-
"""总督京营戎政大臣任职段组装：vol3_jingying_entries.json → official_jingying.json。

official_jingqing 同构适配（数据接入规范 2.2/3.3/3.4/3.6 + D15）：
  * 分组键 = (person_id, office)：七衙署带（總督京營戎政/協理京營戎政/五軍營/
    三千營/神樞營/神機營/京營參將）各自独立成段；
    三千營/神樞營 为同槽异名（书本身混印，1570 起即见神樞營标签，非硬切换）——
    按印本如实分立；
  * 页级溯源：书页 = PDF 页 + 2215（页脚锚点 2222/2223/2526）；一年一页 →
    book_page = year + 672（1550→2222 … 1646→2318）；
  * office_status：label-column（段内含标签页年）/ row-order（全段无标签页，
    置信封顶 0.6）/ mixed；无标签页条目 review 贯通到段；
  * D-01 同名分代（>80 年跨度拆 #k）、gap 合并、D15 截断（1644.3）；
  * CBDB 映射 vol3_jingying_person_cbdb_v1.json（未建 → 全 NULL，宁空勿误挂）。

三条纪律不变：NULL≠0、不臆造、段可溯源。
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mingoff.glue_repair import apply_glue_repair
from mingoff.official import CUT_M, CUT_Y
from mingoff.official_buyuan import infer_yield_ends, merge_gap_segments
from mingoff.official_jingqing import _leave, _start_month, split_identities

DATA = Path(__file__).resolve().parent / "data"
PAGE_BASE = 2222          # 1550 年书页；book_page = year + 672
YEAR0 = 1550

CBDB_MAP_FILES = ("vol3_jingying_person_cbdb_v1.json",)


def load_jingying() -> list[dict]:
    return json.loads((DATA / "vol3_jingying_entries.json").read_text(encoding="utf-8"))["entries"]


def load_jingying_repaired(report: dict | None = None) -> list[dict]:
    """OCR 条目 + 格子级修复（glue_repair "jingying" 表；暂无规则）。"""
    return apply_glue_repair(load_jingying(), "jingying", report)


def load_jingying_cbdb() -> dict:
    for v in CBDB_MAP_FILES:
        p = DATA / v
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def build_page_map() -> dict[int, int]:
    return {y: y - YEAR0 + PAGE_BASE for y in range(YEAR0, 1647)}


def _office_basis(seg_years: list[int], review_of: dict[int, str | None]) -> str:
    flagged = {y for y in seg_years
               if review_of.get(y) and "无标签页" in review_of[y]}
    if not flagged:
        return "label-column"
    if flagged == set(seg_years):
        return "row-order"
    return "mixed"


def build_jingying_tenures() -> list[dict]:
    entries = [e for e in load_jingying_repaired() if e["year"] <= CUT_Y]
    identities = split_identities(entries)
    pid_of: dict[tuple[str, int], str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            for y in ys:
                pid_of[(name, y)] = pid
    label_of: dict[str, str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            label_of[pid] = f"{name}（{min(ys)}–{max(ys)}）" if pid != name else name

    page_map = build_page_map()
    mapping = load_jingying_cbdb()
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in entries:
        pid = pid_of[(e["person"], e["year"])]
        by_key[(pid, e["office"])].append(e)

    tenures: list[dict] = []
    for (pid, office), rows in sorted(by_key.items()):
        rows.sort(key=lambda e: e["year"])
        person = rows[0]["person"]
        dedup: list[dict] = []
        for e in rows:
            if dedup and dedup[-1]["year"] == e["year"]:
                if e["note"] and e["note"] not in dedup[-1]["note"]:
                    dedup[-1]["note"] = (dedup[-1]["note"] + "；" + e["note"]).strip("；")
            else:
                dedup.append(dict(e))
        rows = dedup

        years = [e["year"] for e in rows]
        note_of = {e["year"]: e["note"] for e in rows}
        review_of = {e["year"]: e.get("review") for e in rows}
        segs, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                segs.append(cur)
                cur = [y]
        segs.append(cur)

        same_name_risk = len(identities[person]) > 1
        for seg in segs:
            sy, ey = seg[0], seg[-1]
            s_note, e_note = note_of.get(sy, ""), note_of.get(ey, "")
            sm, sm_leap, sm_event = _start_month(s_note)
            em, em_leap, leave = _leave(e_note)

            eff_sm = sm or (em if (sy == ey and em) else None)
            if sy > CUT_Y or (sy == CUT_Y and eff_sm and eff_sm > CUT_M):
                continue
            if sy == CUT_Y and sm is None and "南" in s_note:
                continue

            clamped = False
            if ey > CUT_Y:
                ey, em, clamped = CUT_Y, CUT_M, True
            elif ey == CUT_Y and (em is None or em > CUT_M):
                em, clamped = CUT_M, True

            conflict = bool(sy == ey and sm and em and sm > em)
            has_enter, has_leave = sm_event, leave != "未載"
            if has_enter and has_leave:
                conf = 0.8
            elif has_enter or has_leave:
                conf = 0.7
            elif sm or len(seg) >= 2:
                conf = 0.6
            else:
                conf = 0.5
            if conflict:
                conf = min(conf, 0.5)
            basis = _office_basis(seg, review_of)
            if basis == "row-order":
                conf = min(conf, 0.6)
            elif basis == "mixed":
                conf = min(conf, 0.7)

            ttype = "署理" if "署" in s_note else "实授"
            m = mapping.get(pid, {})
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": label_of[pid],
                "cbdb_id": m.get("cbdb_id"),       # 未建映射 → NULL（宁空勿误挂）
                "cbdb_name": m.get("cbdb_name"),
                "office": office,
                "office_raw": office,
                "office_status": basis,
                "tenure_type": ttype,
                "start_year": sy,
                "start_month": sm,
                **({"start_leap": True} if sm_leap else {}),
                "end_year": ey,
                "end_month": em,
                **({"end_leap": True} if em_leap else {}),
                "month_conflict": conflict,
                "end_clamped": clamped,
                "confidence": conf,
                "leave": leave,
                "note": s_note.strip(),
                "start_book_page": page_map.get(sy),
                "end_book_page": page_map.get(ey),
                "years": seg,
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    return infer_yield_ends(merge_gap_segments(tenures))


# ---------------- 审计（G2/G3/G6-京营版） ----------------

def audit() -> dict:
    tenures = build_jingying_tenures()
    blockers: list[str] = []
    warnings: list[str] = []
    bad_years = [t for t in tenures
                 if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    if bad_years:
        blockers.append(f"段年不连续 {len(bad_years)}")
    bad_month = [t for t in tenures if any(
        mm is not None and not 1 <= mm <= 12 for mm in (t["start_month"], t["end_month"]))]
    if bad_month:
        blockers.append(f"月越界 {len(bad_month)}")
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > CUT_M)]
    if d15:
        blockers.append(f"D15 残留 {len(d15)}")
    by_key = defaultdict(list)
    for t in tenures:
        by_key[(t["person_id"], t["office"])].append(t)
    for key, ts in by_key.items():
        ts.sort(key=lambda t: t["start_year"])
        for a, b in zip(ts, ts[1:]):
            if a["end_year"] >= b["start_year"] and not a.get("gap_years"):
                overlap = (a["end_year"], b["start_year"])
                if overlap[0] >= overlap[1]:
                    blockers.append(f"段重叠 {key[0]}·{key[1]} {overlap}")
    no_page = [t for t in tenures
               if t["start_book_page"] is None or t["end_book_page"] is None]
    if no_page:
        warnings.append(f"无页码段 {len(no_page)}")
    span_bad = {t["person_id"] for t in tenures
                if t["end_year"] - t["start_year"] > 80}
    if span_bad:
        blockers.append(f"同名分代残留 {span_bad}")
    return {"blockers": blockers, "warnings": warnings, "tenures": len(tenures)}


# ---------------- 导出 ----------------

def export_jingying() -> dict:
    tenures = build_jingying_tenures()
    stats = {
        "tenures": len(tenures),
        "persons": len({t["person_id"] for t in tenures}),
        "display_persons": len({t["person"] for t in tenures}),
        "offices": sorted({t["office"] for t in tenures}),
        "years_covered": [min(t["start_year"] for t in tenures),
                          max(t["end_year"] for t in tenures)],
        "person_years": sum(len(t["years"]) for t in tenures),
        "with_start_month": sum(1 for t in tenures if t["start_month"]),
        "with_end_month": sum(1 for t in tenures if t["end_month"]),
        "with_leave": sum(1 for t in tenures if t["leave"] != "未載"),
        "office_status_dist": dict(defaultdict(int,
            {s: sum(1 for t in tenures if t["office_status"] == s)
             for s in {t["office_status"] for t in tenures}})),
        "end_clamped": sum(1 for t in tenures if t["end_clamped"]),
        "gap_merged_tenures": sum(1 for t in tenures if t.get("merged_segments", 1) >= 2),
    }
    doc = {
        "meta": {
            "dataset": "总督京营戎政大臣年表",
            "source": "张德信《明代职官年表》第3册 PDF 7–103（书页 2222–2318）；"
                      "PaddleOCR 行框解析（ocr_jingying.py）",
            "year_range": [1550, 1646],
            "page_offset": 2215,
            "band_rule": "名字行属于其下方第一条位置标签（京卿同规律）；"
                         "无标签页继承最近带标签页 schema；"
                         "三千營 万历十六年(1588) 改称 神樞營，同槽异名分立",
            "stats": stats,
            "review_note": "无标签页/多人同带 review 见 vol3_jingying_review.json；"
                           "CBDB 映射未建，全部 NULL（宁空勿误挂）",
        },
        "tenures": tenures,
    }
    (DATA / "official_jingying.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


if __name__ == "__main__":
    doc = export_jingying()
    r = audit()
    s = doc["meta"]["stats"]
    print(f"总督京营戎政段 {s['tenures']}（{s['persons']} 实体，{s['years_covered'][0]}–"
          f"{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("官职:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"离任原因 {s['with_leave']}，D15 截尾 {s['end_clamped']}，"
          f"gap 合并 {s['gap_merged_tenures']}")
    print("office_status:", s["office_status_dist"])
    print("audit:", r)
