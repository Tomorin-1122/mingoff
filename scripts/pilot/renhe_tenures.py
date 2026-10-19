"""人工核验 6 条：查修正面（site 数据）与官方 buyuan（有的问题可能在 tenures 段而非 entries）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
b = json.loads((ROOT / "src/mingoff/data/official_buyuan.json").read_text(encoding="utf-8"))
c = json.loads((ROOT / "src/mingoff/data/official_cabinet.json").read_text(encoding="utf-8"))

NAMES = ["李國𣚴", "李國槺", "李國楷", "李國", "錢溥", "錢士升", "劉一燝", "劉一焴",
         "翟鑾", "蔣冕", "劉珝", "劉翔"]
out = []
for tag, doc in (("部院", b), ("内阁", c)):
    for t in doc["tenures"]:
        if any(n in t["person"] or t["person"] in n for n in NAMES):
            out.append(f"[{tag}] {t['person']} {t.get('person_label','')} "
                       f"{t['office']} {t['start_year']}–{t['end_year']} "
                       f"years={t.get('years', [])[:8]}")
print("\n".join(out) if out else "（十部数据无命中）")
(ROOT / "docs/evidence/_renhe_tenures.txt").write_text("\n".join(out), encoding="utf-8")
