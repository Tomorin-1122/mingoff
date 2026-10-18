# -*- coding: utf-8 -*-
"""正文侧：每页抽出「条目开头的人名」（用于与 INDEX 目录对校）。

判据沿用正文解析那套：人名前必须是引文收尾（`)` / `卷/页` / `。`），
人名后必须跟（生卒）/字/號/初名/以字行/，X人。
输出 _scratch/mineru_mrzj/body_heads.json
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
CJK = r"\u4e00-\u9fff"
CAND = re.compile(rf"([{CJK}]{{2,4}})(?=，|字|號|初名|以字行|（\d{{3}}|\(\d{{3}})")
DATE_PAREN = re.compile(r"[（(]\d{3,4}\s*[—–\-]*\s*\d{0,4}[）)]$")
CITE_TAIL = re.compile(r"(?:[)）]|/\d+[下上]?|\d+[下上]|[。】])$")
NAME_STOP = set("字號初以改別晚又自人氏妻母父弟男")
# 书名/篇名常见尾字，避免把出处当成条目
TITLE_TAIL = set("碑銘傳序表狀錄志記集稿考略說議疏跋贊頌賦詩文書公君母太父")
# 3 字以上以「氏」收尾的多为「母王氏」这类，排除；2 字「王氏」保留（本身是条目）


def heads(text: str) -> list[str]:
    out = []
    for m in CAND.finditer(text):
        name = m.group(1)
        s = m.start()
        if name[0] in NAME_STOP or name[-1] in TITLE_TAIL:
            continue
        if len(name) >= 3 and name[-1] == "氏":
            continue
        if s == 0:
            out.append(name)
            continue
        left = text[max(0, s - 24) : s]
        if not CITE_TAIL.search(left):
            continue
        if left.endswith((")", "）")) and DATE_PAREN.search(left):
            continue
        out.append(name)
    # 去相邻重复
    dedup = []
    for n in out:
        if not dedup or dedup[-1] != n:
            dedup.append(n)
    return dedup


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "corpus.json"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / "body_heads.json"
    pages = json.loads(src.read_text(encoding="utf-8"))
    rows = []
    for p in pages:
        hs = heads(p["text"])
        rows.append({"printed_page": p["printed_page"], "group": p["group"], "heads": hs})
    dst.write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    tot = sum(len(r["heads"]) for r in rows)
    print(f"页 {len(rows)}  条目人名 {tot}  平均 {tot/len(rows):.1f}/页")
    print("样例:", rows[18]["heads"][:10])
    print("->", dst)


if __name__ == "__main__":
    main()
