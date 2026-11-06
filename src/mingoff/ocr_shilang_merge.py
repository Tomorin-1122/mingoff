# -*- coding: utf-8 -*-
"""合并部院侍郎年表逐页转录 → 提取物（试点）。

输入：_scratch/mineru_nianbiao/shilang_transcribe/sl*.json
输出：src/mingoff/data/vol1_shilang_entries.json

版式要点（2026-10-22 实测）：
  - 一行一衙，左端竖排衙署名（吏部…都察院，另有「易州山廠提督」）；
  - 格内人多时折列：有横排（洪武初，一人一列）也有竖排（成化后，上下列），**同一表内混用**；
  - 原书人名后偶带 (左)/(右)/(文) 标注，原样存 tag，不推断左右侍郎。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_scratch" / "mineru_nianbiao" / "shilang_transcribe"
OUT = ROOT / "src" / "mingoff" / "data" / "vol1_shilang_entries.json"


def main() -> int:
    pages = []
    for f in sorted(SRC.glob("sl*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d.get("pages", []):
            p["_agent"] = d.get("agent") or f.stem
            pages.append(p)
    pages.sort(key=lambda p: p["pdf_page"])

    entries = []
    for p in pages:
        for row in p.get("rows", []):
            for per in row.get("persons", []):
                entries.append({
                    "year": p["year"],
                    "era": p.get("era"),
                    "office": row.get("office"),
                    "person": per.get("name"),
                    "tag": per.get("tag"),
                    "note": per.get("note") or "",
                    "unclear": bool(per.get("unclear")),
                    "book_page": p.get("book_page"),
                    "pdf_page": p["pdf_page"],
                    "layout": p.get("layout"),
                    "src": "transcribe:" + p["_agent"],
                })

    years = sorted({e["year"] for e in entries})
    payload = {
        "meta": {
            "dataset": "部院侍郎年表（京師）· 试点",
            "source": "张德信《明代職官年表》册1 正文 681–980（PDF 696–995）",
            "method": "逐页人工转录（子代理看页图），OCR 仅作反证",
            "year_range": [min(years), max(years)],
            "stats": {
                "entries": len(entries),
                "years": len(years),
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "unclear": sum(1 for e in entries if e["unclear"]),
                "pages": len(pages),
                "offices": len({e["office"] for e in entries}),
            },
            "note": "试点仅 2 页（1368 横排 / 1470 折列）。左右侍郎不单独建字段，原书 (左)/(右) 标注存 tag，其余见注文。",
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"条目 {len(entries)}／年 {len(years)}／人 {payload['meta']['stats']['persons']}"
          f"／有注 {payload['meta']['stats']['with_note']}／unclear {payload['meta']['stats']['unclear']}")
    for y in years:
        es = [e for e in entries if e["year"] == y]
        print(f"  {y} ({len(es)}) " + " ".join(f'{e["office"]}:{e["person"]}' for e in es)[:150])
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
