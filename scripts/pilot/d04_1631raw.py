"""1631/1632 OCR 原文里「督倉場」行的原始形态（只读）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
t = (ROOT.parent / "_scratch" / "mineru_buyuan" / "vol1_buyuan_b.md").read_text(encoding="utf-8")
out = []
i = t.find("(1631)")
j = t.find("(1633)")
seg = t[i:j]
for m in re.finditer(r"<tr>(.*?)</tr>", seg, re.S):
    r = m.group(1)
    if "倉場" in r:
        out.append(re.sub(r"<[^>]+>", " ┃ ", r)[:200])
(ROOT / "docs/evidence/d04/_1631raw.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
