"""追踪 1633 錢士升 在条目链里哪一步丢了（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SCR = Path(__file__).resolve().parents[3] / "_scratch"
for f in ("vol1_entries_raw.json", "vol1_entries_canon.json", "vol1_entries_final.json"):
    d = json.loads((SCR / f).read_text(encoding="utf-8"))
    hits = [(r["year"], r["person"], r.get("note", "")[:20]) for r in d
            if r["year"] == 1633 and "錢" in r["person"]]
    print(f, hits)
