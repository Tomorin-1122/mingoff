# -*- coding: utf-8 -*-
"""276 年事件流装配：年表条目 → 任职段（tenure）。

## 年表体例（已实测）

年表是**「年在位」体**：某人某年出现在表里 = 该年此人在任；注文记该年的
任免动作。所以装配逻辑是：

  1. 按 (person, section) 把条目按年排序 → 得到「在任年序列」
  2. 年连续（或年份差=1）的合并为一段 → start_year / end_year
  3. 从注文事件推断边界精度：
       - 该年有「入/任/起/召/入直」→ start_month 可信（有月则取月）
       - 该年有「罷/卒/致仕/削籍/丁憂」→ end_month 可信
       - 无事件 → 仅到年（start_month/end_month = NULL，D4 纪律）
  4. 年与年之间的空档 = 离任期（不填补，空白即信息）

## 与前缀标记

* `start_clamped` / `end_clamped`：段边界受"该人首次/末次出现"限制（可能未载）
* `confidence`：有明确任免事件 = 0.8；仅出现在表里 = 0.6；段首尾无事件 = 0.5
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"mingoff/src/mingoff/data")

# 事件动词分类（装配边界判据）
# ⚠️ 年表注文的"入职"多是**不带动词的授官记述**（'禮尚兼東閣大學士入'、
# '遷禮尚兼東閣大學士'），所以除显式动词外，还要认「兼…大學士入」这类
# 定式（见 ENTER_PAT）。只靠动词表会让起月覆盖率低到 8%（实测）。
ENTER = {"入", "入朝", "入直", "任", "起", "起復", "召", "復官", "還朝", "視事", "至京"}
LEAVE = {"罷", "卒", "致仕", "削籍", "革職", "下獄", "論死", "正法", "自盡",
         "被執", "戍", "謫", "丁憂", "丁父憂", "丁母憂", "憂去", "乞歸", "乞休",
         "養病", "杜門", "卒于", "調別任", "免", "回籍", "致仕歸"}
PROMOTE = {"遷", "改", "進", "加", "兼", "掌"}

# 入职定式（正则，在 chunk 上匹配）
import re as _re
ENTER_PAT = _re.compile(
    r"(大學士入|入閣|入直|入朝|兼東閣大學士|兼文淵閣大學士|兼武英殿大學士|"
    r"兼文華殿大學士|兼建極殿大學士|兼中極殿大學士|兼謹身殿大學士|兼華蓋殿大學士|"
    r"遷禮尚兼|遷禮尚|任[;；。]?$|起用|召|至京|視事|掌翰林院事)")


def norm_verb(v: str, chunk: str = "") -> str:
    """动词 + chunk 定式联合判定。"""
    if chunk and ENTER_PAT.search(chunk):
        return "enter"
    for s in ENTER:
        if v.startswith(s):
            return "enter"
    for s in LEAVE:
        if v.startswith(s):
            return "leave"
    return "other"


# section 归并：殿閣-XX-YY 全部归为「殿閣大學士」（同一人的殿阁官经历了
# 翰林学士→侍读学士→国子监祭酒等台阶，细分会导致同一段任期被切成多段）
def canon_section(sec: str) -> str:
    if sec.startswith("內閣"):
        return "內閣"
    if sec.startswith("殿閣"):
        # 大学士本体（中極/建極/文華/武英/文淵/東閣/華蓋/謹身）
        for d in ("中極殿", "建極殿", "文華殿", "武英殿", "文淵閣", "東閣", "華蓋殿", "謹身殿"):
            if sec == f"殿閣-{d}":
                return "殿閣大學士"
        return "翰林院"
    return sec


def load():
    ents = json.loads((ROOT / "neige_entries_aligned.json").read_text(encoding="utf-8"))
    evs = json.loads((ROOT / "neige_events.json").read_text(encoding="utf-8"))
    # 事件按 (person, year) 归并
    by_py = defaultdict(list)
    for e in evs:
        for v in e.get("events", []):
            by_py[(e["person"], e["year"])].append(v)
    return ents, by_py


def build_tenures():
    ents, by_py = load()
    # 按 (person, canon_section) 聚合在任年
    pres = defaultdict(set)
    for e in ents:
        if e["cbdb_id"] is None and e["person"].startswith(("明代", "年官")):
            continue
        pres[(e["person"], canon_section(e["section"]))].add(e["year"])

    tenures = []
    for (person, section), years in pres.items():
        ys = sorted(years)
        # 切连续段
        segs, cur = [], [ys[0]]
        for y in ys[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                segs.append(cur)
                cur = [y]
        segs.append(cur)

        for seg in segs:
            s_y, e_y = seg[0], seg[-1]
            # 边界事件（动词 + chunk 定式联合判定）
            s_evs = [v for v in by_py.get((person, s_y), [])]
            e_evs = [v for v in by_py.get((person, e_y), [])]
            s_enter = [v for v in s_evs if norm_verb(v["verb"], v.get("raw", "")) == "enter"]
            e_leave = [v for v in e_evs if norm_verb(v["verb"], v.get("raw", "")) == "leave"]
            # 兜底：该年有 leave 事件但没识别到 enter 时，若段首年亦无任何事件，
            # 说明此人入职早于年表可见范围（如册 1 起点前的旧任）
            e_any_leave = [v for v in e_evs if norm_verb(v["verb"], v.get("raw", "")) == "leave"]

            # 起始月：该年有入职事件且事件带月 → 取月；否则 NULL（不臆造，D4）
            start_month = None
            if s_enter:
                cand = [v for v in s_enter if v["month"]]
                if len({v["month"] for v in cand}) == 1:
                    start_month = cand[0]["month"]
            # 终止月：同理
            end_month = None
            if e_leave:
                cand = [v for v in e_leave if v["month"]]
                if len({v["month"] for v in cand}) == 1:
                    end_month = cand[0]["month"]

            # ⚠️ 单年段（s_y == e_y）且有**入职与离任双事件**：
            # 年表体例是「同年内先入后离」（如 楊榮 1407 年十月起復、次年六月丁忧、
            # 但表把两年并进同一格）。这**不是时间倒挂**，而是段被压成一年。
            # 正确处理：保留年份，两个月份都记，并标注 month_conflict 供 UI 提示；
            # 不擅自调换或丢弃月份（D4：不臆造，也不删真实记载）。
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
                "cbdb_id": next((e["cbdb_id"] for e in ents
                                 if e["person"] == person and e["cbdb_id"]), None),
                "section": section,
                "start_year": s_y,
                "start_month": start_month,
                "end_year": e_y,
                "end_month": end_month,
                "month_conflict": month_conflict,
                "span_years": len(seg),
                "years": seg,
                "enter_verbs": sorted({v["verb"] for v in s_enter}),
                "leave_verbs": sorted({v["verb"] for v in e_leave}),
                "confidence": conf,
                "note": next((e["note"] for e in ents
                              if e["person"] == person and e["year"] == s_y), ""),
            })
    return tenures


if __name__ == "__main__":
    ts = build_tenures()
    out = ROOT / "tenures_from_nianbiao.json"
    out.write_text(json.dumps(ts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"任职段 {len(ts)} → {out}")
    from collections import Counter
    print("section 分布:", dict(Counter(t["section"].split("-")[0] for t in ts)))
    print("confidence:", dict(Counter(t["confidence"] for t in ts)))
    n_sm = sum(1 for t in ts if t["start_month"])
    n_em = sum(1 for t in ts if t["end_month"])
    print(f"有起月 {n_sm}（{100*n_sm/len(ts):.0f}%），有迄月 {n_em}（{100*n_em/len(ts):.0f}%）")
    cz = [t for t in ts if t["end_year"] >= 1628]
    print(f"\n崇祯相关段 {len(cz)}，示例:")
    for t in sorted(cz, key=lambda x: x["start_year"])[:12]:
        print(f"  {t['person']:<8} {t['section'][:14]:<16} {t['start_year']}"
              f"{'.'+str(t['start_month']) if t['start_month'] else ''}–{t['end_year']}"
              f"{'.'+str(t['end_month']) if t['end_month'] else ''} "
              f"({'/'.join(t['enter_verbs']) or '-'} → {'/'.join(t['leave_verbs']) or '-'}) conf={t['confidence']}")
