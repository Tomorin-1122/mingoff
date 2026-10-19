"""人工核验：钱士升 1637-1638 在场检查 + 受影响条目计数（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SCR = Path(__file__).resolve().parents[3] / "_scratch" / "mineru_neige"
t = ((SCR / "vol1_neige_a.md").read_text(encoding="utf-8")
     + (SCR / "vol1_neige_b.md").read_text(encoding="utf-8"))
for y in (1636, 1637, 1638):
    i = t.find(f"({y})")
    j = t.find(f"({y + 1})")
    seg = t[i: j if j > i else i + 3000]
    print(y, "錢士升 in:", "錢士升" in seg)

ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_entries.json").read_text(encoding="utf-8"))
affected = [r for r in e if r["person"] in ("錢溥", "李國楷", "蔣晁", "劉翔")]
print("affected entries:", len(affected), [(r["year"], r["person"]) for r in affected])
