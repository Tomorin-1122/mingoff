"""人工核验 6 条：全库定位相关人名（繁简/异体宽搜，只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))

# 宽搜关键字
KEYS = {
    "1_李國": ["李國", "李槺", "李𣚴", "李國𣚴", "李國楷"],
    "2_錢溥": ["錢溥", "钱溥", "錢士升", "钱士升"],
    "3_劉一": ["劉一", "刘一"],
    "4_翟鑾": ["翟鑾", "翟銮"],
    "5_蔣冕": ["蔣冕", "蒋冕"],
    "6_劉珝翔": ["劉珝", "劉翔", "刘珝", "刘翔"],
}
out = []
for tag, names in KEYS.items():
    out.append(f"== {tag} ==")
    hits = [r for r in e if any(n in r["person"] or r["person"] in n for n in names)]
    if not hits:
        out.append("  （无命中）")
    for r in hits:
        out.append(f"  {r['year']} {r['office']} {r['person']!r} raw={r.get('raw_person')!r} "
                   f"note={r.get('note','')[:26]!r} page={r.get('book_page')}")
print("\n".join(out))
(ROOT / "docs/evidence/_renhe_locate.txt").write_text("\n".join(out), encoding="utf-8")
