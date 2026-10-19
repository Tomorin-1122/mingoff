"""检查 D42 修正后 1547 刑部/都察院 的注文归属（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
lines = []
for r in e:
    if r["year"] == 1547 and r["office"] in ("刑部", "都察院"):
        lines.append(f"{r['office']} {r['person']} | {r['note'][:44]} | {r.get('note_status')} | {r.get('note_source')}")
(ROOT / "docs/evidence/d04/_p1547notes.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
