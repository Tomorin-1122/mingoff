# -*- coding: utf-8 -*-
"""部院大臣年表（京師）任职段组装：vol1_buyuan_entries.json → official_buyuan.json。

依据《数据接入规范》2.2/3.3/3.4 与 D15 断限，在 official.py（内阁 v3）基础上做部院适配：

  * 分组键 = (person, office)：部院一人可历多部，各部独立成段；
  * 入场动词增补：遷（641 次，"司農卿遷"=由司农卿迁入本任）、掌（掌部/掌院）、
    改的定向判定（"工尚改"=由工部改任本任→入场；"改兵尚"=改除兵部→离场）；
  * 离任动词增补：出（"出江西參政"=外放）；
  * tenure_type：注文含"署"（署部事/署掌）→ 署理，否则实授；
  * 同名不同人（張鳳/胡松/李敏/王佐/顧佐/吴山，见 _scratch/buyuan_merges.json）：
    连续段自然切分 + `same_name_risk` 标记，不合并实体；
  * D15：1644.3 后任命剔除；末段截 1644.3 打 end_clamped。

三条纪律不变：NULL≠0、不臆造、段可溯源。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mingoff.official import (CUT_M, CUT_Y, SHILU_SHOW, _cross_year, _month_of,
                              build_shilu)

DATA = Path(__file__).resolve().parent / "data"

# 入场动词（部院注文形态）
ENTER_BASE = ("入", "任", "起復", "起", "召", "視事", "至京", "復官", "復",
              "掌", "陞", "升")
# 迁入："司農卿遷""兵侍遷"（原官在遷前）→ 入场
ENTER_QIAN = re.compile(r"[一-龥]{1,6}(?:尚書|尚书|侍郎|卿|御史|使|監|丞|郎中|主事|同知|僉事)?遷[,，;；。]?$")
# "X改"（原官在改前，改后无宾语）→ 入场；"改X"（改后有官名）→ 离场
ENTER_GAI = re.compile(r"[一-龥]{1,6}改[,，;；。]?$")
LEAVE_GAI = re.compile(r"改[一-龥]")

LEAVE_EXTRA = {"出": "出為外任", "調": "調除", "改": "改除", "遷": "遷除"}


def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


def _enter_chunk(chunk: str) -> bool:
    if any(v in chunk for v in ENTER_BASE):
        return True
    if ENTER_QIAN.search(chunk):      # "司農卿遷" 收尾 → 迁入
        return True
    if ENTER_GAI.search(chunk) and not LEAVE_GAI.search(chunk):
        return True                   # "工尚改" 收尾 → 由工部改任本任
    return False


def _leave_chunk(chunk: str) -> str | None:
    """返回离任标签；无离任返回 None。"""
    if "南京" in chunk and ("改" in chunk or "調" in chunk):
        return "改南京"
    for v in ("罷", "卒", "致仕", "削籍", "下獄", "被執", "戍", "謫", "丁憂",
              "丁父憂", "丁母憂", "憂去", "乞歸", "乞休", "養病", "免", "回籍",
              "為民", "降", "死於難", "死難", "歿於", "正法", "自盡", "殉難", "棄市",
              "革職", "奪官", "謫戍", "奔喪", "守制", "奪贈謚"):
        if v in chunk:
            return {"卒": "卒于任", "歿於": "卒于任", "死於難": "死於難", "死難": "死於難"}.get(v, v)
    if re.search(r"[一-龥]出[,，;；。]?|[一二三四五六七八九十]+[、，][^,，]*出[一-龥]", chunk):
        return "出為外任"
    if LEAVE_GAI.search(chunk):       # "改兵尚" → 改除
        return "改除"
    return None


def _start_month(note: str) -> tuple[int | None, bool]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        if _enter_chunk(c):
            m = _month_of(c)
            if m:
                return m, True
    # 退回本年首个纪月（不标记为事件）
    for c in _chunks(note):
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


SAME_NAME_GROUPS = {"張鳳", "胡松", "李敏", "王佐", "顧佐", "吴山"}
GAP_SPLIT_YEARS = 15  # 同名组内间隔 ≥15 年视为不同实体


def load_buyuan() -> list[dict]:
    return json.loads((DATA / "vol1_buyuan_entries.json").read_text(encoding="utf-8"))


def load_buyuan_cbdb() -> dict:
    p = DATA / "vol1_buyuan_person_cbdb.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def build_buyuan_tenures() -> list[dict]:
    entries = [e for e in load_buyuan() if e["year"] <= CUT_Y]
    mapping = load_buyuan_cbdb()

    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    skipped_no_office = []
    for e in entries:
        if not e["office"]:
            # NULL 铁律：office 未归部不得造假值；条目留待回原书核对
            skipped_no_office.append(e)
            continue
        by_key[(e["person"], e["office"])].append(e)

    tenures: list[dict] = []
    for (person, office), rows in sorted(by_key.items()):
        rows.sort(key=lambda e: e["year"])
        # 防御性去重：同年多条 → 合并注文（多事件年合法，但同段键下同年只留一条）
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
        flag_of = {e["year"]: e.get("flag") or "" for e in rows}
        segs, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                segs.append(cur)
                cur = [y]
        segs.append(cur)

        # 同名不同人风险：人名级标记（同名组跨部跨代，按部内分段无法表达）
        same_name_risk = person in SAME_NAME_GROUPS
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
            has_enter = sm_event
            has_leave = leave != "未載"
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

            m = mapping.get(person, {})
            ttype = "署理" if ("署" in s_note or "署" in flag_of.get(sy, "")) else "实授"
            tenures.append({
                "person": person,
                "cbdb_id": m.get("cbdb_id"),
                "cbdb_name": m.get("cbdb_name"),
                "office": office,
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
                "years": seg,
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    if skipped_no_office:
        _append_review(skipped_no_office)
    return tenures


def _append_review(rows: list[dict]) -> None:
    """NULL-office 条目并入待校清单（office 未知 → 回原书核对后再入段）。"""
    p = DATA / "vol1_buyuan_review.json"
    rv = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
    have = {(r.get("year"), r.get("raw")) for r in rv}
    for e in rows:
        key = (e["year"], e.get("raw_person") or e["person"])
        if key in have:
            continue
        rv.append({"year": e["year"], "person": e["person"], "office": None,
                   "issue": "no-office", "raw": e.get("raw_person") or e["person"],
                   "note": e.get("note", "")[:60]})
    p.write_text(json.dumps(rv, ensure_ascii=False, indent=1), encoding="utf-8")


def export_buyuan(out_path: Path | None = None) -> dict:
    tenures = build_buyuan_tenures()
    shilu = build_shilu(tenures)
    doc = {
        "meta": {
            "dataset": "mingoff-buyuan",
            "version": 1,
            "canvas_from": 1368,
            "source": "张德信《明代职官年表》册1·部院大臣年表（京師）（MinerU OCR）；"
                      "人名校验：CBDB 20261010 + 中研院明實錄 + 弇山堂别集/國榷（识典古籍）；"
                      "《明實錄》命中据中研院检索",
            "pipeline": "mingoff.official_buyuan (v1: (person,office) 分组 + 遷/改/署 适配 + D15)",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stats": {
                "tenures": len(tenures),
                "persons": len({t["person"] for t in tenures}),
                "offices": sorted({t["office"] for t in tenures}),
                "years_covered": [min(t["start_year"] for t in tenures),
                                  max(t["end_year"] for t in tenures)],
                "with_start_month": sum(1 for t in tenures if t["start_month"]),
                "with_end_month": sum(1 for t in tenures if t["end_month"]),
                "cbdb_aligned": sum(1 for t in tenures if t["cbdb_id"]),
                "with_leave": sum(1 for t in tenures if t["leave"] != "未載"),
                "shu_li": sum(1 for t in tenures if t["tenure_type"] == "署理"),
                "same_name_risk": sum(1 for t in tenures if t.get("same_name_risk")),
                "shilu_persons": len(shilu),
                "shilu_hits": sum(v["count"] for v in shilu.values()),
                "person_years": sum(len(t["years"]) for t in tenures),
            },
        },
        "tenures": tenures,
        "shilu": shilu,
    }
    if out_path is None:
        out_path = DATA / "official_buyuan.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


if __name__ == "__main__":
    doc = export_buyuan()
    s = doc["meta"]["stats"]
    print(f"部院任职段 {s['tenures']}（{s['persons']} 人，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("官职:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"CBDB 对齐 {s['cbdb_aligned']}，离任原因 {s['with_leave']}，署理 {s['shu_li']}，"
          f"同名风险段 {s['same_name_risk']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
