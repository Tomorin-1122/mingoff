"""人工核验 #4：翟鑾 1540-1543 逐年 OCR 在场检查（只读）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
t = ((Path(__file__).resolve().parents[3] / "_scratch" / "mineru_neige" / "vol1_neige_a.md").read_text(encoding="utf-8")
     + (Path(__file__).resolve().parents[3] / "_scratch" / "mineru_neige" / "vol1_neige_b.md").read_text(encoding="utf-8"))
for y in (1540, 1541, 1542, 1543):
    k = t.find(f"({y})")
    s = t[k: t.find(f"({y + 1})")] if k >= 0 else ""
    print(y, "翟鑾 in:", "翟鑾" in s, "| len:", len(s))
