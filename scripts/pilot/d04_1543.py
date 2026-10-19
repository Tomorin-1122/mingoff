"""D-04：看 1543/1544 两页（同为对页无标签年）的行归属，判断 parser 的「三级锚定」是否可控。"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

out = []
for y in (1543, 1544):
    d = collections.defaultdict(list)
    for r in rows:
        if r["year"] == y:
            d[r["office"]].append(r["person"])
    out.append(f"## {y} 数据各衙")
    out.append("  " + json.dumps(d, ensure_ascii=False))
    for r in rows:
        if r["year"] == y and r.get("flag"):
            out.append(f"  FLAG {r['office']} {r['person']} | {r['flag']} | note={r.get('note', '')[:36]}")

out.append("")
out.append("## 原书转写")
out.append("1544 p579/PDF594：吏部 許讚/熊浹；戶部 王杲；禮部 張璧/費寀；兵部 毛伯温/戴金；"
           "刑部 聞淵；工部 甘爲霖；總督京儲 陳經；都察院 周用/熊浹")
out.append("1545 p580/PDF595：吏部 熊浹/唐龍；戶部 王杲；禮部 費寀；兵部 戴金/唐龍/路迎；"
           "刑部 聞淵；工部 甘爲霖；總督京儲 陳經；都察院 周用")
(ROOT / "_d04_1543.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
