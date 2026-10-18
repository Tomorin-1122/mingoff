# -*- coding: utf-8 -*-
"""用罗马字 + 姓氏块双重约束，纠正 INDEX 里的姓氏错字。

原理：
  1. 正文里每个姓只出现在固定页段（如 卞 18–19、卜 5–6）；
  2. INDEX 的同一条目给了罗马字（如 Pien = 卞）；
  3. 若某名的页码落在本姓页段之外，却在**同罗马字**的另一姓页段之内，
     且这样的候选姓唯一 —— 判为姓氏 OCR 错字。

只处理「唯一候选」，多解一律不动。用法: python mrzj_roman_fix.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")


def first_syl(roman: str) -> str:
    r = (roman or "").strip()
    if not r:
        return ""
    return r.split()[0].lower().replace("'", "").replace("’", "")


def main():
    cat = json.loads((BASE / "index_catalog.json").read_text(encoding="utf-8"))
    heads = json.loads((BASE / "body_heads_corrected.json").read_text(encoding="utf-8"))
    surname_pages = defaultdict(list)
    for r in heads:
        for h in r["heads"]:
            surname_pages[h[0]].append(r["printed_page"])
    span = {k: (min(v), max(v)) for k, v in surname_pages.items()}

    def in_block(s: str, p: int) -> bool:
        lo, hi = span.get(s, (0, -1))
        return lo <= p <= hi

    trusted = [c for c in cat if c["roman"] and in_block(c["name"][0], c["pages"][0])]
    syl_sur = defaultdict(Counter)
    for c in trusted:
        syl_sur[first_syl(c["roman"])][c["name"][0]] += 1

    fixes, ambiguous = [], 0
    for c in cat:
        if not c["roman"]:
            continue
        p = c["pages"][0]
        if in_block(c["name"][0], p):
            continue
        cands = [s for s in syl_sur.get(first_syl(c["roman"]), {}) if in_block(s, p)]
        if len(cands) == 1:
            new = cands[0] + c["name"][1:]
            if new != c["name"]:
                fixes.append(
                    {
                        "old": c["name"],
                        "new": new,
                        "page": p,
                        "roman": c["roman"],
                        "from_sur": c["name"][0],
                        "to_sur": cands[0],
                    }
                )
        elif len(cands) > 1:
            ambiguous += 1

    (BASE / "roman_surname_fixes.json").write_text(
        json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"可定姓氏 {len(fixes)} 条；罗马字多解未动 {ambiguous} 条")
    for f in fixes[:20]:
        print(f"  p{f['page']:<4} {f['old']} → {f['new']}   (roman={f['roman']})")


if __name__ == "__main__":
    main()
