"""查 1631/1632 页（book 666/667 = PDF 681/682？）实际页码（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pages = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_pages.json").read_text(encoding="utf-8"))
for y in ("1630", "1631", "1632", "1633"):
    print(y, pages.get(y))
