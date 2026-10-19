"""D-04 1546 页码错位核对：数据把「1545 页」的行放到了 1546 名下（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

out = ["## 1544–1547 兵部与總督京儲（数据）"]
for y in (1544, 1545, 1546, 1547):
    for off in ("兵部", "總督京儲"):
        got = [(r["person"], r.get("note", "")[:26], r.get("src"), r.get("book_page"))
               for r in rows if r["year"] == y and r["office"] == off]
        out.append(f"{y} {off}: {got}")

out.append("")
out.append("## 原书转写")
BOOK = {
    1545: "p580/PDF595  兵部：戴金/唐龍/路迎；總督京儲：陳經；都察院：周用",
    1546: "p581/PDF596  兵部：路迎/陳經；司属末行：陳經/張珩/王暐；都察院：周用/宋景",
    1547: "p582/PDF597  兵部：陳經/王以旂；刑部：聞淵/屠僑/喻茂堅；總督京儲：王暐/劉儲秀；都察院：宋景/王以旂/屠僑",
}
out.extend(BOOK.values())
(ROOT / "_d04_1546.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
