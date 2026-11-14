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
                              build_shilu, entry_names_source_office,
                              _month_leap, precedes_office_name)
from mingoff.buyuan_repair import ENTRY_ADD, NAME_CANON, NAME_FIX, OFFICE_FIX

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
# 「遷/改/調/還」带宾语 = 迁出本衙（简体变体防 OCR 偶产简体）。命名 BY 避免与
# 京卿部 LEAVE_QIAN（official_jingqing 独立副本）混淆——两表词序一致。
LEAVE_QIAN_BY = re.compile(r"[遷改調還迁调还][一-龥]")


def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


# 「X署」收尾 = 由 X 署理入场（兵左侍署 / 左都署）——京卿部已有，部院补（張璁
# 1527「八、庚戌、五,兵左侍署」此前不识别，起月误取「入閣」的 10 月）
ENTER_SHU = re.compile(r"[一-龥]{1,6}署[,，;；。]?$")


def _enter_chunk(chunk: str) -> bool:
    # 「入閣」的「入」是入阁大学士语境，不是本衙入场证据（張璁 1527 误触发）
    text = chunk.replace("入閣", "").replace("入阁", "")
    if any(v in text for v in ENTER_BASE):
        return True
    if ENTER_QIAN.search(chunk):      # "司農卿遷" 收尾 → 迁入
        return True
    if ENTER_GAI.search(chunk) and not LEAVE_GAI.search(chunk):
        return True                   # "工尚改" 收尾 → 由工部改任本任
    if ENTER_SHU.search(chunk):
        return True                   # "兵左侍署" 收尾 → 署理入场
    return False


def _leave_chunk(chunk: str, office: str = "") -> str | None:
    """返回离任标签；无离任返回 None。office 用于衙衔定向（遷X 的 X 若为
    本衙官衔必为到任——左都御史不可能作为都察院的离任目的地）。"""
    if "南京" in chunk and ("改" in chunk or "調" in chunk):
        return "改南京"
    # 2026-11-12 原书验证补全：誅/死/閑住此前不在表内，死难段被误判无离任注
    # 而落进迄月推定池（余熂 1385 实录四月伏誅被推成六月）。「死」列于死难词之后。
    for v in ("罷", "罢", "卒", "致仕", "削籍", "下獄", "下狱", "被執", "戍", "謫", "谪",
              "丁憂", "丁父憂", "丁母憂", "憂去", "乞歸", "乞休", "養病", "免", "回籍", "回部", "回京",
              "為民", "降", "死於難", "死難", "歿於", "正法", "自盡", "殉難", "棄市",
              "革職", "奪官", "謫戍", "奔喪", "守制",
              "誅", "诛", "戰死", "閑住", "閒住", "死"):
        if v in chunk:
            return {"卒": "卒于任", "歿於": "卒于任", "死於難": "死於難", "死難": "死於難",
                    "誅": "罪誅", "诛": "罪誅", "死": "死",
                    "閑住": "閑住", "閒住": "閑住"}.get(v, v)
    if re.search(r"[一-龥]出[,，;；。]?|[一二三四五六七八九十]+[、，][^,，]*出[一-龥]", chunk):
        return "出為外任"
    if LEAVE_GAI.search(chunk):       # "改兵尚" → 改除
        return "改除"
    m = LEAVE_QIAN_BY.search(chunk)   # "調大理卿"带宾语 → 調除（馬森 1558「坐调大理卿」）
    if m:
        if precedes_office_name(chunk, m.start()):
            return None          # 「吏左侍遷左都」完整句式=到任，非离任
        if office == "都察院" and chunk[m.start() + 1:m.start() + 4].startswith(
                ("左都", "右都", "副都", "僉都", "佥都")):
            return None          # 「遷左都」領起式=到任本衙（劉宇 1507 型）
        return {"遷": "遷除", "改": "改除", "調": "調除", "還": "還除",
                "迁": "遷除", "调": "調除", "还": "還除"}[m.group()[0]]
    return None


