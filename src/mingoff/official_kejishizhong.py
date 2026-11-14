# -*- coding: utf-8 -*-
"""六科都給事中年表任职段组装：vol2_kejishizhong_entries.json → official_kejishizhong.json。

official_jingqing.py 同构适配（三条纪律不变：NULL≠0、不臆造、段可溯源）：

  * 分组键 = (person_id, office)：六科（吏/戶/禮/兵/刑/工科）各独立成段，科不合并；
  * 入场动词沿京卿机件（X遷/X署/X改 收尾 + 任/起/掌…）；六科注文「署兵給遷」
    「遷吏都給」即由 X遷/X 收尾机件覆盖；
  * 离场动词在京卿集上增补「閑住/閒住」（科道常见处分，趙興邦 1626 实例）；
  * book-patch：keji_repair.apply_keji_repair（1618 补 3 条 + 1638 补配 4 注）组装前应用；
  * D-01 同名分代 / D15 断限（1644.3） / 1–2 年 gap 合并：沿京卿；
  * 页级溯源：year → book_page 由 content_list 页脚实测（253/254 页捕获；
    线性式 1268+(年−1393) 于 1393–1636 逐页精确，1638–1643 因原书缺 1637 页
    整体 −1，1644=1518）；content_list 缺失时退回 null（不臆造）；
  * office_status：label-column / row-order / mixed，按该年原书页有无六科标签列实测
    （书为奇偶页交替：跨年段天然 mixed，同京卿）；
  * 缺年白名单：6 空框年 + 1637 原书缺页；其余缺年 = audit blocker。
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
from mingoff.keji_repair import (BOOK_ADD_1618, BOOK_GAP_YEARS, BOOK_PAGE_MAP,
                                 BOOK_PATCH_1638, apply_keji_repair)
from mingoff.match_cbdb import S2T
from mingoff.ocr_jingqing import parse_tables, row_year
from mingoff.ocr_kejishizhong import MD, OFFICES, label_of, split_year_pages_keji
from mingoff.official import (CUT_M, CUT_Y, _cross_year, _month_leap,
                              build_shilu, precedes_office_name)
from mingoff.official_buyuan import (CONF_DOWN, infer_yield_ends,
                                     merge_gap_segments)
from mingoff.official_jingqing import (LEAVE_LABEL_JQ, LEAVE_QIAN,
                                       LEAVE_VERBS_JQ, MAX_SPAN, _chunks,
                                       _start_month, split_identities)

DATA = Path(__file__).resolve().parent / "data"
ROOT = DATA.parents[2]
CL = [ROOT / "_scratch" / "mineru_nianbiao" / "out" / f"vol2_kejishizhong_{p}.content_list.json"
      for p in ("a", "b")]

# 空框年白名单（11 年，史实同为缺官/无考，两种 OCR 表现）：
#   页级缺表 6：1394/1396/1398/1400/1420/1422（1394 实拍验证，MinerU 无表产出）
#   页在而全空 5：1395/1399/1419/1421/1423（md 表六科全空格；1395=·1270· 实拍验证）
EMPTY_FRAME_YEARS = {1394, 1395, 1396, 1398, 1399, 1400,
                     1419, 1420, 1421, 1422, 1423}
BOOK_GAP_YEAR_SET = set(BOOK_GAP_YEARS)
ALLOWED_MISSING_YEARS = EMPTY_FRAME_YEARS | BOOK_GAP_YEAR_SET

# CBDB 映射（scripts/match_official_cbdb.py 产出；缺失 = 未对齐，宁空勿误挂）
CBDB_MAP_FILES = ("vol2_kejishizhong_person_cbdb_v1.json",)


def load_kejishizhong_cbdb() -> dict:
    for v in CBDB_MAP_FILES:
        p = DATA / v
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}

# 六科离场动词 = 京卿集 + 閑住（含「閒住」异体）
LEAVE_VERBS_KEJ = LEAVE_VERBS_JQ + ("閑住", "閒住")
LEAVE_LABEL_KEJ = {**LEAVE_LABEL_JQ, "閑住": "閑住", "閒住": "閑住"}


def _leave_kej(note: str) -> tuple[int | None, bool, str]:
    """六科版离场判定：动词集增补閑住，其余沿京卿（遷/改/調 带宾语 → 遷除/改除/調除）。"""
    for c in _chunks(note):
        if _cross_year(c):
            continue
        label = None
        for v in LEAVE_VERBS_KEJ:
            if v in c:
                label = LEAVE_LABEL_KEJ.get(v, v)
                break
        if label is None:
            m = LEAVE_QIAN.search(c)
            if m:
                if precedes_office_name(c, m.start()):
                    label = None    # 「吏左給遷戶都」类完整句式=到任
                else:
                    label = {"遷": "遷除", "改": "改除", "調": "調除", "還": "還除",
                             "迁": "遷除", "调": "調除", "还": "還除"}[m.group()[0]]
        if label:
            if label in ("下獄", "下狱") and re.search(r"宥|釋|释|復職|復官|赦", c):
                continue          # 下狱后获释复职——非离任（沿京卿 2026-11-12 轮）
            return (*_month_leap(c), label)
    return None, False, "未載"


# ---------------- 页级溯源（content_list 页脚实测） ----------------

_FOOT_RE = re.compile(r"^(1[2-5]\d{2})$")


def _formula_page(year: int) -> int:
    return 1268 + (year - 1393)


def build_page_map_keji() -> tuple[dict[int, int], dict]:
    """md 表 ↔ content_list 表块按序对应（46 处双年 md 表 = 相邻两物理页两块），
    页脚裸数字文本块为印刷页码。返回 ({year: book_page}, 验证记录)。

    验证锚点（2026-11-07 原书实拍）：1393→1268 / 1636→1511 / 1638→1512 / 1644→1518。
    content_list 缺失（_scratch 被清）→ ({}, {status: missing})，页码 null 不臆造。
    """
    ver: dict = {"method": "content_list 页脚实测（md 表按序对应表块，双年 md 表占两块）"}
    if not all(p.is_file() for p in CL):
        ver["status"] = "missing"
        ver["detail"] = "content_list 不存在（_scratch 清理后未重建），页码退回 null"
        return {}, ver
    tables = [t for p in MD for t in parse_tables(p.read_text(encoding="utf-8"))]
    blocks = [json.loads(p.read_text(encoding="utf-8")) for p in CL]
    # ⚠ 两切片的 page_idx 各自 0 基：页脚必须按切片归属查，合并 dict 会被 b 覆盖 a
    footers: list[dict[int, int]] = [{} for _ in blocks]
    tp: list[int] = []
    block_slice: list[int] = []
    for si, cl in enumerate(blocks):
        for blk in cl:
            if blk.get("type") == "table":
                tp.append(blk.get("page_idx", -1))
                block_slice.append(si)
                continue
            m = _FOOT_RE.match((blk.get("text") or "").strip())
            if m:
                pi = blk.get("page_idx")
                footers[si][pi] = max(footers[si].get(pi, 0), int(m.group(1)))
    year2page: dict[int, int] = {}
    j = 0
    for tb in tables:
        ys = []
        for r in tb:
            yy = row_year(r)
            if yy:
                ys.append(yy)
        seen = sorted({y for y in ys if y is not None and 1300 <= y <= 1650})
        n_pages = max(1, len(seen))
        prs = []
        for _ in range(n_pages):
            if j < len(tp):
                prs.append(footers[block_slice[j]].get(tp[j]))
                j += 1
            else:
                prs.append(None)
        for y, pr in zip(seen, prs):
            if y in year2page:
                # 同年出现于多表（1644 正页 1518 + 弘光页年份头被 OCR 误拷成崇禎十七年）：
                # 保留首个（按书序=正页），冲突留档
                if year2page[y] != pr:
                    ver.setdefault("year_page_conflicts", []).append(
                        {"year": y, "pages": [year2page[y], pr], "kept": year2page[y]})
            else:
                year2page[y] = pr
    ver["status"] = "ok"
    ver["tables_md"] = len(tables)
    ver["table_blocks_content_list"] = len(tp)
    ver["blocks_consumed"] = j
    ver["footers_captured"] = f"{sum(len(f) for f in footers)}/{len(tp) + 1}"
    deviations = sorted((y, pr, _formula_page(y)) for y, pr in year2page.items()
                        if pr is not None and pr != _formula_page(y))
    ver["formula_deviations"] = deviations
    ver["formula_note"] = ("线性式 1393–1636 逐页精确；1638–1643 因原书缺 1637 页整体 −1；"
                           if all(d[2] - d[1] in (0, 1) for d in deviations) else "偏差异常，须核查")
    ver["anchors"] = {"1393": year2page.get(1393), "1636": year2page.get(1636),
                      "1638": year2page.get(1638), "1644": year2page.get(1644)}
    ver["anchors_expect"] = {"1393": 1268, "1636": 1511, "1638": 1512, "1644": 1518}
    ver["anchors_ok"] = all(year2page.get(int(y)) == e for y, e in ver["anchors_expect"].items())
    # book-patch 年的实测页码补入（1618 页在而 MinerU 丢表；页脚 ·1493· 原书可见）
    for y, p in BOOK_PAGE_MAP.items():
        year2page.setdefault(y, p)
    ver["book_patch_pages"] = dict(BOOK_PAGE_MAP)
    return year2page, ver


def build_year_frames() -> dict[int, str]:
    """{year: "label-column"|"row-order"}：该年原书页有无六科标签列（重走切页判 labelled）。"""
    try:
        pages, _dropped = split_year_pages_keji(
            [parse_tables(p.read_text(encoding="utf-8")) for p in MD])
    except OSError:
        return {}
    frames: dict[int, str] = {}
    for page in pages:
        y = page["years"][0]
        labelled = any(label_of(r[0].strip() if r else "") for r in page["rows"])
        frames.setdefault(y, "label-column" if labelled else "row-order")
    return frames


# ---------------- D-01 同名分代（沿京卿 split_identities） ----------------

# ---------------- 组装 ----------------

def load_keji() -> list[dict]:
    return json.loads(
        (DATA / "vol2_kejishizhong_entries.json").read_text(encoding="utf-8"))["entries"]


def load_keji_repaired(report: dict | None = None) -> list[dict]:
    return apply_glue_repair(apply_keji_repair(load_keji(), report),
                             "kejishizhong", report)


def _office_basis_kej(seg_years: list[int], frames: dict[int, str]) -> str:
    kinds = {frames.get(y, "row-order") for y in seg_years}
    if kinds == {"label-column"}:
        return "label-column"
    if kinds == {"row-order"}:
        return "row-order"
    return "mixed"


def build_kejishizhong_tenures() -> list[dict]:
    entries = [e for e in load_keji_repaired() if e["year"] <= CUT_Y]
    identities = split_identities(entries)
    pid_of: dict[tuple[str, int], str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            for y in ys:
                pid_of[(name, y)] = pid
    label_of_pid: dict[str, str] = {}
    for name, ents in identities.items():
        for pid, ys in ents:
            label_of_pid[pid] = f"{name}（{min(ys)}–{max(ys)}）" if pid != name else name

    page_map, _page_ver = build_page_map_keji()
    frames = build_year_frames()
    mapping = load_kejishizhong_cbdb()
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
            em, em_leap, leave = _leave_kej(e_note)

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
            basis = _office_basis_kej(seg, frames)
            if basis == "row-order":
                conf = min(conf, 0.6)
            elif basis == "mixed":
                conf = min(conf, 0.7)

            ttype = "署理" if "署" in s_note else "实授"
            m = mapping.get(pid, {})
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": label_of_pid[pid],
                "cbdb_id": m.get("cbdb_id"),       # 无映射保持 NULL（宁空勿误挂）
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


# ---------------- 审计（G2/G3/G6-六科版） ----------------

def audit() -> dict:
    report: dict = {}
    entries = [e for e in load_keji_repaired(report) if e["year"] <= CUT_Y]
    tenures = build_kejishizhong_tenures()
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
        blockers.append(f"同科段重叠 {len(overlap)}: {overlap[:5]}")
    # 实体跨度 >80 年（规范 3.6-11）
    span_by_id: dict[str, tuple[int, int]] = {}
    for t in tenures:
        lo, hi = span_by_id.get(t["person_id"], (t["start_year"], t["end_year"]))
        span_by_id[t["person_id"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    too_long = [p for p, (lo, hi) in span_by_id.items() if hi - lo > MAX_SPAN]
    if too_long:
        blockers.append(f"实体跨度>80年 {len(too_long)}: {too_long[:5]}")
    # 科集合
    bad_office = sorted({t["office"] for t in tenures} - set(OFFICES))
    if bad_office:
        blockers.append(f"科越界 {bad_office}")
    # 缺年白名单：6 空框 + 1637 原书缺页；段覆盖（含 gap 合并补进的年）之外不得有未归因缺年
    covered: set[int] = set()
    for t in tenures:
        covered |= set(t["years"])
    missing = [y for y in range(1393, CUT_Y + 1) if y not in covered]
    unattributed = [y for y in missing if y not in ALLOWED_MISSING_YEARS]
    if unattributed:
        blockers.append(f"未归因缺年 {unattributed}")
    # 页级溯源覆盖
    no_page = sum(1 for t in tenures if t.get("start_book_page") is None)
    if no_page:
        warnings.append(f"无页码段 {no_page}（content_list 页脚索引缺失时出现）")
    # 条目-段对账：段人-年（扣除 gap 合并补进的年份）应 ≤ 条目数
    person_years = sum(len(t["years"]) for t in tenures)
    gap_years = sum(len(t.get("gap_years") or []) for t in tenures)
    if person_years - gap_years > len(entries):
        blockers.append(f"人-年 {person_years - gap_years} 超过条目 {len(entries)}")
    # CBDB 门（映射存在时，镜像 audit_buyuan §6）：生卒 vs 段跨度硬冲突 / 同一 id 多正名
    cbdb_map = load_kejishizhong_cbdb()
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
            "missing_years": missing,
            "book_patch": report.get("book_patch"),
            "no_page_years": no_page_years}


# ---------------- 导出 ----------------

def export_kejishizhong(out_path: Path | None = None) -> dict:
    tenures = build_kejishizhong_tenures()
    shilu = build_shilu(tenures)
    entry_years = {e["year"] for e in load_keji() if e["year"] <= CUT_Y}
    missing_years = sorted(set(range(1393, CUT_Y + 1)) - entry_years)
    doc = {
        "meta": {
            "dataset": "mingoff-kejishizhong",
            "version": 1,
            "canvas_from": 1368,
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "source": "张德信《明代职官年表》册2·六科都給事中年表 正文 1267–1520"
                      "（PDF 5–258，offset −1262 实测；MinerU OCR，解析 ocr_kejishizhong.py）；"
                      "页级溯源用 content_list 页脚实测（build_page_map_keji）；CBDB 对齐 v1"
                      "（match_official_cbdb.py 评分器，宁空勿误挂）",
            "pipeline": "mingoff.official_kejishizhong (v1: (person_id,office) 分组 + "
                        "遷/改/調定向判定 + 閑住离场 + book-patch（1618 补 3 条/1638 补 4 注）"
                        "+ D-01 同名分代 + gap 合并 + D15 + CBDB 对齐)",
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
                "gap_after_tenures": sum(1 for t in tenures if t.get("gap_after")),
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "missing_years": missing_years,
                "empty_frame_years": sorted(EMPTY_FRAME_YEARS),
                "book_gap_years": sorted(BOOK_GAP_YEAR_SET),
                "book_patch_added": len(BOOK_ADD_1618),
                "book_patch_notes": len(BOOK_PATCH_1638),
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
        out_path = DATA / "official_kejishizhong.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def refresh_manifest(doc: dict) -> None:
    """manifest 由当前数据实测生成（规范 3.7：禁止手写统计/Gates）。"""
    entry_years = {e["year"] for e in load_keji() if e["year"] <= CUT_Y}
    missing = sorted(set(range(1393, CUT_Y + 1)) - entry_years)
    unattributed = [y for y in missing if y not in ALLOWED_MISSING_YEARS]
    tenures = doc["tenures"]
    bad_years = [t for t in tenures
                 if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    bad_month = [t for t in tenures if any(
        mm is not None and not 1 <= mm <= 12 for mm in (t["start_month"], t["end_month"]))]
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > CUT_M)]
    _page_map, page_ver = build_page_map_keji()
    try:
        _r = audit()
        g6 = "pass" if not _r["blockers"] else f"fail({_r['blockers']})"
    except Exception as exc:  # pragma: no cover
        g6 = f"not-run({exc})"
    m = {
        "source": "张德信《明代职官年表》册2（扫描 PDF）",
        "pdf_pages": 258, "offset": -1262,
        "table": "六科都給事中年表", "book_pages": [1267, 1520], "pdf_range": [5, 258],
        "slices": [{"file": "vol2_kejishizhong_a.pdf", "pages": 200},
                   {"file": "vol2_kejishizhong_b.pdf", "pages": 54}],
        "tool": {"name": "MinerU", "params": {"model": "vlm", "ocr": True,
                                              "table": True, "language": "ch"}},
        "batch_id": "e2bc7d5b-3a0c-4e01-b4e9-35dc683f97b4",
        "page_index": {
            "method": "content_list 页脚实测（md 表按序对应表块，双年 md 表占两块）",
            "content_list": [str(p.relative_to(ROOT)) for p in CL],
            "verification": page_ver,
        },
        "gates": {
            "G1": "pass" if not unattributed else
                  f"fail(未归因缺年 {unattributed}；白名单外缺年即 blocker)",
            "G2": "pass" if not bad_years else f"fail(段年不连续 {len(bad_years)})",
            "G3": "pass" if not bad_month and not d15 else
                  f"fail(月 {len(bad_month)} / D15 {len(d15)})",
            "G4": "run pytest tests/test_official_kejishizhong.py",
            "G5": "见 docs/六科年表报告.md 抽检（转录对照表 + 页映射锚点）",
            "G6": g6,
        },
        "evidence": ["docs/六科年表报告.md", "docs/evidence/keji/"],
        "tenure_assembly": {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pipeline": doc["meta"]["pipeline"],
            "output": "official_kejishizhong.json",
            "stats": doc["meta"]["stats"],
            "status": "v1-g6-pass" if g6 == "pass" else "review",
            "note": "v1：CBDB 对齐 v1 已做（match_official_cbdb.py，宁空勿误挂）；"
                    "人名未过正字表归一；"
                    "无标签年段 office_status=row-order、置信度封顶 0.6；"
                    "1618=MinerU 丢表已 book-patch 补 3 条；1637=原书缺页不补条目，"
                    "段跨 1637 由 gap 逻辑显式记录",
        },
    }
    (DATA / "vol2_kejishizhong_manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    doc = export_kejishizhong()
    refresh_manifest(doc)
    s = doc["meta"]["stats"]
    print(f"六科任职段 {s['tenures']}（{s['persons']} 实体 / {s['display_persons']} 姓名，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("科:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"页码起 {s['with_start_page']}，离任原因 {s['with_leave']}，署理 {s['shu_li']}，"
          f"同名分代 {s['split_entities']}，gap 合并 {s['gap_merged_tenures']} 段"
          f"（{s['gap_years_total']} 年），gap_after {s['gap_after_tenures']} 段")
    print(f"book-patch：补 {s['book_patch_added']} 条 / 补注 {s['book_patch_notes']} 条；"
          f"缺年 {len(s['missing_years'])}（空框 {len(s['empty_frame_years'])} / "
          f"原书缺页 {s['book_gap_years']}）")
    print(f"office_status: {s['office_status_dist']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
    _r = audit()
    print("audit:", _r)
