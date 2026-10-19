"""D-04 原始条目快查：某年某衙有哪些条目、注文有没有提到某人（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]


def show(year, office=None, needle=None):
    hit = [r for r in rows if r["year"] == year and (office is None or r["office"] == office)]
    if needle:
        hit = [r for r in hit if needle in (r.get("note") or "") or needle in r["person"]]
    out = [f"== {year} {office or '全部'} 含「{needle or ''}」：{len(hit)} 条 =="]
    for r in hit:
        out.append(f"  {r['year']} {r['office']} {r['person']} | note={r.get('note')} | flag={r.get('flag')} | page={r.get('book_page')}")
    return "\n".join(out)


lines = [
    show(1546, "兵部"),
    show(1546, None, "陳經"),
    show(1548, None, "張潤"),
    show(1548, None, "劉儲秀"),
    show(1558, None, "雷禮"),
    show(1558, None, "歐陽必進"),
    show(1558, None, "吳鵬"),
    show(1556, None, "何鰲"),
    show(1556, None, "歐陽必進"),
    show(1556, None, "盧紳"),
    show(1556, None, "高燿"),
    show(1547, "總督京儲"),
]
(ROOT / "_d04_raw.txt").write_text("\n\n".join(lines), encoding="utf-8")
print("written", sum(len(x) for x in lines))
