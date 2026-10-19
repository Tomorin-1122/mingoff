"""D-04 收尾核对：1631/1632 原书标签写法（只读）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
t = (ROOT.parent / "_scratch" / "mineru_buyuan" / "vol1_buyuan_b.md").read_text(encoding="utf-8")

# 1631 表（PDF 681）标签列原文
out = []
for y in ("1630", "1631", "1632", "1633"):
    i = t.find(f"({y})")
    seg = t[i:i + 6000]
    labels = re.findall(r"<td[^>]*>\s*([^<]*倉場[^<]*)\s*</td>", seg)
    out.append(f"{y}: {[l.strip() for l in labels[:3]]}")
(ROOT / "docs/evidence/d04/_label_1631.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
