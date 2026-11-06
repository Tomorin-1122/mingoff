# -*- coding: utf-8 -*-
"""合并中书省逐页转录（子代理产物）→ 提取物，并与 OCR 解析结果交叉校验。

输入：_scratch/mineru_nianbiao/zhongshu_transcribe/zs*.json
输出：src/mingoff/data/vol1_zhongshu_entries.json
      src/mingoff/data/vol1_zhongshu_check.json（与 OCR 版的人名差异、同期重出）

纪律：转录为准，OCR 只作反证。差异一律列出，不自动合并。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_scratch" / "mineru_nianbiao" / "zhongshu_transcribe"
OUT = ROOT / "src" / "mingoff" / "data" / "vol1_zhongshu_entries.json"
CHECK = ROOT / "src" / "mingoff" / "data" / "vol1_zhongshu_check.json"


def main() -> int:
    pages = []
    for f in sorted(SRC.glob("zs*.json")):
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
                    "side": row.get("side"),
                    "person": per.get("name"),
                    "note": per.get("note") or "",
                    "unclear": bool(per.get("unclear")),
                    "book_page": p.get("book_page"),
                    "pdf_page": p["pdf_page"],
                    "page_has_labels": p.get("has_labels"),
                    "src": "transcribe:" + p["_agent"],
                })

    # 同期同一人在多行出现（一人兼两职 or 转录重出）
    dup = {}
    for e in entries:
        k = (e["year"], e["person"])
        dup.setdefault(k, []).append(f'{e["office"]}{("·" + e["side"]) if e["side"] else ""}')
    multi = [{"year": k[0], "person": k[1], "rows": v} for k, v in dup.items() if len(set(v)) > 1]

    years = sorted({e["year"] for e in entries})
    payload = {
        "meta": {
            "dataset": "中書省大臣年表",
            "source": "张德信《明代職官年表》册1 正文 1–14（PDF 16–29）",
            "method": "逐页人工转录（7 个子代理分工，按页图），OCR 仅作反证",
            "year_range": [min(years), max(years)],
            "stats": {
                "entries": len(entries),
                "years": len(years),
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "unclear": sum(1 for e in entries if e["unclear"]),
                "pages": len(pages),
                "rows": sum(len(p.get("rows", [])) for p in pages),
            },
            "note": "注文按原书逐人归位；无标签页已标 page_has_labels=false，行序为推定。",
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # 与 OCR 版对比（若旧文件存在，先备份再比）
    ocr_person = {}
    ocr_file = ROOT / "src" / "mingoff" / "data" / "vol1_zhongshu_ocr.json"
    if ocr_file.exists():
        old = json.loads(ocr_file.read_text(encoding="utf-8"))
        for e in old.get("entries", []):
            ocr_person.setdefault(e["year"], set()).add(e["person"])
    mine = {}
    for e in entries:
        mine.setdefault(e["year"], set()).add(e["person"])
    diff = []
    for y in years:
        a, b = mine.get(y, set()), ocr_person.get(y, set())
        if a ^ b:
            diff.append({"year": y, "only_transcribe": sorted(a - b), "only_ocr": sorted(b - a)})

    CHECK.write_text(json.dumps({"multi_row_same_year": multi, "vs_ocr": diff},
                                ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"条目 {len(entries)}／年份 {len(years)}／人 {payload['meta']['stats']['persons']}"
          f"／有注 {payload['meta']['stats']['with_note']}／unclear {payload['meta']['stats']['unclear']}")
    print(f"同期重出 {len(multi)} 组；与 OCR 人名差异 {len(diff)} 年")
    for y in years:
        es = [e for e in entries if e["year"] == y]
        print(f"  {y} ({len(es):2d}) " + "  ".join(
            f'{e["person"]}' + (f'@{e["office"]}{("·"+e["side"]) if e["side"] else ""}' if False else "")
            for e in es)[:120])
    if diff:
        print("\n[与 OCR 差异]")
        for d in diff:
            print(f'  {d["year"]}: 转录独有 {d["only_transcribe"]} / OCR 独有 {d["only_ocr"]}')
    if multi:
        print("\n[同期重出]")
        for m in multi:
            print(f'  {m["year"]} {m["person"]}: {m["rows"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
