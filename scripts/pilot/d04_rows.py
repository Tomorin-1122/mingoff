"""D-04/D41：看 1550/1551/1552 年表在 OCR 里的行结构，判断「總倉場」行从哪来（只读）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
t = (ROOT.parent / "_scratch" / "mineru_buyuan" / "vol1_buyuan_a.md").read_text(encoding="utf-8")

out = []
for y in ("1550", "1551", "1552", "1556", "1557"):
    i = t.find(f"({y})")
    if i < 0:
        out.append(f"== {y}: not found ==")
        continue
    seg = t[max(0, i - 300): i + 3000]
    tables = re.findall(r"<table>.*?</table>", seg, re.S)
    out.append(f"== {y} (tables={len(tables)}) ==")
    for tb in tables[:2]:
        rows = re.findall(r"<tr>(.*?)</tr>", tb, re.S)
        for r in rows[:12]:
            cells = [re.sub(r"<[^>]+>", "", c)[:40] for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            out.append("  ROW: " + " ┃ ".join(cells))

(ROOT / "docs/evidence/d04/_rows_1550s.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
