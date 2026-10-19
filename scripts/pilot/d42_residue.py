"""D42 残留两处：1547 刑部 聞淵、1558 總倉場 高燿（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
for r in e:
    if r["year"] == 1547 and r["office"] == "刑部":
        print(f"1547 刑部 {r['person']}: {r['note'][:40]!r}")
    if r["year"] == 1558 and "倉場" in r["office"]:
        print(f"1558 {r['office']} {r['person']}: {r['note'][:40]!r} src={r.get('src')}")
