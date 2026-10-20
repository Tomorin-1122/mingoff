# -*- coding: utf-8 -*-
"""中研院《明實錄》数据对接：把实录月份回填到年表装配出的任职段。

## 对接逻辑（保守，宁缺毋滥）

对每个任职段（person, start_year, end_year）：
  1. 取该人该年的实录命中（era_year → 公元年）
  2. **入职月**：命中在该年 start_year 且文本含授官类词（除/授/遷/改/命…）
     → 视为就任月。若同年多条，取最早且动作词最明确的；**多条冲突则不填**。
  3. **离任月**：同理，命中该年 end_year 且含罢/致仕/卒等词。
  4. 只有**恰好一条**候选时才回填（与 backfill_months.py 同纪律）。

## 与已有回填的关系

年表口径的段可能**已有月份**（从年表注文来）。两者并存时：
  * 年表月份优先（同源，精度最高）
  * 实录月份作为**校勘值**存入 `sinica_start_month`，若与年表冲突进 conflict 清单
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"mingoff/src/mingoff/data")

ERA_START = {"崇禎": 1628, "萬曆": 1573, "嘉靖": 1522, "隆慶": 1567, "天啟": 1621,
             "泰昌": 1620, "正德": 1506, "弘治": 1488, "成化": 1465, "正統": 1436,
             "景泰": 1450, "天順": 1457, "洪武": 1368, "建文": 1399, "永樂": 1403,
             "洪熙": 1425, "宣德": 1426}

# 授官类（入职）／去职类（离任）的实录文本特征。
# ⚠️ 关键教训（实测 43 例冲突诊断得出）：实录命中是「该人在该年被提及的
# 任意一条」，**不等于就任该职**。「遷」既可升任此职也可迁离此职，
# 用宽泛动词会把无关记事当成就任（如周道登天启七年十月记事被当成入阁月）。
# 收紧为**明确指向本官职的授官定式**。
SECTION_OFFICE = {
    "內閣": r"(大學士|入閣|入直|預機務|內閣)",
    "殿閣大學士": r"(大學士|入閣|入直|預機務)",
    "翰林院": r"(翰林|侍讀學士|侍講學士|學士|檢討|編修|庶吉士|祭酒|詹事)",
}
APPOINT_GENERIC = re.compile(r"(除|授|擢|簡用|起復|起用|召|命|補|推|改任|陞|升任)")
DEPART = re.compile(r"(罷|致仕|乞休|乞歸|丁憂|削籍|削奪|免|謫|降|卒|故|病|歸省|回籍|奪官|為民)")


def is_appointment(rec, section: str) -> bool:
    """该条实录命中是否**明确记载此人就任本类官职**。
    条件：含本官职关键词 且（含授官动词 或 含「入/兼」定式）。"""
    txt = rec.get("content", "")
    kw = SECTION_OFFICE.get(section, SECTION_OFFICE["翰林院"])
    if not re.search(kw, txt):
        return False
    return bool(APPOINT_GENERIC.search(txt) or "入" in txt or "兼" in txt)


def era_year_to_gy(era: str, era_no: int, fallback: int | None) -> int | None:
    if not era or not era_no:
        return fallback
    st = next((v for k, v in ERA_START.items() if era.startswith(k)), None)
    return st + era_no - 1 if st else fallback


def main():
    ts = json.loads((ROOT / "tenures_from_nianbiao.json").read_text(encoding="utf-8"))
    sinica = json.loads((ROOT / "sinica_all.json").read_text(encoding="utf-8"))

    # 按 (人, 公元年) 归并实录命中
    by_py = defaultdict(list)
    for person, recs in sinica.items():
        for r in recs:
            gy = era_year_to_gy(r.get("era", ""), r.get("era_year"), r.get("year"))
            if not gy or not r.get("month"):
                continue
            by_py[(person, gy)].append(r)

    filled_s = filled_e = conflicts = 0
    n = 0
    for t in ts:
        n += 1
        p, sy, ey = t["person"], t["start_year"], t["end_year"]

        # ---- 入职月 ----
        cand = [r for r in by_py.get((p, sy), []) if is_appointment(r, t["section"])]
        if cand:
            months = {r["month"] for r in cand}
            if len(months) == 1:
                m = cand[0]["month"]
                t["sinica_start_month"] = m
                t["sinica_start_source"] = cand[0]["source"][:60]
                if t.get("start_month") is None:
                    t["start_month"] = m
                    t["start_month_source"] = "sinica"
                    filled_s += 1
                elif t["start_month"] != m:
                    t["month_conflict"] = True
                    t["note"] = (t.get("note", "") + f"\n[校勘] 年表记 {t['start_month']} 月就任，"
                                 f"实录记为 {m} 月（{cand[0]['source'][:40]}），"
                                 "以年表为准，实录存 sinica_start_month").strip()
                    conflicts += 1

        # ---- 离任月 ----
        cand = [r for r in by_py.get((p, ey), []) if DEPART.search(r.get("content", ""))]
        if cand:
            months = {r["month"] for r in cand}
            if len(months) == 1:
                m = cand[0]["month"]
                t["sinica_end_month"] = m
                t["sinica_end_source"] = cand[0]["source"][:60]
                if t.get("end_month") is None:
                    t["end_month"] = m
                    t["end_month_source"] = "sinica"
                    filled_e += 1
                elif t["end_month"] != m:
                    t["month_conflict"] = True
                    conflicts += 1

    (ROOT / "tenures_with_sinica.json").write_text(
        json.dumps(ts, ensure_ascii=False, indent=1), encoding="utf-8")

    have_s = sum(1 for t in ts if t.get("start_month"))
    have_e = sum(1 for t in ts if t.get("end_month"))
    print(f"任职段 {n}")
    print(f"  实录回填起月 {filled_s}，回填迄月 {filled_e}")
    print(f"  现在有起月 {have_s}（{100*have_s/n:.0f}%），有迄月 {have_e}（{100*have_e/n:.0f}%）")
    print(f"  年表↔实录 月份冲突 {conflicts}（已标注，年表优先）")
    cz = [t for t in ts if t["end_year"] >= 1628]
    cz_s = sum(1 for t in cz if t.get("start_month"))
    print(f"  崇祯朝段 {len(cz)}，有起月 {cz_s}（{100*cz_s/max(len(cz),1):.0f}%）")


if __name__ == "__main__":
    main()
