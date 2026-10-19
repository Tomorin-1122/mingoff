"""人工核验 6 条：这些名字多数在 OCR 原文里查（他们可能在没入数据的页/或被丢弃），定位页码（只读）。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SCR = Path(__file__).resolve().parents[3] / "_scratch" / "mineru_buyuan"
text = ((SCR / "vol1_buyuan_a.md").read_text(encoding="utf-8")
        + (SCR / "vol1_buyuan_b.md").read_text(encoding="utf-8"))

NAMES = {
    "1_李國𣚴": ["李國𣚴", "李國槺", "李國楷", "李國"],
    "2_錢溥": ["錢溥", "钱溥"],
    "2b_錢士升": ["錢士升", "钱士升"],
    "3_劉一燝": ["劉一燝", "劉一焴", "刘一燝"],
    "5_蔣冕": ["蔣冕", "蒋冕"],
    "6_劉珝": ["劉珝", "劉翔", "刘珝"],
}

def year_of(pos: int) -> int | None:
    # 往前找最近的年份头
    best = None
    for m in re.finditer(r"[（(](\d{4})[）)]", text[:pos]):
        best = int(m.group(1))
    return best

out = []
for tag, names in NAMES.items():
    out.append(f"== {tag} ==")
    for n in names:
        idxs = [m.start() for m in re.finditer(n, text)]
        out.append(f"  {n}: {len(idxs)} 次")
        for i in idxs[:6]:
            y = year_of(i)
            ctx = re.sub(r"<[^>]+>", "", text[max(0, i - 30): i + 40]).replace("\n", "")
            out.append(f"    ~year={y} …{ctx}…")
print("\n".join(out))
(ROOT / "docs/evidence/_renhe_ocr.txt").write_text("\n".join(out), encoding="utf-8")
