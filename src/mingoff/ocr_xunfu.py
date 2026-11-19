# -*- coding: utf-8 -*-
"""巡抚年表解析（2026-11-19）。复用 ocr_zongdu 通用区域带管线。

版式差异（pdf311/312/340 实证）：
  * 一年多为一页对：**首页带区域标签**（江西/浙江/湖廣/河南山西/北直隸山東/南直隸蘇松…），
    **续页无标签且人名左移 x~180**（首页 x≈380/1000 双槽）——ocr_zongdu.parse 已按
    「有无本页标签」切换内容区 x 过滤，续页人名不丢；
  * 部分年份单页（一年一页），部分双页（ymap 同年相邻对）；书页 = PDF + 2215；
  * 区域标签为 2-5 字整词（个别纵排），官职正名按印本（剥總督/總理等前缀规则同样适用）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import mingoff.ocr_zongdu as zd

ROOT = Path(__file__).resolve().parents[2]

zd.LO, zd.HI = 311, 707
zd.VOCAB_MIN = 25          # 巡抚型：续页人名也在 x<300，标签词靠全卷词频确认
zd.SKIP_TEXT = zd.SKIP_TEXT | {"巡撫年表"}
zd.OUT = ROOT / "src/mingoff/data/vol3_xunfu_entries.json"
zd.REVIEW = ROOT / "src/mingoff/data/vol3_xunfu_review.json"
DATASET = "巡抚年表"


def main():
    entries, review, stats, ymap = zd.parse()
    meta = {
        "dataset": DATASET,
        "source": "张德信《明代职官年表》第3册 PDF 311–707（书页 2526–2922）；"
                  "PaddleOCR 行框解析（ocr_xunfu.py 复用 ocr_zongdu 管线）",
        "year_range": [min(ymap.values()), max(ymap.values())],
        "page_offset": zd.PAGE_OFFSET,
        "band_rule": "名字行属其下方第一条区域标签；年首页带标签、续页无标签"
                     "（继承首页 schema，人名左移 x~180）",
        "stats": {**dict(stats), "entries": len(entries), "review": len(review)},
    }
    zd.OUT.write_text(json.dumps({"meta": meta, "entries": entries},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    zd.REVIEW.write_text(json.dumps({"meta": meta, "items": review},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print("stats:", json.dumps(meta["stats"], ensure_ascii=False))
    for y in (1430, 1459, 1644):
        es = [(e["office"], e["person"], e["note"][:14])
              for e in entries if e["year"] == y]
        print(f"--- {y} ({len(es)}条) ---")
        for o, p, n in es[:14]:
            print(f"  {o}: {p} {n}")


if __name__ == "__main__":
    main()
