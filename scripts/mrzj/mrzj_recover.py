# -*- coding: utf-8 -*-
"""对 name_missing 做定向找回：用「姓氏块 + 一字差 + 条目开头」三重约束。

分类依据（见 index_check_after.json）：
  - 页码越界：目录页不在该姓氏的正文区间内 → 多半是目录页码 OCR 错
  - 页在区间内：名字本身错 → 在同页/邻页找同姓近名
  - 姓氏全无：连姓都没出现过 → 目录名字严重错，留给人工

用法: python mrzj_recover.py
产物: _scratch/mineru_mrzj/mrzj_recover.json  + 打印摘要
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
CJK = r"\u4e00-\u9fff"
VARIANTS = str.maketrans({"黄": "黃", "吕": "呂", "杨": "楊", "吴": "吳", "苏": "蘇", "郑": "鄭", "颜": "顏"})


def edit1(a: str, b: str) -> bool:
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :]


def main():
    checks = json.loads((BASE / "index_check_after.json").read_text(encoding="utf-8"))
    heads = json.loads((BASE / "body_heads_corrected.json").read_text(encoding="utf-8"))
    corpus = {
        p["printed_page"]: p["text"].translate(VARIANTS)
        for p in json.loads((BASE / "corpus_corrected.json").read_text(encoding="utf-8"))
    }
    head_by_page = {r["printed_page"]: set(r["heads"]) for r in heads}

    surname_pages = defaultdict(list)
    for r in heads:
        for h in r["heads"]:
            surname_pages[h[0]].append(r["printed_page"])
    for k in surname_pages:
        surname_pages[k] = sorted(set(surname_pages[k]))

    miss = [x for x in checks if x["status"] == "name_missing"]
    out = []
    stat = Counter()
    for x in miss:
        name = x["name"].translate(VARIANTS)
        pg = x["pages"][0]
        s = name[0]
        pages = surname_pages.get(s, [])
        if not pages:
            stat["姓氏全无"] += 1
            out.append({**x, "recover": None, "why": "姓氏全无"})
            continue
        in_range = pages[0] <= pg <= pages[-1]
        # 候选页：优先原页及邻近，其次整个姓氏块
        near = [p for p in pages if abs(p - pg) <= 2]
        cand_pages = near or sorted(pages, key=lambda p: abs(p - pg))[:12]
        best = None
        for p in cand_pages:
            for h in head_by_page.get(p, set()):
                if h[0] != s or h == name:
                    continue
                if edit1(h, name):
                    score = (0 if abs(p - pg) <= 2 else 1, len(set(h) ^ set(name)) if False else 0)
                    if best is None or score < best[0]:
                        best = (score, h, p)
        if best:
            stat["找回" if in_range else "页码修正"] += 1
            out.append({**x, "recover": {"name": best[1], "page": best[2]}, "why": "in_range" if in_range else "page_out"})
        else:
            stat["无法找回"] += 1
            out.append({**x, "recover": None, "why": "in_range_no_cand" if in_range else "page_out_no_cand"})

    (BASE / "mrzj_recover.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("name_missing", len(miss), dict(stat))
    for x in [y for y in out if y["recover"]][:12]:
        print(f"  {x['name']}(p{x['pages'][0]}) → {x['recover']['name']}(p{x['recover']['page']}) [{x['why']}]")


if __name__ == "__main__":
    main()
