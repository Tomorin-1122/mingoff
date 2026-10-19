"""人工核验 6 条：内阁源条目（vol1_entries.json）定位（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_entries.json").read_text(encoding="utf-8"))
targets = {"李國楷", "李國𣚴", "李國槺", "李國檜", "錢溥", "錢士升",
           "劉一燝", "翟鑾", "蔣冕", "蔣晁", "蔣 晁", "劉珝", "劉翔"}
lines = []
for r in e:
    if r["person"] in targets:
        lines.append(f"{r['year']} {r['person']!r} note={r.get('note','')[:44]!r}")
print("\n".join(lines))
(ROOT / "docs/evidence/_renhe_entries.txt").write_text("\n".join(lines), encoding="utf-8")
