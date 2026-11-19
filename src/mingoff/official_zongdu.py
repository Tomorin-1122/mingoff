# -*- coding: utf-8 -*-
"""总督年表任职段组装：vol3_zongdu_entries.json → official_zongdu.json。

official_jingying 同构适配：
  * 分组键 = (person_id, office)：office = 区域带正名（兩廣/宣大/薊遼/漕運/陝西三邊/
    貴州/京師/河道/經略…按印本剥總督/總理等前缀）；衙署不合并；
  * 页级溯源：条目自带 book_page（PDF+2215 实测）；跨页年段 start=同年最小页、
    end=最大页；
  * office_status：label-column / row-order（无本页标签年）/ mixed；
  * D-01 同名分代、gap 合并、D15 截断、CBDB 映射（未建 → 宁空勿误挂）。
纪律不变：NULL≠0、不臆造、段可溯源。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mingoff.glue_repair import apply_glue_repair
from mingoff.official import CUT_M, CUT_Y
from mingoff.official_buyuan import infer_yield_ends, merge_gap_segments
from mingoff.official_jingqing import _leave, _start_month, split_identities
from mingoff.official_jingying import _office_basis

DATA = Path(__file__).resolve().parent / "data"
CBDB_MAP_FILES = ("vol3_zongdu_person_cbdb_v1.json",)

# 官职名拆印变体归一（2026-11-19，网络考据：百度百科「总督」明代辖区名录 +
# 维基熊文灿条 [总理南畿河南山西陕西湖广四川军务，崇祯十年]）。
# 原则：只合并有字证/史证的同位异印；立场存疑的保留印本原样（office_raw 留痕）。
OFFICE_NORM: dict[str, str] = {
    # 陝西三邊：网格/拆印变体（西邊陝三=右列先读、进=邊形讹）
    "陝西三邊": "陕西三邊", "陝三邊": "陕西三邊", "陕三西邊": "陕西三邊",
    "陕三西进": "陕西三邊", "西邊陝三": "陕西三邊", "西邊陕三": "陕西三邊",
    "西边陝三": "陕西三邊", "陕三西进": "陕西三邊",
    # 漕運/河道 family（總理=總理河道 1512-1589，与河道同期同位异印）
    "督運漕運": "漕運", "總漕運": "漕運", "總河道": "河道", "總理": "河道",
    "總河漕": "河漕",          # 万历二十六年起 總督河漕
    # 經略朝鮮（1592-98 宋应昌/顧養謙/邢玠）vs 遼東經略（1619+）—— era rule 另判
    "朝鲜": "朝鮮", "經朝鲜": "朝鮮",
    # 湖廣四川貴州（嘉靖五省总督型；「四」为「四川」拆印残字）
    "湖廣四貴州": "湖廣四川貴州", "湖四貴": "湖廣四川貴州",
    # 宣大三關（正德间宣大总督兼三關，同位异印）
    "宣大三關": "宣大", "宣大三": "宣大", "宣三": "宣大",
    "延绥": "延綏",
}
NORM_ERA = {  # era-window 归一：(office, start_year 上界) → canonical
    "經略": [(1610, "朝鮮"), (9999, "遼東經略")],
    # 崇祯剿寇五省总理（熊文灿 1637：总理南畿河南山西陕西湖广四川军务）
    "陝西山西河南湖廣四川軍務直隸山東河南四川湖廣直隸河南四川山西陝西軍務專剿流寇":
        [(9999, "總理五省軍務")],
}


def _norm_office(office: str, start_year: int) -> tuple[str, str | None]:
    """返回 (canonical, raw)。era 规则优先于精确表。"""
    for bound, canon in NORM_ERA.get(office, []):
        if start_year <= bound:
            return canon, office
    if office in OFFICE_NORM:
        return OFFICE_NORM[office], office
    return office, None


def load_zongdu() -> list[dict]:
    return json.loads((DATA / "vol3_zongdu_entries.json").read_text(encoding="utf-8"))["entries"]


def load_zongdu_repaired(report: dict | None = None) -> list[dict]:
    return apply_glue_repair(load_zongdu(), "zongdu", report)


def load_zongdu_cbdb() -> dict:
    for v in CBDB_MAP_FILES:
        p = DATA / v
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def build_page_map(entries: list[dict]) -> dict[int, tuple[int, int]]:
    """year → (min_page, max_page)（条目实测页，支持跨页年）。"""
    ys: dict[int, list[int]] = defaultdict(list)
    for e in entries:
        if e.get("book_page"):
            ys[e["year"]].append(e["book_page"])
    return {y: (min(ps), max(ps)) for y, ps in ys.items()}


def build_zongdu_tenures() -> list[dict]:
    entries = [e for e in load_zongdu_repaired() if e["year"] <= CUT_Y]
    # 官职名归一（office_raw 留印本原样；era 规则按条目年）
    for e in entries:
        canon, raw = _norm_office(e["office"], e["year"])
        if raw is not None:
            e["office_raw"] = raw
        e["office"] = canon
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

    page_map = build_page_map(load_zongdu_repaired())
    mapping = load_zongdu_cbdb()
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
            sp = page_map.get(sy, (None, None))[0]
            ep = page_map.get(ey, (None, None))[1]
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": label_of[pid],
                "cbdb_id": m.get("cbdb_id"),
                "cbdb_name": m.get("cbdb_name"),
                "office": office,
                "office_raw": e.get("office_raw", office),
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
                "start_book_page": sp,
                "end_book_page": ep,
                "years": seg,
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    return infer_yield_ends(merge_gap_segments(tenures))


# ---------------- 审计 ----------------

def audit() -> dict:
    from mingoff.official_jingying import audit as _jy_audit_shape  # noqa: F401
    tenures = build_zongdu_tenures()
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
                blockers.append(f"段重叠 {key[0]}·{key[1]} "
                                f"{(a['end_year'], b['start_year'])}")
    no_page = [t for t in tenures
               if t["start_book_page"] is None or t["end_book_page"] is None]
    if no_page:
        warnings.append(f"无页码段 {len(no_page)}")
    span_bad = {t["person_id"] for t in tenures
                if t["end_year"] - t["start_year"] > 80}
    if span_bad:
        blockers.append(f"同名分代残留 {span_bad}")
    return {"blockers": blockers, "warnings": warnings, "tenures": len(tenures)}


def export_zongdu() -> dict:
    tenures = build_zongdu_tenures()
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
        "office_status_dist": {s: sum(1 for t in tenures if t["office_status"] == s)
                               for s in {t["office_status"] for t in tenures}},
        "end_clamped": sum(1 for t in tenures if t["end_clamped"]),
        "gap_merged_tenures": sum(1 for t in tenures if t.get("merged_segments", 1) >= 2),
    }
    doc = {
        "meta": {
            "dataset": "总督年表",
            "source": "张德信《明代职官年表》第3册 PDF 105–309（书页 2320–2524）；"
                      "PaddleOCR 行框解析（ocr_zongdu.py）",
            "year_range": [1449, 1646],
            "page_offset": 2215,
            "band_rule": "名字行属其下方第一条区域标签；多行纵排/单字网格拼接；"
                         "官职正名剥總督/總理等前缀，按印本如实",
            "stats": stats,
            "review_note": "无本页标签/多人同带 review 见 vol3_zongdu_review.json；"
                           "CBDB 映射未建，全部 NULL",
        },
        "tenures": tenures,
    }
    (DATA / "official_zongdu.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


if __name__ == "__main__":
    doc = export_zongdu()
    r = audit()
    s = doc["meta"]["stats"]
    print(f"总督段 {s['tenures']}（{s['persons']} 实体，{s['years_covered'][0]}–"
          f"{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print(f"官职 {len(s['offices'])} 种:", "、".join(s["offices"][:14]), "…")
    print(f"有起月 {s['with_start_month']}，离任原因 {s['with_leave']}，"
          f"D15 截尾 {s['end_clamped']}，gap 合并 {s['gap_merged_tenures']}")
    print("office_status:", s["office_status_dist"])
    print("audit:", r)
