# -*- coding: utf-8 -*-
"""把目录对校出的 145 条定向修正回写到正文语料，再重建与复检。

不改原始 OCR 产物（out/*.md 保持原样），只在合并层落一份
corpus_corrected.json，保证可回溯、可撤销。

用法: python mrzj_apply_fixes.py
产物:
  _scratch/mineru_mrzj/corrections.json          回写清单
  _scratch/mineru_mrzj/corpus_corrected.json     修正后语料
  _scratch/mineru_mrzj/body_heads_corrected.json 修正后条目人名
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")


def main():
    checks = json.loads((BASE / "index_check.json").read_text(encoding="utf-8"))
    fixes = [x for x in checks if x["status"] == "fixed"]
    corpus = json.loads((BASE / "corpus.json").read_text(encoding="utf-8"))

    by_page: dict[int, list[tuple[str, str]]] = {}
    for f in fixes:
        by_page.setdefault(f["pages"][0], []).append((f["fixed_to"], f["name"]))

    applied = []
    for p in corpus:
        pairs = by_page.get(p["printed_page"])
        if not pairs:
            continue
        txt = p["text"]
        for wrong, right in pairs:
            n = txt.count(wrong)
            if n:
                txt = txt.replace(wrong, right)
                applied.append({"page": p["printed_page"], "wrong": wrong, "right": right, "n": n})
        p["text"] = txt

    (BASE / "corrections.json").write_text(
        json.dumps(applied, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (BASE / "corpus_corrected.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with (BASE / "mrzj_fulltext_corrected.txt").open("w", encoding="utf-8") as fh:
        for p in corpus:
            fh.write(f"\n\n===== 正文 p{p['printed_page']} (PDF {p['pdf_page']}) {p['group']} =====\n")
            fh.write(p["text"])

    print(f"清单 {len(fixes)} 条，实际改动 {len(applied)} 处")
    hit = [a for a in applied if a["n"] > 1]
    print(f"多处命中的 {len(hit)} 条: {[(a['page'], a['wrong'], a['n']) for a in hit[:8]]}")


if __name__ == "__main__":
    main()