def _start_month(note: str) -> tuple[int | None, bool, bool]:
    for c in _chunks(note):
        if _cross_year(c):
            continue
        if _enter_chunk(c):
            m, lp = _month_leap(c)
            if m:
                return m, lp, True
    # 退回本年首个纪月（不标记为事件）
    for c in _chunks(note):
        if _cross_year(c):
            continue
        m, lp = _month_leap(c)
        if m:
            return m, lp, False
    return None, False, False


def _leave(note: str, office: str = "") -> tuple[int | None, bool, str]:
    for c in _chunks(note):
        if _cross_year(c):
            # 跨年 chunk 内混排本年离任（唐暉 1628「八、庚子、十二,遷尚寶卿…；
            # 五年三、…遷右僉都」整条曾被跨年规则跳过）：按逗号切子句回查——
            # 离任词所在子句须自带月分且不跨年（張珩「戍邊慶陽卅一年七」子句
            # 含跨年词仍安全跳过；无月分纯词如「削籍」不取，防别年罢官误挂）。
            cur_m = cur_lp = None
            for sub in re.split(r"[，,]", c):
                sub = sub.strip()
                if not sub or _cross_year(sub):
                    continue
                m, lp = _month_leap(sub)
                if m:
                    cur_m, cur_lp = m, lp   # 离任词前方最近的本年月分
                lb = _leave_chunk(sub, office)
                if lb:
                    if lb in ("下獄", "下狱") and re.search(r"宥|釋|释|復職|復官|赦", sub):
                        continue
                    if cur_m:
                        return cur_m, cur_lp, lb
                    break   # 离任词无月分可归属，不取（防别年罢官误挂）
            continue
        label = _leave_chunk(c, office)
        if label:
            if label in ("下獄", "下狱") and re.search(r"宥|釋|释|復職|復官|赦", c):
                continue          # 下狱后获释复职——非离任（程富 1446「下狱，寻釋」）
            return (*_month_leap(c), label)
    return None, False, "未載"


# D-01：同名拆分后，是否 risky 由「同名实体数 >1」自动判定，不再硬编码名单。
# 断段合并后降一档置信度（仍限定在既有档位，避免出现 0.55 之类）
CONF_DOWN = {0.8: 0.7, 0.7: 0.6, 0.6: 0.5, 0.5: 0.5}


def load_buyuan() -> list[dict]:
    """v3 校记回填版（人工校对 276/277 年）→ v2 修复版 → v1。"""
    for name in ("vol1_buyuan_entries_v3.json", "vol1_buyuan_entries_v2.json",
                 "vol1_buyuan_entries.json"):
        p = DATA / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit("找不到部院条目文件（v3/v2/v1 均缺失）")


