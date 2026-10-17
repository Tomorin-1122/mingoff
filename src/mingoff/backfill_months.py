# -*- coding: utf-8 -*-
"""把中研院《明實錄》月份命中回填到 demo 数据。

## 策略（保守，宁缺毋滥）

`sinica_months.json` 里每个人有若干命中记录（year / era_year / month / source / content）。
**不做语义判断**（哪条是"上任"、哪条是"离任"）——那是校勘工作，不是脚本该干的。
回填规则只有一条：

* 某人某年若恰有**一条**命中（或多条同月），把该年该月视作该人「有记载的事件月」，
  仅当该年恰是其 tenure 的 start_year / end_year 时，回填 start_month / end_month。

多条同年不同月的命中**不回填**（歧义，留给人工校勘），但全部进抽屉展示。

## 明确的边界

* 闰月（`leap: true`）：把月份原样填入（如閏五月 → 5）。画布按 12 格等宽，
  闰月不占独立格——展示时在抽屉里注明「閏」，不假装日历精确。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]  # .../mingoff

SHILU_PATH = ROOT / "src" / "mingoff" / "data" / "sinica_months.json"
MERGED = ROOT / "web" / "demo-data-merged.json"


def main() -> int:
    if not SHILU_PATH.is_file():
        print(f"[错误] 缺 {SHILU_PATH}，先跑 _verify/fetch_months_for_demo.py")
        return 2
    shilu = json.loads(SHILU_PATH.read_text(encoding="utf-8"))
    data = json.loads(MERGED.read_text(encoding="utf-8"))

    # 按人建 year → {month: is_leap} 索引（同月既见闰又见平，按平月记——保守）
    by_person: dict[str, dict[int, dict[int, bool]]] = defaultdict(lambda: defaultdict(dict))
    for person, recs in shilu.items():
        for r in recs:
            y = r.get("era_year")
            if y is None:
                continue
            # era_year 是年号年序（崇祯十年=10），转公元年：崇祯元年=1628
            # 但命中可能落在萬曆/天啟朝 —— 用 era 字段判断换算基准
            era = r.get("era", "")
            if era == "崇禎":
                gy = 1627 + y
            elif era == "天啟":
                gy = 1620 + y
            elif era == "萬曆":
                gy = 1572 + y
            else:
                continue  # 其他朝的命中对崇祯朝 demo 无意义
            m = r.get("month")
            if m:
                # 闰/平冲突时取平（闰标记只在唯一来源时保留）
                if m not in by_person[person][gy] or not r.get("leap"):
                    by_person[person][gy][m] = bool(r.get("leap"))

    filled = ambiguous = 0
    for t in data["tenures"]:
        p = t["person"]
        months = by_person.get(p)
        if not months:
            continue
        sy, ey = t.get("start"), t.get("end")

        def month_is_unique(ms: dict) -> tuple[int | None, bool]:
            """该年恰一个月 → (month, is_leap)；多月 → (None, False)。"""
            if len(ms) != 1:
                return None, False
            return next(iter(ms.items()))

        # 起始年：该年恰好一条月记录 → 回填（含闰月标记）
        if sy is not None and sy in months and t.get("start_month") is None:
            m, leap = month_is_unique(months[sy])
            if m is not None:
                t["start_month"] = m
                t["start_month_leap"] = leap
                t["start_month_from_shilu"] = True
                filled += 1
            else:
                ambiguous += 1
        # 终止年：同规则（不覆盖 end_clamped 的 3 月截断——保留截断语义）
        if ey is not None and ey in months and t.get("end_month") is None and not t.get("end_clamped"):
            m, leap = month_is_unique(months[ey])
            if m is not None:
                t["end_month"] = m
                t["end_month_leap"] = leap
                t["end_month_from_shilu"] = True
                filled += 1
            else:
                ambiguous += 1

    MERGED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[回填完成] 明确回填 {filled} 处月份；{ambiguous} 处同年多月、留待人工校勘")
    # 汇总
    n_sm = sum(1 for t in data["tenures"] if t.get("start_month"))
    n_em = sum(1 for t in data["tenures"] if t.get("end_month"))
    print(f"  现在有 start_month 的 {n_sm}/{len(data['tenures'])} 条；"
          f"end_month {n_em} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
