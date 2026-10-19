"""1547 聞淵 注文 vs 原书（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
for r in e:
    if r["year"] == 1547 and r["person"] == "聞淵":
        print(f"{r['office']}: note={r['note']!r} status={r.get('note_status')} src={r.get('note_source')}")
