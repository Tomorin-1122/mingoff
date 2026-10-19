"""D-04 复核：对页无标签年的 parser 归属，用「对页合并 + 行序」解释数据到底怎么来的（只读）。"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

# 原书两页合并后的行（对页版式：标签在另一页，8 行）
PAGES = {
    1543: ["吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督京儲", "都察院"],
}

out = []
for y in (1543, 1544, 1545):
    d = collections.defaultdict(list)
    for r in rows:
        if r["year"] == y:
            d[r["office"]].append(r["person"])
    out.append(f"{y}: " + json.dumps({k: sorted(v) for k, v in d.items()}, ensure_ascii=False))
(ROOT / "_d04_1543b.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
