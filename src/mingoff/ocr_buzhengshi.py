# -*- coding: utf-8 -*-
"""承宣布政使年表解析（2026-11-20）。复用 ocr_zongdu 区域带管线 + 双栏分页预处理。

版式（vol4 pdf7 实证）：
  1. **一页两年双栏**：左栏（x≈180-700）年份 A 带省标签（北平/山東/山西/河南/陕西/
     四川/江西/湖廣/浙江/福建/廣東/廣西/雲南/貴州/交阯），右栏（x≈1000-1450）年份 B
     无标签、共用左栏 band y 位；两栏年份头分立（x≈477/1110）→ 按双头 x 中点分栏；
  2. 单年页（单年份头）不分栏；书页 = PDF + 3177（锚点 ·3184）；
  3. band 规则同总督（名字行属下方首标签）；省名正名按印本（剥承宣布政使司等前缀）。
虚拟页键：page*2-1=左栏/整页，page*2=右栏。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from mingoff.ocr_jingqing import RE_YEAR_FULL, RE_YEAR_BARE
import mingoff.ocr_zongdu as zd

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "_scratch/vol34/raw_buzhengshi"
OUT = ROOT / "src/mingoff/data/vol4_buzhengshi_entries.json"
REVIEW = ROOT / "src/mingoff/data/vol4_buzhengshi_review.json"
LO, HI = 7, 393
PAGE_OFFSET = 3177
DATASET = "承宣布政使年表"


def load_split_pages() -> dict[int, list]:
    """双年份头页按 x 中点拆左右虚拟栏；键 page*2-1（左/整页）、page*2（右栏）。"""
    pages: dict[int, list] = {}
    for p in range(LO, HI + 1):
        f = RAW / f"p{p}.jsonl"
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
        oc = d["result"]["ocrResults"][0]["prunedResult"]
        rows = []
        for t, b in zip(oc["rec_texts"], oc["rec_boxes"]):
            x, y = int(b[0]), int(b[1])
            if x > 1150 and 1700 < y < 1850:
                zd.wm_skipped[0] += 1
                continue
            rows.append((t.strip(), x, y))
        hdrs = []
        for t, x, y in rows:
            if y > 400:
                continue
            m = RE_YEAR_FULL.search(t) or RE_YEAR_BARE.search(t)
            if m:
                yr = int(m.group(2)) if RE_YEAR_FULL.search(t) else int(m.group(1))
                hdrs.append((x, yr))
        hdrs.sort()
        if len(hdrs) >= 2 and hdrs[-1][0] - hdrs[0][0] > 500:
            mid = (hdrs[0][0] + hdrs[-1][0]) // 2
            pages[p * 2 - 1] = [r for r in rows if r[1] < mid]
            pages[p * 2] = [r for r in rows if r[1] >= mid]
        else:
            pages[p * 2 - 1] = rows
    return pages


def main():
    # 接管 zd 管线：换 loader/范围/输出，虚拟键区间给 zd.parse
    zd.load_pages = load_split_pages
    zd.LO, zd.HI = LO * 2 - 1, HI * 2
    zd.VOCAB_MIN = 25
    zd.BAND_RULE = "nearest"   # 布政使名字与标签同行（±20px），取最近标签行
    zd.PREFIX_STRIP = zd.PREFIX_STRIP + ("承宣布政使司", "布政使司")
    zd.SKIP_TEXT = zd.SKIP_TEXT | {"承宣布政使年表", "承宣布政使司年表",
                                   "布政使年表", "官歷", "官歷表"}
    entries, review, stats, ymap = zd.parse()
    # 虚拟键(page*2-1/page*2) → 真实 PDF 页 → 书页（PDF+3177）
    for e in entries:
        key = e["book_page"] - zd.PAGE_OFFSET
        e["book_page"] = (key + 1) // 2 + PAGE_OFFSET
    for r in review:
        if r.get("book_page"):
            key = r["book_page"] - zd.PAGE_OFFSET
            r["book_page"] = (key + 1) // 2 + PAGE_OFFSET
    meta = {
        "dataset": DATASET,
        "source": "张德信《明代职官年表》第4册 PDF 7–393（书页 3184–3570）；"
                  "PaddleOCR 行框解析（ocr_buzhengshi.py，一页两年双栏拆分）",
        "year_range": [min(ymap.values()), max(ymap.values())] if ymap else [],
        "page_offset": PAGE_OFFSET,
        "band_rule": "左栏带省标签、右栏无标签共用 y 带；band=名字行下方首标签",
        "stats": {**dict(stats), "entries": len(entries), "review": len(review)},
    }
    OUT.write_text(json.dumps({"meta": meta, "entries": entries},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps({"meta": meta, "items": review},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print("stats:", json.dumps(meta["stats"], ensure_ascii=False))
    for y in (1376, 1430, 1644):
        es = [(e["office"], e["person"], e["note"][:12])
              for e in entries if e["year"] == y]
        print(f"--- {y} ({len(es)}条) ---")
        for o, p, n in es[:12]:
            print(f"  {o}: {p} {n}")


if __name__ == "__main__":
    main()
