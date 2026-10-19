"""D-04：核对 1557 前后衙署标签在原书里的实际写法与起止年（按年份头逐表扫描）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
SCR = ROOT.parent / "_scratch" / "mineru_buyuan"
text = (SCR / "vol1_buyuan_a.md").read_text(encoding="utf-8") + (SCR / "vol1_buyuan_b.md").read_text(encoding="utf-8")

LABELS = ("總倉場", "總督倉場", "總會場", "總督京儲", "總督倉塲")
rows = []
for m in re.finditer(r"\((\d{4})\)", text):
    year = int(m.group(1))
    if not (1540 <= year <= 1645):
        continue
    seg = text[m.start(): m.start() + 6000]
    labels = [lab for lab in LABELS if f">{lab}<" in seg]
    rows.append((year, "/".join(labels) if labels else "（无标签/续页）"))

# 去重（同一年可能多次出现）
seen = {}
for y, lab in rows:
    seen.setdefault(y, lab)
lines = [f"{y}: {seen[y]}" for y in sorted(seen)]
(ROOT / "docs/evidence/d04/_labels_1540_1644.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
