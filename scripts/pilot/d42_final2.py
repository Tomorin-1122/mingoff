"""D42 终验：聞淵 1547 两衙条目、32 组「年×衙」一致性（只读，UTF-8 输出）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
lines = []
for r in e:
    if r["year"] == 1547 and r["person"] == "聞淵":
        lines.append(f"1547 聞淵 @ {r['office']}: {r['note'][:40]!r} status={r.get('note_status')}")
# 1547 刑部 = 聞淵/屠僑/喻茂堅？
xq = sorted(r["person"] for r in e if r["year"] == 1547 and r["office"] == "刑部")
lines.append(f"1547 刑部 = {xq}  {'✅' if xq == ['喻茂堅', '屠僑', '聞淵'] else '⚠'}")
(ROOT / "docs/evidence/d04/_d42_final2.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
