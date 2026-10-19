"""人工核验 #5 蒋冕：OCR「蔣 晁」疑为「蔣 冕」形近误识（只读核对）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
t = ((Path(__file__).resolve().parents[3] / "_scratch" / "mineru_neige" / "vol1_neige_a.md").read_text(encoding="utf-8")
     + (Path(__file__).resolve().parents[3] / "_scratch" / "mineru_neige" / "vol1_neige_b.md").read_text(encoding="utf-8"))
print("蔣 晁 出现次数:", t.count("蔣 晁"), " 蔣晁:", t.count("蔣晁"), " 蔣冕:", t.count("蔣冕"))
# 列出所有 蔣 晁 出现的年份
out = []
for m in re.finditer(r"蔣 晁", t):
    prev = re.findall(r"[（(](\d{4})[）)]", t[:m.start()])
    y = prev[-1] if prev else "?"
    ctx = re.sub(r"<[^>]+>", "", t[max(0, m.start() - 30): m.start() + 60]).replace("\n", "")
    out.append(f"{y}: …{ctx[:80]}…")
print("\n".join(out))
(ROOT / "docs/evidence/_renhe_jiangmian.txt").write_text("\n".join(out), encoding="utf-8")
