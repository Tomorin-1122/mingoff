# -*- coding: utf-8 -*-
"""京卿年表（京師）任职段组装：vol1_jingqing_entries.json → official_jingqing.json。

依据《数据接入规范》2.2/3.3/3.4/3.6 与 D15 断限，official_buyuan.py 同构适配：

  * 分组键 = (person_id, office)：八衙（通政使/大理卿/太常卿/光祿卿/太僕卿/鴻臚卿/
    尚寶卿/順天府府尹）各独立成段，衙署不合并；
  * 入场动词增补：「X遷」收尾（"大理左少遷"=由大理左少卿迁入本任）、
    「X署」收尾（"左都署"=署理入场）、實授、掌；
  * 离场动词增补：「遷X/改X/調X」带宾语（"遷南刑右侍"=迁出本衙 → 遷除/改除/調除）；
  * tenure_type：注文含"署"→ 署理，否则实授；
  * D-01 同名分代：同一显示名跨度 >80 年 → 按 ≥10 年大缺口拆 person_id#k，
    记 same_name_risk；拆不开的留单实体交审计报 blocker；
  * 页级溯源：year → book_page 由 Paddle 逐页年份头索引实测（无 Paddle 产物则 null）；
  * 无标签年/双年页的条目 review 贯通到段（office_status + confidence 封顶）；
  * D15：1644.3 后任命剔除；末段截 1644.3 打 end_clamped。

三条纪律不变：NULL≠0、不臆造、段可溯源。
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

from mingoff.glue_repair import apply_glue_repair
from mingoff.official import CUT_M, CUT_Y, _cross_year, _month_of, build_shilu
from mingoff.match_cbdb import S2T
from mingoff.official_buyuan import CONF_DOWN, merge_gap_segments

DATA = Path(__file__).resolve().parent / "data"
PADDLE_PAGES = DATA.parents[2] / "_scratch" / "paddle_jingqing" / "raw_pages"

# CBDB 映射（scripts/match_official_cbdb.py 产出；缺失 = 未对齐，宁空勿误挂）
CBDB_MAP_FILES = ("vol1_jingqing_person_cbdb_v1.json",)


def load_jingqing_cbdb() -> dict:
    for v in CBDB_MAP_FILES:
        p = DATA / v
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}

# 入场动词（京卿注文形态；"任""掌"沿部院）
ENTER_BASE = ("入", "任", "起復", "起", "召", "視事", "至京", "復官", "復",
              "掌", "陞", "升", "實授")
# 「X遷」收尾 = 由 X 迁入本任（大理左少遷 / 司正遷 / 翰林編修署遷）
ENTER_QIAN = re.compile(r"[一-龥]{1,6}(?:卿|少卿|寺丞|使|尹|丞|郎)?[,，]?遷[,，;；。]?$")
# 「X署」收尾 = 由 X 署理入场（左都署 / 翰林編修署）
ENTER_SHU = re.compile(r"[一-龥]{1,6}署[,，;；。]?$")
# 「X改」收尾 = 由 X 改任本任（光祿卿改 / 大理卿改）
ENTER_GAI = re.compile(r"[一-龥]{1,6}改[,，;；。]?$")
# 「遷X/改X/調X」带宾语 = 迁出本衙
LEAVE_QIAN = re.compile(r"[遷改調][一-龥]")

LEAVE_VERBS_JQ = ("罷", "卒", "致仕", "削籍", "下獄", "被執", "戍", "謫", "丁憂",
                  "丁父憂", "丁母憂", "憂去", "乞歸", "乞休", "養病", "免", "回籍",
                  "為民", "降", "死於難", "死難", "歿於", "正法", "自盡", "殉難",
                  "棄市", "革職", "奪官", "謫戍", "奔喪", "守制")
LEAVE_LABEL_JQ = {"卒": "卒于任", "歿於": "卒于任", "死於難": "死於難",
                  "死難": "死於難", "免": "免職", "降": "降職"}


def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


def _enter_chunk(chunk: str) -> bool:
    if any(v in chunk for v in ENTER_BASE):
        return True
    if ENTER_QIAN.search(chunk):        # "大理左少遷" 收尾 → 迁入
        return True
    if ENTER_SHU.search(chunk):         # "左都署" 收尾 → 署理入场
        return True
    if ENTER_GAI.search(chunk):         # "光祿卿改" 收尾 → 由光祿卿改任本任
        return True
    return False


def _leave_chunk(chunk: str) -> str | None:
    for v in LEAVE_VERBS_JQ:
        if v in chunk:
            return LEAVE_LABEL_JQ.get(v, v)
    m = LEAVE_QIAN.search(chunk)
    if m:
        return {"遷": "遷除", "改": "改除", "調": "調除"}[m.group()[0]]
    return None


def _start_month(note: str) -> tuple[int | None, bool]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        if _enter_chunk(c):
            m = _month_of(c)
            if m:
                return m, True
    for c in _chunks(note):             # 退回本年首个纪月（非事件）
        if _cross_year(c):
            continue
        m = _month_of(c)
        if m:
            return m, False
    return None, False


def _leave(note: str) -> tuple[int | None, str]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        label = _leave_chunk(c)
        if label:
            return _month_of(c), label
    return None, "未載"


# ---------------- 页级溯源 ----------------

_ERA_START: dict[str, int] = {}


def _cn_num(num: str) -> int:
    """元/一/十/十一/三十/廿/廿一/卅一 → 1/1/10/11/30/20/21/31。"""
    if num == "元":
        return 1
    cn = {c: i + 1 for i, c in enumerate("一二三四五六七八九")}
    for ch, tens in (("廿", 20), ("卅", 30)):
        if num.startswith(ch):
            rest = num[1:]
            return tens + (cn[rest] if rest else 0)
    if "十" in num:
        t, _, o = num.partition("十")
        return cn.get(t, 1) * 10 + (cn.get(o, 0) if o else 0)
    return cn[num]


def _era_year(text: str) -> list[int]:
    """页眉形态「隆慶二年戊辰(158)」→ [1568]。必须带干支锚（注文跨年引用无干支）。"""
    if not _ERA_START:
        from mingoff.ocr_jingqing import ERA_SPANS
        _ERA_START.update({era: y0 for era, y0, _y1 in ERA_SPANS})
    out = []
    for m in re.finditer(
            r"(洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎)"
            r"(元|[一二三四五六七八九十廿卅]{1,3})年"
            r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]", text):
        if m.group(1) in _ERA_START:
            y = _ERA_START[m.group(1)] + _cn_num(m.group(2)) - 1
            if 1368 <= y <= 1644:
                out.append(y)
    return out


def build_page_map() -> dict[int, int]:
    """Paddle 逐页结果 → {year: book_page}。缺产物返回 {}。"""
    if not PADDLE_PAGES.is_dir():
        return {}
    page_map: dict[int, int] = {}
    for f in sorted(PADDLE_PAGES.glob("p*.jsonl")):
        pdf_page = int(f.stem[1:])
        try:
            obj = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
        except (json.JSONDecodeError, IndexError):
            continue
        parts: list[str] = []
        for r in obj.get("result", {}).get("ocrResults") or []:
            parts += r.get("prunedResult", {}).get("rec_texts") or []
        text = " ".join(parts)
        found = [int(m.group(1)) for m in re.finditer(r"[（(](1[3-6]\d{2})[)）]", text)]
        found += [y for y in _era_year(text) if y not in found]
        for y in found:
            page_map.setdefault(y, pdf_page - 15)
    return page_map


# ---------------- D-01 同名分代 ----------------

MAX_SPAN = 80   # 规范 3.6-11：同一 person_id 跨度不得超过 80 年
SPLIT_GAP = 10  # 分代切点：≥10 年缺口


def split_identities(entries: list[dict]) -> dict[str, list[tuple[str, set[int]]]]:
    """显示名 → [(person_id, 年集合)]。跨度 ≤80 单实体；否则按大缺口切。"""
    by_name: dict[str, set[int]] = defaultdict(set)
    for e in entries:
        by_name[e["person"]].add(e["year"])
    out: dict[str, list[tuple[str, set[int]]]] = {}
    for name, ys in by_name.items():
        seq = sorted(ys)
        if seq[-1] - seq[0] <= MAX_SPAN:
            out[name] = [(name, set(seq))]
            continue
        cuts = [i for i in range(1, len(seq)) if seq[i] - seq[i - 1] >= SPLIT_GAP]
        if not cuts:
            out[name] = [(name, set(seq))]  # 拆不开 → 审计 blocker
            continue
        groups, prev = [], 0
        for i in cuts:
            groups.append(seq[prev:i])
            prev = i
        groups.append(seq[prev:])
        out[name] = [(f"{name}#{k + 1}", set(g)) for k, g in enumerate(groups)]
    return out


# ---------------- 组装 ----------------

def load_jingqing() -> list[dict]:
    return json.loads((DATA / "vol1_jingqing_entries.json").read_text(encoding="utf-8"))["entries"]


def load_jingqing_repaired(report: dict | None = None) -> list[dict]:
    """OCR 条目 + 格子级粘连修复（glue_repair，正字别名轮）。"""
    return apply_glue_repair(load_jingqing(), "jingqing", report)


def _office_basis(seg_years: list[int], review_of: dict[int, str | None]) -> str:
    """段的官职归属依据：label-column / row-order（整段无标签年行序推）/ dual / mixed。

    年表奇偶页交替：跨年段天然混合有标签年与无标签年 → mixed 是常态。
    """
    flagged = {y for y in seg_years
               if review_of.get(y)
               and ("双年页" in review_of[y] or "无标签年" in review_of[y])}
    if not flagged:
        return "label-column"
    if flagged == set(seg_years):
        kinds = {("dual" if "双年页" in review_of[y] else "row-order") for y in flagged}
        return kinds.pop() if len(kinds) == 1 else "mixed"
    return "mixed"


def build_jingqing_tenures() -> list[dict]:
    entries = [e for e in load_jingqing_repaired() if e["year"] <= CUT_Y]
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
    mapping = load_jingqing_cbdb()
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in entries:
        pid = pid_of[(e["person"], e["year"])]
        by_key[(pid, e["office"])].append(e)

    tenures: list[dict] = []
    for (pid, office), rows in sorted(by_key.items()):
        rows.sort(key=lambda e: e["year"])
        person = rows[0]["person"]
        # 防御性去重：同年多条 → 合并注文
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
            sm, sm_event = _start_month(s_note)
            em, leave = _leave(e_note)

            # D15：1644.3 之后任命剔除
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
            elif basis == "dual":
                conf = min(conf, 0.5)

            ttype = "署理" if "署" in s_note else "实授"
            m = mapping.get(pid, {})
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": label_of[pid],
                "cbdb_id": m.get("cbdb_id"),       # 无映射保持 NULL（宁空勿误挂）
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
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    return merge_gap_segments(tenures)


# ---------------- 审计（G2/G3/G6-京卿版） ----------------

def audit() -> dict:
    entries = [e for e in load_jingqing_repaired() if e["year"] <= CUT_Y]
    tenures = build_jingqing_tenures()
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
    # 同 (person_id, office) 段不得重叠
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
    # 实体跨度 >80 年（规范 3.6-11）
    span80 = [pid for (pid, _off) in by_key
              if "#" not in pid and (min(t["start_year"] for t in by_key[(pid, _off)]),
                                     max(t["end_year"] for t in by_key[(pid, _off)]))]
    id_span: dict[str, int] = {}
    for t in tenures:
        id_span[t["person_id"]] = max(id_span.get(t["person_id"], 0), t["end_year"])
        id_span[t["person_id"]] = min(id_span.get(t["person_id"], 9999), t["start_year"])
    too_long = [p for p, (lo, hi) in [] if True]  # 占位，下面重算
    span_by_id: dict[str, tuple[int, int]] = {}
    for t in tenures:
        lo, hi = span_by_id.get(t["person_id"], (t["start_year"], t["end_year"]))
        span_by_id[t["person_id"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    too_long = [p for p, (lo, hi) in span_by_id.items() if hi - lo > MAX_SPAN]
    if too_long:
        blockers.append(f"实体跨度>80年 {len(too_long)}: {too_long[:5]}")
    # 页级溯源覆盖
    no_page = sum(1 for t in tenures if t.get("start_book_page") is None)
    if no_page:
        warnings.append(f"无页码段 {no_page}（Paddle 页索引缺失时出现）")
    # 条目-段对账：段人-年（扣除 gap 合并补进的年份）应 ≤ 条目数
    person_years = sum(len(t["years"]) for t in tenures)
    gap_years = sum(len(t.get("gap_years") or []) for t in tenures)
    if person_years - gap_years > len(entries):
        blockers.append(f"人-年 {person_years - gap_years} 超过条目 {len(entries)}")
    # CBDB 门（映射存在时，镜像 audit_buyuan §6）：生卒 vs 段跨度硬冲突 / 同一 id 多正名
    cbdb_map = load_jingqing_cbdb()
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
                        # 简繁变体 person_id（吴/吳 等 OCR 前后不一）归一后比对，
                        # 同一人类的两种写法不算「同 id 多正名」
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
                shared = sorted(f"{cid}:{sorted(ps)}" for cid, ps in ids.items()
                                if len(ps) > 1)
                # 同 id 组：若组内人名都能经 CBDB 自身别名表归到该 id（同一人不同名，
                # 如 許觀=黃觀、蘭芳=藺芳），不算冲突；只有真正异人（趙榮/王榮 型）才挂
                if shared:

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

                    shared = {k: v for k, v in shared.items()
                              if not _benign(int(k), set(v))}
                if date_conflicts:
                    blockers.append(f"CBDB 生卒冲突 {len(date_conflicts)}: "
                                    f"{date_conflicts[:5]}")
                if shared:
                    blockers.append(f"同一 CBDB id 多正名 {len(shared)}: {shared[:5]}")
            finally:
                con.close()
        else:
            warnings.append("CBDB 库缺失，跳过生卒冲突/同 id 校验")
    no_page_years = sorted({t["start_year"] for t in tenures
                            if t.get("start_book_page") is None})
    return {"blockers": blockers, "warnings": warnings,
            "tenures": len(tenures), "person_years": person_years,
            "no_page_years": no_page_years}


# ---------------- 导出 ----------------

def export_jingqing(out_path: Path | None = None) -> dict:
    tenures = build_jingqing_tenures()
    shilu = build_shilu(tenures)
    doc = {
        "meta": {
            "dataset": "mingoff-jingqing",
            "version": 1,
            "canvas_from": 1368,
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "source": "张德信《明代职官年表》册1·京卿年表（京師）正文 981–1266"
                      "（PDF 996–1281，MinerU OCR；解析 ocr_jingqing.py v1 试点）；"
                      "页级溯源用 PaddleOCR 逐页年份头索引；CBDB 对齐 v1"
                      "（match_official_cbdb.py 评分器，宁空勿误挂）",
            "pipeline": "mingoff.official_jingqing (v1: (person_id,office) 分组 + "
                        "遷/改/調定向判定 + D-01 同名分代 + gap 合并 + D15 + CBDB 对齐)",
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
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "with_start_month": sum(1 for t in tenures if t["start_month"]),
                "with_end_month": sum(1 for t in tenures if t["end_month"]),
                "with_start_page": sum(1 for t in tenures if t.get("start_book_page")),
                "with_end_page": sum(1 for t in tenures if t.get("end_book_page")),
                "cbdb_aligned": sum(1 for t in tenures if t["cbdb_id"]),
                "with_leave": sum(1 for t in tenures if t["leave"] != "未載"),
                "shu_li": sum(1 for t in tenures if t["tenure_type"] == "署理"),
                "same_name_risk": sum(1 for t in tenures if t.get("same_name_risk")),
                "office_status_dist": dict(Counter(t.get("office_status") for t in tenures)),
                "shilu_persons": len(shilu),
                "shilu_hits": sum(v["count"] for v in shilu.values()),
                "person_years": sum(len(t["years"]) for t in tenures),
            },
        },
        "tenures": tenures,
        "shilu": shilu,
    }
    if out_path is None:
        out_path = DATA / "official_jingqing.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def refresh_manifest(doc: dict) -> None:
    """manifest 由当前数据实测生成（规范 3.7：禁止手写统计/Gates）。"""
    entries = load_jingqing()
    years = sorted({e["year"] for e in entries})
    missing = [y for y in range(1368, CUT_Y + 1) if y not in years]
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
        "table": "京卿年表（京師）", "book_pages": [981, 1266], "pdf_range": [996, 1281],
        "slices": [{"file": "vol1_jingqing_jingshi_a.pdf", "pages": 200},
                   {"file": "vol1_jingqing_jingshi_b.pdf", "pages": 86}],
        "tool": {"name": "MinerU", "params": {"model": "vlm", "ocr": True,
                                              "table": True, "language": "ch"}},
        "gates": {
            "G1": "pass" if not missing else f"fail(缺年 {missing[:5]})",
            "G2": "pass" if not bad_years else f"fail(段年不连续 {len(bad_years)})",
            "G3": "pass" if not bad_month and not d15 else
                  f"fail(月 {len(bad_month)} / D15 {len(d15)})",
            "G4": "run pytest tests/test_official_jingqing.py",
            "G5": "见 docs/京卿年表试点报告.md 抽检（9 锚点）",
            "G6": g6,
        },
        "evidence": ["docs/京卿年表试点报告.md"],
        "tenure_assembly": {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pipeline": doc["meta"]["pipeline"],
            "output": "official_jingqing.json",
            "stats": doc["meta"]["stats"],
            "status": "v1-g6-pass" if g6 == "pass" else "review",
            "note": "v1：CBDB 对齐 v1 已做（match_official_cbdb.py，宁空勿误挂）；"
                    "人名未过正字表归一；"
                    "无标签年段 office_status=row-order、置信度封顶 0.6",
        },
    }
    (DATA / "vol1_jingqing_manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    doc = export_jingqing()
    refresh_manifest(doc)
    s = doc["meta"]["stats"]
    print(f"京卿任职段 {s['tenures']}（{s['persons']} 实体 / {s['display_persons']} 姓名，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("官职:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"页码起 {s['with_start_page']}，离任原因 {s['with_leave']}，署理 {s['shu_li']}，"
          f"同名分代 {s['split_entities']}，gap 合并 {s['gap_merged_tenures']} 段"
          f"（{s['gap_years_total']} 年）")
    print(f"office_status: {s['office_status_dist']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
    _r = audit()
    print("audit:", _r)
