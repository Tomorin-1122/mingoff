"""D-11 建议分布摘要（只读）。"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_d11_review.json").read_text(encoding="utf-8"))
rows = d["rows"]
how = collections.Counter(r["how"] for r in rows)
hi = [r for r in rows if r["conf"] >= 0.9]
mid = [r for r in rows if 0.5 <= r["conf"] < 0.9]
lo = [r for r in rows if r["conf"] < 0.5]
lines = [
    f"how 分布: {json.dumps(how, ensure_ascii=False)}",
    f"conf>=0.9: {len(hi)}  0.5–0.9: {len(mid)}  <0.5: {len(lo)}",
    "",
    "样例（conf>=0.9 前 12 条）:",
]
for r in hi[:12]:
    lines.append(f"  {r['year']} 行{r['row']} {'/'.join(r['names'])} -> {r['suggest_office']} ({r['conf']})")
lines.append("")
lines.append("样例（0.5–0.9 前 8 条）:")
for r in mid[:8]:
    lines.append(f"  {r['year']} 行{r['row']} {'/'.join(r['names'])} -> {r['suggest_office']} ({r['conf']})")
(ROOT / "docs/evidence/d11/_d11_dist.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