def load_buyuan_cbdb() -> dict:
    for name in ("vol1_buyuan_person_cbdb_v4.json", "vol1_buyuan_person_cbdb_v3.json",
                 "vol1_buyuan_person_cbdb_v2.json", "vol1_buyuan_person_cbdb.json"):
        p = DATA / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def build_buyuan_tenures() -> list[dict]:
    entries = [e for e in load_buyuan() if e["year"] <= CUT_Y]
    # 原书实拍补行（2026-11-14 遗留轮）：OCR/行归属整行丢失、以实拍裁决的条目
    # （buyuan_repair.ENTRY_ADD，pf=book-add 可溯源）。同年同 note 重复由下方
    # dedup 循环兜底。
    for add in ENTRY_ADD:
        if add["year"] <= CUT_Y:
            entries.append(dict(add))
    # 无标签列页（p607/p661 型）行→衙重复归属修正 + 讹名/错挂归正（2026-11-13
    # 抽查轮）：运行时应用 OFFICE_FIX / NAME_FIX（buyuan_repair 同款）。NAME_FIX
    # 键序敏感（倉場互换对：王永光→鐘羽正 先于 鍾羽→王永光），dict 保序生效。
    # NAME_CANON 为异体全局归一（屠勲类），先于键式修正执行。
    for e in entries:
        canon = NAME_CANON.get(e.get("person") or "")
        if canon:
            e["name_fix"] = {"from": e["person"], "to": canon}
            e["person"] = canon
            e["person_id"] = canon
        fx = OFFICE_FIX.get((e["year"], e.get("person"), e["office"]))
        if fx:
            e["office_fix"] = {"from": e["office"], "to": fx[0], "source": fx[1]}
            e["office"] = fx[0]
        nf = NAME_FIX.get((e["year"], e.get("person"), e["office"]))
        if nf:
            e["name_fix"] = {"from": e["person"], "to": nf[0]}
            e["person"] = nf[0]
            e["person_id"] = nf[1]
    mapping = load_buyuan_cbdb()
    name_entities: dict[str, set[str]] = defaultdict(set)
    for e in entries:
        name_entities[e["person"]].add(e.get("person_id") or e["person"])

    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    skipped_no_office = []
    for e in entries:
        if not e["office"]:
            # NULL 铁律：office 未归部不得造假值；条目留待回原书核对
            skipped_no_office.append(e)
            continue
        pid = e.get("person_id") or e["person"]
        by_key[(pid, e["office"])].append(e)

    tenures: list[dict] = []
    for (pid, office), rows in sorted(by_key.items()):
        rows.sort(key=lambda e: e["year"])
        person = rows[0]["person"]
        person_label = rows[0].get("person_label") or person
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
        raw_of = {e["year"]: e.get("raw_office") or office for e in rows}
        # D-11 方案B：行→衙归属依据贯通到段（row-order=灰显候选）
        status_of = {e["year"]: e.get("office_status") for e in rows}
        segs, cur = [], [years[0]]
        for y in years[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                segs.append(cur)
                cur = [y]
        segs.append(cur)

        # D-01：同名多实体才标风险；拆开后同一 person_id 不得再跨代
        same_name_risk = len(name_entities[person]) > 1
        for seg in segs:
            sy, ey = seg[0], seg[-1]
            s_note, e_note = note_of.get(sy, ""), note_of.get(ey, "")
            sm, sm_leap, sm_event = _start_month(s_note)
            em, em_leap, leave = _leave(e_note, office)

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

            m = mapping.get(pid, {})
            ttype = "署理" if ("署" in s_note or "署" in flag_of.get(sy, "")) else "实授"
            # D-11：段内各年归属依据聚合——全 row-order 灰显；混合 mixed；页核优先
            st = [status_of.get(y) for y in seg]
            if all(s == "page-verified" for s in st):
                office_status = "page-verified"
            elif any(s == "row-order" for s in st):
                office_status = "row-order" if all(s == "row-order" for s in st) else "mixed"
            elif all(s == "name-anchor" for s in st):
                office_status = "name-anchor"
            else:
                office_status = None
            tenures.append({
                "person": person,
                "person_id": pid,
                "person_label": person_label,
                "cbdb_id": m.get("cbdb_id"),
                "cbdb_name": m.get("cbdb_name"),
                "office": office,
                "office_raw": raw_of.get(sy, office),
                "office_status": office_status,
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
                "start_book_page": rows[0].get("book_page"),
                "end_book_page": rows[-1].get("book_page"),
                "years": seg,
                **({"same_name_risk": True} if same_name_risk else {}),
            })
    if skipped_no_office:
        _append_review(skipped_no_office)
    return infer_yield_ends(merge_gap_segments(tenures))


# 推定守卫：注文含被捕/勘问类词 → 继任到任不蕴含前任离任（下狱后可复职），
# 且跨年 chunk 内漏识别的离任词也在此拦下（宁空勿错，2026-11-12 原书验证轮）
_YIELD_GUARD = re.compile(
    r"下獄|下狱|逮|繫|誅|诛|死|戰死|閑住|閒住|謫|谪|戍|還|还|調|调|削籍|革職"
    r"|罷|罢|卒|致仕|乞歸|乞休|憂|免|降|為民|回籍|棄市")


def infer_yield_ends(tenures: list[dict]) -> list[dict]:
    """同衙同年继任到任 → 推定前任迄月（2026-11-09，四表共用）。

    年表「迁出/迁入双记」体例下，前任无离任注时其段以年截尾（D8 填满到年底），
    画布上与同年到任的继任者重叠。推定：同 office 相邻两段，a 无离任注、迄月空、
    a.end_year == b.start_year、b 起月已知且非署理 → a.end_month = b.start_month，
    标 `yield_inferred`（抽屉注明「迄月据继任到任推定」，非史料所载）。
    推定只收紧、不外延：b 起月早于 a 起月（同年倒序）不推，宁缺勿错。

    2026-11-12 原书验证轮两改：
    * 规则二（先跑，证据更硬）：同人下一段（转任）入场注指认自本衙迁来
      （如丁懋遜通政使段注「太僕卿遷」）→ 本衙段迄=下段起。若规则一先跑会把
      丁懋遜太僕卿段误截到同年第三人到任月，故规则二必须先行。
    * 规则一加守卫：a.note 含被捕/死难/罢退类词但 leave 仍=未載（下狱复职型、
      跨年 chunk 漏识型）→ 跳过推定。
    """
    # 规则二：同人下段入场注指认自本衙迁来 → 迄=下段起
    by_person: dict[str, list[dict]] = defaultdict(list)
    for t in tenures:
        by_person[t["person_id"]].append(t)
    for ts in by_person.values():
        ts.sort(key=lambda t: (t["start_year"], t["start_month"] or 13))
        for a, c in zip(ts, ts[1:]):
            if (a["end_month"] is not None or a["leave"] != "未載"
                    or a.get("end_clamped") or a.get("yield_inferred")
                    or len(a["office"]) < 3):
                continue      # 二字衙名（禮部/兵部）防「禮部侍郎」子串误配，不启用
            if not c["start_month"] or c.get("tenure_type") == "署理":
                continue
            # 只接续同年换职或次年转任，防隔多年误配（a 段早已结束）
            if c["start_year"] not in (a["end_year"], a["end_year"] + 1):
                continue
            if (c["start_year"] == a["end_year"]
                    and c["start_month"] <= (a["start_month"] or 0)):
                continue
            entry = next((x for x in _chunks(c.get("note") or "")
                          if _enter_chunk(x)), None)
            if entry and entry_names_source_office(a["office"], entry):
                a["end_year"] = c["start_year"]
                a["end_month"] = c["start_month"]
                if c["start_year"] > a["years"][-1]:
                    # audit G2 铁律：years 必须连续覆盖 start~end（丁懋遜 1621→1622）
                    a["years"] = a["years"] + list(
                        range(a["years"][-1] + 1, c["start_year"] + 1))
                a.pop("gap_after", None)   # 已接续，原 gap 虚线撤除
                a["yield_inferred"] = True

    # 规则一：同衙同年继任到任 → 推定前任迄月（原规则 + 守卫）
    by_off: dict[str, list[dict]] = defaultdict(list)
    for t in tenures:
        by_off[t["office"]].append(t)
    for lst in by_off.values():
        lst.sort(key=lambda t: (t["start_year"], t["start_month"] or 13))
        for a, b in zip(lst, lst[1:]):
            if (a["end_month"] is None and a["leave"] == "未載"
                    and a["end_year"] == b["start_year"]
                    and b["start_month"]
                    and b.get("tenure_type") != "署理"
                    and not _YIELD_GUARD.search(a.get("note") or "")
                    and (a["start_year"] != b["start_year"]
                         or b["start_month"] > (a["start_month"] or 0))):
                a["end_month"] = b["start_month"]
                a["yield_inferred"] = True
    return tenures


def merge_gap_segments(tenures: list[dict]) -> list[dict]:
    """合并同人同衙 1–2 年「无离任/入场注文」的缺口段，并显式记录 gap_years。

    年表为逐年名单：同人同衙中间缺 1–2 年、且前段无离任、后段无入场事件，
    绝大多数是上游 OCR 缺行（部院 v1 实测 282 段假断段）。合并只为呈现，**不伪造**：
    缺失年份写入 `gap_years`，置信度降一档，前端应以虚线段标识。
    """
    by_key = defaultdict(list)
    for t in tenures:
        by_key[(t["person_id"], t["office"])].append(t)
    out: list[dict] = []
    for key, ts in by_key.items():
        ts.sort(key=lambda t: t["start_year"])
        cur = ts[0]
        for nxt in ts[1:]:
            gap = nxt["start_year"] - cur["end_year"] - 1
            boundary_end = cur["leave"] != "未載"
            boundary_start = any(v in (nxt["note"] or "") for v in ENTER_BASE)
            if 0 < gap <= 2 and not boundary_end and not boundary_start \
                    and not cur["end_clamped"]:
                merged = dict(cur)
                merged["end_year"] = nxt["end_year"]
                merged["end_month"] = nxt["end_month"]
                merged["end_clamped"] = nxt["end_clamped"]
                merged["leave"] = nxt["leave"]
                merged["month_conflict"] = cur["month_conflict"] or nxt["month_conflict"]
                merged["years"] = cur["years"] + list(
                    range(cur["end_year"] + 1, nxt["end_year"] + 1))
                merged["gap_years"] = (cur.get("gap_years") or []) + list(
                    range(cur["end_year"] + 1, nxt["start_year"]))
                merged["merged_segments"] = (cur.get("merged_segments") or 1) + \
                    (nxt.get("merged_segments") or 1)
                merged["confidence"] = CONF_DOWN.get(
                    min(cur["confidence"], nxt["confidence"]), 0.5)
                cur = merged
            else:
                out.append(cur)
                cur = nxt
        out.append(cur)
    out.sort(key=lambda t: (t["person_id"], t["office"], t["start_year"]))
    # 剩余多段之间的缺口：不合并，但显式登记 gap_after（供前端虚线/待校），
    # 避免「静默两段」；同名风险组的缺口另行标记。
    by2 = defaultdict(list)
    for t in out:
        by2[(t["person_id"], t["office"])].append(t)
    for ts in by2.values():
        ts.sort(key=lambda t: t["start_year"])
        for a, b in zip(ts, ts[1:]):
            gap = b["start_year"] - a["end_year"] - 1
            if gap > 0:
                a["gap_after"] = list(range(a["end_year"] + 1, b["start_year"]))
    return out


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
            "version": 3,
            "canvas_from": 1368,
            "license": "CC BY-NC-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "source": "张德信《明代职官年表》册1·部院大臣年表（京師）（MinerU OCR）；"
                      "v2 修复：人名归一/伪名清理/注文隔离/衙署分期/CBDB 重挂；"
                      "v3 D-01：同名拆分 person_id（李本/李敏/王佐/顧佐/吳山/胡松），"
                      "張鳳 1629 改張鳳翔；"
                      "人名校验：CBDB 20261010 + 中研院明實錄 + 弇山堂别集/國榷（识典古籍）；"
                      "《明實錄》命中据中研院检索",
            "pipeline": "mingoff.official_buyuan (v3: D-01 identity split + (person_id,office) "
                        "分组 + gap 合并 + D15)",
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
        out_path = DATA / "official_buyuan.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def refresh_manifest(doc: dict) -> None:
    """由当前数据实测刷新 manifest（规范 3.7：禁止手写统计/Gates）。"""
    p = DATA / "vol1_buyuan_manifest.json"
    if not p.is_file():
        return
    m = json.loads(p.read_text(encoding="utf-8"))
    entries = load_buyuan()
    years = sorted({e["year"] for e in entries})
    missing = [y for y in range(1368, CUT_Y + 1) if y not in years]
    tenures = doc["tenures"]
    bad_years = [t for t in tenures if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    bad_month = [t for t in tenures if any(
        mm is not None and not 1 <= mm <= 12 for mm in (t["start_month"], t["end_month"]))]
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > 3)
           or (t["end_year"] == CUT_Y and not (t["end_clamped"] and t["end_month"] == 3))]
    repair = {}
    repair_full = {}
    rp = DATA / "vol1_buyuan_repair.json"
    if rp.is_file():
        repair_full = json.loads(rp.read_text(encoding="utf-8"))
        repair = repair_full.get("counts", {})
    # 剩余待校：长缺口 + 隔离注文 + 重复冲突，写入 review_v2
    gaps = []
    for t in tenures:
        if t.get("gap_after"):
            gaps.append({"person_id": t["person_id"], "person": t["person"],
                         "office": t["office"], "after": t["end_year"],
                         "years": t["gap_after"]})
    review_v2 = {"long_gaps": gaps,
                 "quarantined_notes": repair_full.get("note_quarantine", []),
                 "note_resolution": repair_full.get("note_resolution", []),
                 "note_resolution_counts": repair_full.get("note_resolution_counts", {}),
                 "dup_conflicts": repair_full.get("dup_conflicts", [])}
    (DATA / "vol1_buyuan_review_v2.json").write_text(
        json.dumps(review_v2, ensure_ascii=False, indent=1), encoding="utf-8")
    # G6：先写入实测 stats，再跑审计（审计会对比 manifest）；失败不阻塞导出但如实写状态
    m.setdefault("stats", {})
    m["stats"].update({
        "entries": len(entries),
        "persons_unique": len({e.get("person_id") or e["person"] for e in entries}),
        "display_persons": len({e["person"] for e in entries}),
        "split_entities": len({e.get("person_id") for e in entries
                               if "#" in (e.get("person_id") or "")}),
        "years": len(years), "missing_years": missing,
        "no_office_entries": sum(1 for e in entries if not e.get("office")),
        "offices": sorted({e["office"] for e in entries if e.get("office")}),
        "quarantined_notes": repair.get("quarantined"),
        "notes_inferred": repair.get("notes_inferred"),
        "notes_prefix": repair.get("notes_prefix"),
        "notes_manual": repair.get("notes_manual"),
        "note_resolution": repair_full.get("note_resolution_counts", {}),
        "book_patches": repair.get("book_patch"),
        "book_page_coverage": repair.get("book_page_coverage"),
        "review_items": len(gaps),
    })
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from mingoff.audit_buyuan import audit as _audit
        _r = _audit()
        g6 = "pass" if not _r["blockers"] else f"fail({_r['blockers']})"
    except Exception as exc:  # pragma: no cover
        g6 = f"not-run({exc})"
    m["tenure_assembly"] = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline": doc["meta"]["pipeline"],
        "output": "official_buyuan.json",
        "stats": doc["meta"]["stats"],
        "gates": {
            "G1": "pass" if not missing else f"fail(缺年 {missing[:5]})",
            "G2": "pass" if not bad_years else f"fail(段年不连续 {len(bad_years)})",
            "G3": "pass" if not bad_month and not d15 else
                  f"fail(月 {len(bad_month)} / D15 {len(d15)})",
            "G4": "run pytest tests/test_official_buyuan.py",
            "G5": "见 docs/部院数据接收报告.md 抽检",
            "G6": g6,
        },
        "status": "v3-g6-pass" if g6 == "pass" else "review",
        "identity": repair_full.get("identity", []),
        "repair": repair,
    }
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    doc = export_buyuan()
    refresh_manifest(doc)
    s = doc["meta"]["stats"]
    print(f"部院任职段 {s['tenures']}（{s['persons']} 实体 / {s['display_persons']} 姓名，"
          f"{s['years_covered'][0]}–{s['years_covered'][1]}，人-年 {s['person_years']}）")
    print("官职:", "、".join(s["offices"]))
    print(f"有起月 {s['with_start_month']}，有迄月 {s['with_end_month']}，"
          f"CBDB 对齐 {s['cbdb_aligned']}，离任原因 {s['with_leave']}，署理 {s['shu_li']}，"
          f"同名风险段 {s['same_name_risk']}")
    print(f"实录相关命中 {s['shilu_hits']} 条 / {s['shilu_persons']} 人")
    print("confidence:", dict(Counter(t["confidence"] for t in doc["tenures"])))
