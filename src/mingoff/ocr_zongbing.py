# -*- coding: utf-8 -*-
"""镇守总兵官年表解析（2026-11-20）。复用 ocr_zongdu 区域带管线。

版式（pdf709 实证）：与总督年表同构——区域标签（雲南/薊州/宣府…）在带底，
名字行属其下方第一条标签；一年一页为主；书页 = PDF + 2215（锚点 2924）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import mingoff.ocr_zongdu as zd

ROOT = Path(__file__).resolve().parents[2]

zd.LO, zd.HI = 709, 967
zd.RAW = ROOT / "_scratch/vol34/raw_zongbing"
zd.OUT = ROOT / "src/mingoff/data/vol3_zongbing_entries.json"
zd.REVIEW = ROOT / "src/mingoff/data/vol3_zongbing_review.json"
zd.VOCAB_MIN = 25
zd.MIN_WORD_LABELS = 1   # 总兵页标签稀疏（靖难年间单区域页）
zd.LABEL_JOIN_GAP = 60   # 总兵 band 113-125px；两行复合标签(鎮守+region)约 50px
zd.PREFIX_STRIP = zd.PREFIX_STRIP + ("鎮守", "總兵", "协守", "協守", "分守")
zd.SKIP_TEXT = zd.SKIP_TEXT | {"鎮守總兵官年表", "总兵官年表"}
DATASET = "镇守总兵官年表"


def main():
    entries, review, stats, ymap = zd.parse()
    meta = {
        "dataset": DATASET,
        "source": "张德信《明代职官年表》第3册 PDF 709–967（书页 2924–3182）；"
                  "PaddleOCR 行框解析（ocr_zongbing.py 复用 ocr_zongdu 管线）",
        "year_range": [min(ymap.values()), max(ymap.values())] if ymap else [],
        "page_offset": 2215,
        "band_rule": "名字行属其下方第一条区域标签；官职正名剥鎮守/總兵等前缀",
        "stats": {**dict(stats), "entries": len(entries), "review": len(review)},
    }
    zd.OUT.write_text(json.dumps({"meta": meta, "entries": entries},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    zd.REVIEW.write_text(json.dumps({"meta": meta, "items": review},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print("stats:", json.dumps(meta["stats"], ensure_ascii=False))
    for y in (1399, 1550, 1644):
        es = [(e["office"], e["person"], e["note"][:12])
              for e in entries if e["year"] == y]
        print(f"--- {y} ({len(es)}条) ---")
        for o, p, n in es[:10]:
            print(f"  {o}: {p} {n}")


if __name__ == "__main__":
    main()
