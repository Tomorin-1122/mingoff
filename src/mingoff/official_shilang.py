# -*- coding: utf-8 -*-
"""部院侍郎年表（京師）任职段组装：vol1_shilang_geo.json → official_shilang.json。

official_jingqing.py 同构适配（三条纪律不变：NULL≠0、不臆造、段可溯源）：

  * 输入 = 几何解析全量 6,249 条（299 页 / 277 年，PaddleOCR 行级 bbox）；
  * 行带 → 职官：六部 row1=左侍郎（1376 前单侍郎带）、row2=右侍郎、row≥3=深行
    （未核行带，pending）；原书 (左)(右) 旗标覆盖行位推断；都察院 = 左/右副都御史
    （1383 前单带=副都御史）；御史中丞/提督易州山廠/總糧儲 沿原书；
  * 原书核验：shilang_repair.BOOK_FIX（954/800/760 三页已逐行核对原书页图修正），
    未核验的 band 警报页条目打 pending_book_check（confidence 封顶 0.5 + review），
    站点按 D-11 惯例灰显——数据不删，等校对台逐页清除；
  * D-01 同名分代 / D15 断限 / 1–2 年 gap 合并 / 实录互证：沿京卿；
  * 页级溯源：year → book_page 由条目自带 book 页实测（逐众数）；
  * audit：G2/G3/G6 + CBDB 生卒冲突/同 id 门（与 keji/jingqing 同款）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mingoff.match_cbdb import S2T
from mingoff.official import CUT_M, CUT_Y, _cross_year, _month_of, build_shilu
from mingoff.official_buyuan import CONF_DOWN, merge_gap_segments
from mingoff.official_jingqing import (LEAVE_LABEL_JQ, LEAVE_QIAN,
                                       LEAVE_VERBS_JQ, MAX_SPAN, _chunks,
                                       _start_month, split_identities)
from mingoff.shilang_repair import IDENTITY_FORCE, apply_book_fix

DATA = Path(__file__).resolve().parent / "data"
ROOT = DATA.parents[2]
GEO = DATA / "vol1_shilang_geo.json"
ALARMS = DATA / "vol1_shilang_geo_alarms.json"

# CBDB 映射（scripts/match_official_cbdb.py 产出；缺失 = 未对齐，宁空勿误挂）
CBDB_MAP_FILES = ("vol1_shilang_person_cbdb_v1.json",)


def load_shilang_cbdb() -> dict:
    for v in CBDB_MAP_FILES:
        p = DATA / v
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}

MINISTRIES = ("吏部", "戶部", "禮部", "兵部", "刑部", "工部")
CANON_OFFICES = (
    *(f"{m}{s}" for m in MINISTRIES for s in ("侍郎", "左侍郎", "右侍郎")),
    "副都御史", "左副都御史", "右副都御史", "御史中丞",
    "提督易州山廠", "總糧儲",
)
# 仕历链/任职判定词干（CBDB matcher 用）
CAREER_STEM = {**{m: [m] for m in MINISTRIES},
               "副都御史": ["御史"], "左副都御史": ["御史"], "右副都御史": ["御史"],
               "御史中丞": ["御史"],
               "提督易州山廠": ["工部", "山廠"], "總糧儲": ["總督倉場", "戶部"]}
HINT_EXACT = {
    **{f"{m}侍郎": [f"{m}侍郎"] for m in MINISTRIES},
    **{f"{m}左侍郎": [f"{m}左侍郎", f"{m}侍郎"] for m in MINISTRIES},
    **{f"{m}右侍郎": [f"{m}右侍郎", f"{m}侍郎"] for m in MINISTRIES},
    "副都御史": ["副都御史"], "左副都御史": ["左副都御史", "副都御史"],
    "右副都御史": ["右副都御史", "副都御史"], "御史中丞": ["御史中丞", "御史"],
    "提督易州山廠": ["山廠"], "總糧儲": ["總督倉場", "倉場", "糧儲"],
}

# 六科离场动词 = 京卿集 + 閑住（含「閒住」异体）
LEAVE_VERBS_SL = LEAVE_VERBS_JQ + ("閑住", "閒住")
LEAVE_LABEL_SL = {**LEAVE_LABEL_JQ, "閑住": "閑住", "閒住": "閑住"}


def _leave_sl(note: str) -> tuple[int | None, str]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        label = None
        for v in LEAVE_VERBS_SL:
            if v in c:
                label = LEAVE_LABEL_SL.get(v, v)
                break
        if label is None:
            m = LEAVE_QIAN.search(c)
            if m:
                label = {"遷": "遷除", "改": "改除", "調": "調除"}[m.group()[0]]
        if label:
            return _month_of(c), label
    return None, "未載"


def band_alarm_pages() -> set[int]:
    """行带类警报页（deep_row/label_mismatch/页级/借衙署/年份）——须原书核验。"""
    if not ALARMS.is_file():
        return set()
    al = json.loads(ALARMS.read_text(encoding="utf-8"))
    al = al if isinstance(al, list) else al.get("alarms", [])
    band_kinds = {"deep_row_suspect", "label_mismatch", "borrow_office",
                  "page_level", "first_band", "year", "借衙署"}
    out = set()
    for a in al:
        if a.get("kind") in band_kinds:
            out.add(a["book"])
    return out


def load_shilang_repaired(report: dict | None = None) -> list[dict]:
    """geo 条目 + 原书核验修正 + 行带→职官派生。"""
    doc = json.loads(GEO.read_text(encoding="utf-8"))
    entries = apply_book_fix(doc["entries"], report)
    alarms_pages = band_alarm_pages()

    # 各部右侍郎带（row2）起始年——单侍郎带（row1）的左/右命名分界
    row2_start: dict[str, int] = {}
    for e in entries:
        if e["row"] == 2 and e["office"] in MINISTRIES + ("都察院",):
            o = e["office"]
            if o not in row2_start or e["year"] < row2_start[o]:
                row2_start[o] = e["year"]

    def derive(e: dict) -> tuple[str, bool]:
        off, row, tag, year = e["office"], e["row"], e.get("tag"), e["year"]
        pending = e["book"] in alarms_pages and not e.get("office_fix")
        if off in MINISTRIES:
            if tag in ("左", "右"):
                return f"{off}{tag}侍郎", pending
            if row == 1:
                return (f"{off}左侍郎" if year >= row2_start.get(off, 1376)
                        else f"{off}侍郎"), pending
            if row == 2:
                return f"{off}右侍郎", pending
            return f"{off}侍郎", True          # r≥3 未核行带，一律 pending
        if off == "都察院":
            if tag in ("左", "右"):
                return f"{tag}副都御史", pending
            if row == 1:
                return ("左副都御史" if year >= row2_start.get("都察院", 1384)
                        else "副都御史"), pending
            if row == 2:
                return "右副都御史", pending
            return "副都御史", True
        if off == "御史中丞":
            return "御史中丞", pending
        if "山廠" in off or off == "提督":
            return "提督易州山廠", pending
        if off == "總糧儲":
            return "總糧儲", pending
        return off, pending

    out = []
    for e in entries:
        office, pending = derive(e)
        note = "；".join(n for n in (e.get("notes") or []) if n)
        if e.get("inline_note"):
            note = (note + "；" if note else "") + f"（{e['inline_note']}）"
        if e.get("tag") and e["tag"] not in ("左", "右"):
            note = (note + "；" if note else "") + f"原书标注（{e['tag']}）"
        out.append({
            "year": e["year"], "era": e.get("era"), "office": office,
            "person": e["person"], "note": note,
            "raw": (e.get("office_raw") or "") + "｜" + (e["person"] or ""),
            "book": e["book"], "conf_src": e.get("conf"), "pending": pending,
            "review": (None if not pending else "行带警报页，归属待原书核验"),
            "office_fix": e.get("office_fix"),
        })
    return out


# ---------------- 页级溯源：year → book_page（条目自带，逐众数） ----------------

def build_page_map(entries: list[dict]) -> dict[int, int]:
    by_year: dict[int, Counter] = defaultdict(Counter)
    for e in entries:
        by_year[e["year"]][e["book"]] += 1
    return {y: c.most_common(1)[0][0] for y, c in by_year.items()}


# ---------------- D-01 同名分代（沿京卿 split_identities） ----------------

# ---------------- 组装 ----------------

def load_shilang() -> list[dict]:
    return load_shilang_repaired()


def _office_basis_sl(seg_years: list[int], pending_of: dict[int, bool]) -> str:
    n_pending = sum(1 for y in seg_years if pending_of.get(y))
    if n_pending == 0:
        return "verified"
    if n_pending == len(seg_years):
        return "pending"
    return "mixed"


def build_shilang_tenures() -> list[dict]:
    entries = [e for e in load_shilang_repaired() if e["year"] <= CUT_Y]
    identities = split_identities(entries)
    # 强制分代（shilang_repair.IDENTITY_FORCE）：真两人但跨度未过 80 年阈值者，
    # 按 ≥10 年缺口切——王暹 1387–88 兵右（試）≠ 1449 左副都御史（原书 p701/p764）
    for nm in IDENTITY_FORCE:
        if nm not in identities:
            continue
        seq = sorted(set().union(*[g for _, g in identities[nm]]))
        if len(seq) < 2:
            continue
        groups, cur = [], [seq[0]]
        for y in seq[1:]:
            if y - cur[-1] >= 10:
                groups.append(set(cur))
                cur = [y]
            else:
                cur.append(y)
        groups.append(set(cur))
        if len(groups) > 1:
            identities[nm] = [(f"{nm}#{k + 1}", g) for k, g in enumerate(groups)]
    pid_of: dict[tuple[str, int], str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            for y in ys:
                pid_of[(name, y)] = pid
    label_of_pid: dict[str, str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            label_of_pid[pid] = f"{name}（{min(ys)}–{max(ys)}）" if pid != name else name

    page_map = build_page_map(entries)
    mapping = load_shilang_cbdb()
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
                dedup[-1]["pending"] = dedup[-1].get("pending") and e.get("pending", False)
            else:
                dedup.append(dict(e))
        rows = dedup

        years = [e["year"] for e in rows]
        note_of = {e["year"]: e["note"] for e in rows}
        pending_of = {e["year"]: bool(e.get("pending")) for e in rows}
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
            sm, sm_event = _start_month(s_note)
            em, leave = _leave_sl(e_note)

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
            basis = _office_basis_sl(seg, pending_of)
            if basis == "pending":
                conf = min(conf, 0.5)
            elif basis == "mixed":
                conf = min(conf, 0.6)

            ttype = "署理" if "署" in s_note else "实授"
            m = mapping.get(pid, {})
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": label_of_pid[pid],
                "cbdb_id": m.get("cbdb_id"),
                "cbdb_name": m.get("cbdb_name"),
                "office": office,
                "office_raw": office,
                "office_status": basis,
                "tenure_type": ttype,
                "start_year": sy,
                "start_month": sm,
                "end_year": ey,
                "end_month": em,
                "month_conflict": conflict,
                "end_clamped": clamped,
                "confidence": conf,
                "leave": leave,
                "note": s_note.strip(),
                "start_book_page": page_map.get(sy),
                "end_book_page": page_map.get(ey),
                "years": seg,
                **({"pending_book_check": True} if basis in ("pending", "mixed")
                   else {}),
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    return merge_gap_segments(tenures)


# ---------------- 审计（G2/G3/G6-侍郎版） ----------------

def audit() -> dict:
    entries = [e for e in load_shilang_repaired() if e["year"] <= CUT_Y]
    tenures = build_shilang_tenures()
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
    overlap = []
    for ts in by_key.values():
        ts.sort(key=lambda t: t["start_year"])
        for a, b in zip(ts, ts[1:]):
            if b["start_year"] <= a["end_year"]:
                overlap.append(f"{a['person_id']}/{a['office']}@{b['start_year']}")
    if overlap:
        blockers.append(f"同衙段重叠 {len(overlap)}: {overlap[:5]}")
    span_by_id: dict[str, tuple[int, int]] = {}
    for t in tenures:
        lo, hi = span_by_id.get(t["person_id"], (t["start_year"], t["end_year"]))
        span_by_id[t["person_id"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    too_long = [p for p, (lo, hi) in span_by_id.items() if hi - lo > MAX_SPAN]
    if too_long:
        blockers.append(f"实体跨度>80年 {len(too_long)}: {too_long[:5]}")
    bad_office = sorted({t["office"] for t in tenures} - set(CANON_OFFICES))
    if bad_office:
        blockers.append(f"衙署越界 {bad_office}")
    covered: set[int] = set()
    for t in tenures:
        covered |= set(t["years"])
    missing = [y for y in range(1368, CUT_Y + 1) if y not in covered]
    if missing:
        blockers.append(f"缺年 {missing[:10]}")
    # 页面核验状态（不阻断——灰显交付，校对台消化）
    n_pending = sum(1 for t in tenures if t.get("pending_book_check"))
    if n_pending:
        warnings.append(f"待原书核验段 {n_pending}（band 警报页，灰显交付）")
    # CBDB 门
    cbdb_map = {}
    for v in ("vol1_shilang_person_cbdb_v1.json",):
        p = DATA / v
        if p.is_file():
            cbdb_map = json.loads(p.read_text(encoding="utf-8"))
            break
    if cbdb_map:
        db_path = DATA.parents[3] / "_cbdb" / "cbdb_20261010.sqlite3"
        if not db_path.is_file():
            db_path = Path.cwd() / "_cbdb" / "cbdb_20261010.sqlite3"
        if db_path.is_file():
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                date_conflicts: list[str] = []
                ids: dict[int, set[str]] = defaultdict(set)
                for t in tenures:
                    cid = t.get("cbdb_id")
                    if cid:
                        ids[cid].add(t["person_id"].translate(S2T))
                        bio = con.execute(
                            "select c_birthyear, c_deathyear from BIOG_MAIN "
                            "where c_personid=?", (cid,)).fetchone()
                        if bio and ((bio[1] and bio[1] < t["start_year"] - 1)
                                    or (bio[0] and bio[0] > t["end_year"] + 1)):
                            date_conflicts.append(
                                f"{t['person_id']}@{t['start_year']}({bio[0]}-{bio[1]})")
                for pid, m in cbdb_map.items():
                    if m.get("cbdb_id"):
                        ids[m["cbdb_id"]].add(pid.translate(S2T))
                shared_raw = {cid: sorted(ps) for cid, ps in ids.items()
                              if len(ps) > 1}
                # 同 id 组：若组内人名都能经 CBDB 自身别名表归到该 id（同一人不同名，
                # 如 許觀=黃觀、蘭芳=藺芳），不算冲突；只有真正异人（趙榮/王榮 型）才挂
                if shared_raw:

                    def _benign(cid: int, group: set[str]) -> bool:
                        nm = con.execute(
                            "select c_name_chn from BIOG_MAIN where c_personid=?",
                            (cid,)).fetchone()
                        pool = {a[0] for a in con.execute(
                            "select c_alt_name_chn from ALTNAME_DATA "
                            "where c_personid=?", (cid,)).fetchall()}
                        if nm:
                            pool.add(nm[0])
                        return all(n.split("#")[0].translate(S2T) in pool
                                   for n in group)

                    shared = {str(k): v for k, v in shared_raw.items()
                              if not _benign(k, set(v))}
                else:
                    shared = {}
                if date_conflicts:
                    blockers.append(f"CBDB 生卒冲突 {len(date_conflicts)}: "
                                    f"{date_conflicts[:5]}")
                if shared:
                    blockers.append(f"同一 CBDB id 多正名 {len(shared)}: "
                                    f"{[(k, v) for k, v in list(shared.items())[:5]]}")
            finally:
                con.close()
        else:
            warnings.append("CBDB 库缺失，跳过生卒冲突/同 id 校验")
    person_years = sum(len(t["years"]) for t in tenures)
    gap_years = sum(len(t.get("gap_years") or []) for t in tenures)
    if person_years - gap_years > len(entries):
        blockers.append(f"人-年 {person_years - gap_years} 超过条目 {len(entries)}")
    return {"blockers": blockers, "warnings": warnings,
            "tenures": len(tenures), "person_years": person_years,
            "pending_tenures": n_pending, "entries": len(entries)}


# ---------------- 导出 ----------------

def export_shilang(out_path: Path | None = None) -> dict:
    tenures = build_shilang_tenures()
    shilu = build_shilu(tenures)
    entry_years = {e["year"] for e in load_shilang_repaired() if e["year"] <= CUT_Y}
    missing_years = sorted(set(range(1368, CUT_Y + 1)) - entry_years)
    doc = {
        "meta": {
            "dataset": "mingoff-shilang",
            "version": 1,
            "canvas_from": 1368,
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "source": "张德信《明代职官年表》册1·部院侍郎年表（京師）正文 682–980"
                      "（PDF 697–995；PaddleOCR 行级 bbox 几何解析 ocr_shilang_geo.py）；"
                      "页级溯源用条目自带书页；CBDB 对齐 v1（宁空勿误挂）",
            "pipeline": "mingoff.official_shilang (v1: (person_id,office) 分组 + 行带→"
                        "左右侍郎派生 + 原书核验修正 954/800/760 + band 警报页 pending "
                        "灰显 + D-01 同名分代 + gap 合并 + D15)",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": {
                "tenures": len(tenures),
                "persons": len({t["person_id"] for t in tenures}),
                "display_persons": len({t["person"] for t in tenures}),
                "split_entities": len({t["person_id"] for t in tenures
                                       if "#" in t["person_id"]}),
                "same_name_entities": len({t["person"] for t in tenures
                                           if t.get("same_name_risk")}),
                "offices": sorted({t["office"] for t in tenures}),
                "gap_merged_tenures": sum(1 for t in tenures if t.get("gap_years")),
                "gap_years_total": sum(len(t.get("gap_years") or []) for t in tenures),
                "pending_book_check": sum(1 for t in tenures
                                          if t.get("pending_book_check")),
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "missing_years": missing_years,
                "with_start_month": sum(1 for t in tenures if t["start_month"]),
                "with_end_month": sum(1 for t in tenures if t["end_month"]),
                "with_start_page": sum(1 for t in tenures if t.get("start_book_page")),
                "with_end_page": sum(1 for t in tenures if t.get("end_book_page")),
                "cbdb_aligned": sum(1 for t in tenures if t["cbdb_id"]),
                "with_leave": sum(1 for t in tenures if t["leave"] != "未載"),
                "shu_li": sum(1 for t in tenures if t["tenure_type"] == "署理"),
                "same_name_risk": sum(1 for t in tenures if t.get("same_name_risk")),
                "office_status_dist": dict(Counter(t.get("office_status")
                                                   for t in tenures)),
                "shilu_persons": len(shilu),
                "shilu_hits": sum(v["count"] for v in shilu.values()),
                "person_years": sum(len(t["years"]) for t in tenures),
            },
        },
        "tenures": tenures,
        "shilu": shilu,
    }
    if out_path is None:
        out_path = DATA / "official_shilang.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def refresh_manifest(doc: dict) -> None:
    entry_years = {e["year"] for e in load_shilang_repaired() if e["year"] <= CUT_Y}
    missing = sorted(set(range(1368, CUT_Y + 1)) - entry_years)
    tenures = doc["tenures"]
    bad_years = [t for t in tenures
                 if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    bad_month = [t for t in tenures if any(
        mm is not None and not 1 <= mm <= 12 for mm in (t["start_month"], t["end_month"]))]
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > CUT_M)]
    try:
        _r = audit()
        g6 = "pass" if not _r["blockers"] else f"fail({_r['blockers']})"
    except Exception as exc:  # pragma: no cover
        g6 = f"not-run({exc})"
    m = {
        "source": "张德信《明代职官年表》册1（扫描 PDF）",
        "pdf_pages": 1281, "offset": 15,
        "table": "部院侍郎年表（京師）", "book_pages": [682, 980], "pdf_range": [697, 995],
        "tool": {"name": "PaddleOCR PP-OCRv5 行级 bbox + 几何解析",
                 "params": {"model": "PP-OCRv5"}},
        "gates": {
            "G1": "pass" if not missing else f"fail(缺年 {missing[:5]})",
            "G2": "pass" if not bad_years else f"fail(段年不连续 {len(bad_years)})",
            "G3": "pass" if not bad_month and not d15 else
                  f"fail(月 {len(bad_month)} / D15 {len(d15)})",
            "G4": "run pytest tests/test_official_shilang.py",
            "G5": "见 docs/侍郎表接入报告.md（核验页 954/800/760 + 抽检指南）",
            "G6": g6,
        },
        "evidence": ["docs/侍郎表几何解析报告.md", "docs/侍郎表接入报告.md",
                     "_scratch/shilang/verify/"],
        "tenure_assembly": {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pipeline": doc["meta"]["pipeline"],
            "output": "official_shilang.json",
            "stats": doc["meta"]["stats"],
            "status": "v1-g6-pass" if g6 == "pass" else "review",
            "note": "v1：CBDB 对齐 v1；band 警报页（103 页）条目 pending 灰显，"
                    "校对台逐页清除；954/800/760 已原书核验修正",
        },
    }
    (DATA / "vol1_shilang_manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    doc = export_shilang()
    refresh_manifest(doc)
    s = doc["meta"]["stats"]
    print(f"侍郎任职段 {s['tenures']}（{s['persons']} 实体 / {s['display_persons']} 姓名，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("衙署:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"页码起 {s['with_start_page']}，离任原因 {s['with_leave']}，署理 {s['shu_li']}，"
          f"同名分代 {s['split_entities']}，gap 合并 {s['gap_merged_tenures']} 段")
    print(f"待原书核验段 {s['pending_book_check']}（band 警报页灰显）")
    print(f"office_status: {s['office_status_dist']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
    _r = audit()
    print("audit:", _r)
