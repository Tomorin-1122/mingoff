"""1550 年表里有没有倉場/京儲行？（只读，输出写 UTF-8 文件）"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
t = (ROOT.parent / "_scratch" / "mineru_buyuan" / "vol1_buyuan_a.md").read_text(encoding="utf-8")

out = []
for y in ("1549", "1550", "1551", "1552", "1553", "1556"):
    i = t.find(f"({y})")
    j = t.find(f"({int(y) + 1})")
    if i < 0:
        out.append(f"== {y}: not found ==")
        continue
    seg = t[i: j if j > i else i + 8000]
    hits = []
    for m in re.finditer(r"<tr>(.*?)</tr>", seg, re.S):
        r = m.group(1)
        if "倉場" in r or "京儲" in r:
            cells = [re.sub(r"<[^>]+>", "", c)[:50] for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            hits.append(" ┃ ".join(cells)[:150])
    out.append(f"== {y}: {len(hits)} rows with 倉場/京儲 ==")
    out.extend("  " + h for h in hits)

(ROOT / "docs/evidence/d04/_cc_rows.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
