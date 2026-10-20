# -*- coding: utf-8 -*-
"""正式版数据管线 v3：从「张德信年表册1 重解析条目」重建内阁任职段。

与前两版的区别（2026-10-17 数据重建）：
  * 输入 `vol1_entries.json` 是**重解析**后的逐年名单（人-年 1,036），
    修复了旧 `parse_neige.py` 丢弃“无注文人名行”的 bug；
  * 人名已按正字归一（含 CBDB 用字差异，如 楊士奇↔楊寓、金幼孜↔金善）；
  * `vol1_person_cbdb.json` 修复了旧 cbdb_id 错挂（楊士奇/楊溥/曹鼐/張孚敬/方逢年等）；
  * D15 断限：1644 年三月之后的南明任命（高弘圖/王應熊/史可法/馬士英等）一律剔除；
  * 皇帝行/画布起点由前端定在 1368（洪武元年），内阁 1402 年始设，之前留空。

三条纪律不变：NULL≠0（月未载 → None）、不臆造、段可溯源（注文原文 + CBDB）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA = Path(__file__).resolve().parent / "data"

CUT_Y, CUT_M = 1644, 3
SHILU_SHOW = 8

MONTHS = {"正": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
MONTH_RE = re.compile(r"(閏)?(正|十[一二]|[一二三四五六七八九十])(?:月|[、，])")
ENTER_VERBS = ("入", "任", "起復", "起", "召", "入直", "入閣", "入朝", "還朝",
               "視事", "至京", "復官")
LEAVE_VERBS = ("罷", "卒", "致仕", "削籍", "下獄", "被執", "戍", "謫", "丁憂",
               "丁父憂", "丁母憂", "憂去", "乞歸", "乞休", "養病", "免", "回籍",
               "為民", "降", "死於難", "歿於", "正法", "自盡", "殉難", "棄市",
               "致仕歸", "革職", "奪官", "謫戍", "奔喪", "守制")
LEAVE_LABEL = {
    "卒": "卒于任", "致仕": "致仕", "罷": "罷免", "下獄": "下獄", "削籍": "削籍",
    "被執": "被執", "戍": "謫戍", "謫": "謫", "丁憂": "丁憂", "丁父憂": "丁父憂",
    "丁母憂": "丁母憂", "憂去": "憂去", "乞歸": "乞歸", "乞休": "乞休",
    "養病": "養病", "免": "免職", "回籍": "回籍", "為民": "為民", "降": "降職",
    "死於難": "死於難", "歿於": "卒于任", "殉難": "殉難", "自盡": "自盡",
    "正法": "正法", "棄市": "棄市",
}
CROSS_YEAR = re.compile(
    r"(洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎)"
    r"[元一二三四五六七八九十廿卅零]{1,6}年"
)


# ---------------- 注文解析 ----------------

def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


def _month_of(chunk: str) -> int | None:
    m = MONTH_RE.search(chunk)
    return MONTHS.get(m.group(2)) if m else None


def _cross_year(chunk: str) -> bool:
    """跨年引用（如「正統元年十、丙寅、四，卒」）不算本年的离任事件。"""
    return bool(CROSS_YEAR.search(chunk)
                or re.search(r"[一二三四五六七八九十廿卅]{1,3}年[正一二三四五六七八九十]{0,3}[、，]",
                             chunk))


def _first_month(note: str) -> int | None:
    for c in _chunks(note):
        m = _month_of(c)
        if m:
            return m
    return None


def _start_month(note: str) -> tuple[int | None, bool]:
    """（起月, 是否来自明确入职事件）。无入职事件退回本年首个纪月，标记 False。"""
    for c in _chunks(note):
        if _cross_year(c):
            continue
        if any(v in c for v in ENTER_VERBS):
            m = _month_of(c)
            if m:
                return m, True
    return _first_month(note), False


def _leave(note: str) -> tuple[int | None, str]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        if "南京" in c and ("改" in c or "調" in c):
            return _month_of(c), "改南京"
        for v in LEAVE_VERBS:
            if v in c:
                return _month_of(c), LEAVE_LABEL.get(v, v)
    return None, "未載"


# ---------------- 任职段 ----------------

def load_entries() -> list[dict]:
    path = DATA / "vol1_entries.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_person_cbdb() -> dict:
    path = DATA / "vol1_person_cbdb.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def build_cabinet_tenures() -> list[dict]:
    entries = [e for e in load_entries() if e["year"] <= CUT_Y]
    mapping = load_person_cbdb()

    by_person: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_person[e["person"]].append(e)

    tenures: list[dict] = []
    for person, rows in sorted(by_person.items()):
        rows.sort(key=lambda e: e["year"])
        # 防御性去重：人名归一后偶见同日重复（实测 1402 解縉、1441 曹鼐）
        dedup: list[dict] = []
        for e in rows:
            if dedup and dedup[-1]["year"] == e["year"]:
                if e["note"] and e["note"] not in dedup[-1]["note"]:
                    dedup[-1]["note"] = (dedup[-1]["note"] + " " + e["note"]).strip()
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

        for seg in segs:
            sy, ey = seg[0], seg[-1]
            s_note, e_note = note_of.get(sy, ""), note_of.get(ey, "")
            sm, sm_event = _start_month(s_note)
            em, leave = _leave(e_note)

            # D15：1644 年三月之后的南明任命一律剔除（高弘圖/王應熊等）
            eff_sm = sm or _first_month(s_note)
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
            conf = 0.5
            has_enter = sm_event
            has_leave = leave != "未載"
            if has_enter and has_leave:
                conf = 0.8
            elif has_enter or has_leave:
                conf = 0.7
            elif sm or len(seg) >= 2:
                conf = 0.6
            if conflict:
                conf = min(conf, 0.5)

            m = mapping.get(person, {})
            tenures.append({
                "person": person,
                "cbdb_id": m.get("cbdb_id"),
                "cbdb_name": m.get("cbdb_name"),
                "office": "內閣",
                "tenure_type": "实授",
                "start_year": sy,
                "start_month": sm,
                "end_year": ey,
                "end_month": em,
                "month_conflict": conflict,
                "end_clamped": clamped,
                "confidence": conf,
                "leave": leave,
                "note": s_note.strip(),
                "years": seg,
            })
    return tenures


def build_shilu(tenures: list[dict]) -> dict:
    path = DATA / "sinica_all.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    windows: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for t in tenures:
        windows[t["person"]].append((t["start_year"] - 1, t["end_year"] + 1))

    out: dict[str, dict] = {}
    for person, wins in windows.items():
        sel, seen = [], set()
        for h in raw.get(person, []):
            y = h.get("year")
            if y is None or not any(lo <= y <= hi for lo, hi in wins):
                continue
            key = (h.get("source"), h.get("content"))
            if key in seen:
                continue
            seen.add(key)
            sel.append({
                "year": y,
                "era": h.get("era"),
                "era_year": h.get("era_year"),
                "month": h.get("month"),
                "leap": bool(h.get("leap")),
                "source": h.get("source", ""),
                "content": h.get("content", ""),
            })
        sel.sort(key=lambda x: (x["year"], x["month"] or 0))
        if sel:
            out[person] = {"count": len(sel), "hits": sel[:SHILU_SHOW]}
    return out


def export_official(out_path: Path | None = None) -> dict:
    tenures = build_cabinet_tenures()
    shilu = build_shilu(tenures)
    doc = {
        "meta": {
            "dataset": "mingoff-cabinet",
            "version": 3,
            "canvas_from": 1368,
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "source": "张德信《明代职官年表》册1·內閣大臣年表（MinerU OCR；"
                      "缺块以原书 PDF 页补录）；人物对齐 CBDB（cbdb_20261010）；"
                      "《明實錄》命中据中研院检索",
            "pipeline": "mingoff.official (v3: 表格重解析 + CBDB 修复 + D15 南明过滤)",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": {
                "tenures": len(tenures),
                "persons": len({t["person"] for t in tenures}),
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "with_start_month": sum(1 for t in tenures if t["start_month"]),
                "with_end_month": sum(1 for t in tenures if t["end_month"]),
                "cbdb_aligned": sum(1 for t in tenures if t["cbdb_id"]),
                "with_leave": sum(1 for t in tenures if t["leave"] != "未載"),
                "shilu_persons": len(shilu),
                "shilu_hits": sum(v["count"] for v in shilu.values()),
                "person_years": sum(len(t["years"]) for t in tenures),
            },
        },
        "tenures": tenures,
        "shilu": shilu,
    }
    if out_path is None:
        out_path = DATA / "official_cabinet.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


if __name__ == "__main__":
    doc = export_official()
    s = doc["meta"]["stats"]
    print(f"内阁任职段 {s['tenures']}（{s['persons']} 人，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"CBDB 对齐 {s['cbdb_aligned']}，离任原因 {s['with_leave']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
