# -*- coding: utf-8 -*-
"""D-11 方案 B：把行序兜底行的 (year, office) 显式降级为 office_status="row-order"。

老板拍板（2026-10-19）：先 B 后 A——B 立即让「哪些行是猜的」变成显式数据，A 按页核节奏走。

规则：
  1. 以 `vol1_buyuan_d11_review.json` 的 136 无标签年行为准；
  2. D42 已页核修正的年份（BOOK_PATCH 年份）**不降级**——数据以原书页证为准；
  3. (year, office) 覆盖判定：
     - 落在「行序兜底」行且无人名锚行覆盖 → entry.office_status = "row-order"
     - 落在「人名锚」行（conf≥0.5）→ entry.office_status = "name-anchor"（正向依据）
     - 其余（无依据行/提名失败等）→ 不标记，留待 D-11 后续轮次；
  4. 幂等：重复运行不叠加。

产物：回写 `vol1_buyuan_entries_v2.json`（office_status 字段）+ 统计打印。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))
DATA = HERE.parent.parent / "src" / "mingoff" / "data"

# D42 页核修正的年份（apply_book_patch 已按原书定案）——不降级
PAGE_VERIFIED_YEARS = {1546, 1547, 1548, 1558}


def main() -> None:
    review = json.loads((DATA / "vol1_buyuan_d11_review.json").read_text(encoding="utf-8"))
    rows = review["rows"]
    years_in_scope = sorted({x["year"] for x in rows})
    in_scope = set(years_in_scope) - PAGE_VERIFIED_YEARS

    fallback: set[tuple[int, str]] = set()
    anchor: set[tuple[int, str]] = set()
    for x in rows:
        y = x["year"]
        if y not in in_scope:
            continue
        off = x.get("suggest_office")
        if not off:
            continue
        if x.get("how") == "行序兜底":
            fallback.add((y, off))
        elif x.get("how") == "人名锚" and x.get("conf", 0) >= 0.5:
            anchor.add((y, off))

    path = DATA / "vol1_buyuan_entries_v2.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    n_fb = n_anchor = n_skip_page = 0
    for e in entries:
        y, off = e["year"], e.get("office")
        if not off or y not in (in_scope | PAGE_VERIFIED_YEARS):
            continue
        if (y, off) in fallback and (y, off) not in anchor:
            e["office_status"] = "row-order"
            n_fb += 1
        elif (y, off) in anchor:
            e["office_status"] = "name-anchor"
            n_anchor += 1
        elif y in PAGE_VERIFIED_YEARS:
            e["office_status"] = "page-verified"
            n_skip_page += 1
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"无标签年 {len(years_in_scope)}（页核豁免 {len(PAGE_VERIFIED_YEARS)}）")
    print(f"office_status: row-order {n_fb} 条 / name-anchor {n_anchor} 条 / page-verified {n_skip_page} 条")
    print("分布:", dict(Counter(e.get("office_status") for e in entries)))


if __name__ == "__main__":
    main()
