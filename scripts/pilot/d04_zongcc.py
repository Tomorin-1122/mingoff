"""查 1550–1555 總倉場 行的来源（只读）。

D41 要求「總倉場」只在 1556 及以后出现；但 1550–1555 数据里仍有 5 段挂在「總倉場」。
需要定位这些段在 repair 输入（vol1_buyuan_entries.json）里的 raw_office 是什么——
若是「總倉場」且原书该年表头确为「總督倉場/總督京儲」，就是 parser 当年归一错了。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src" / "mingoff" / "data"
v2 = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
v1 = json.loads((DATA / "vol1_buyuan_entries.json").read_text(encoding="utf-8"))

out = ["## v2 中 office=總倉場 且 year<1556 的条目"]
for e in v2:
    if e["office"] == "總倉場" and e["year"] < 1556:
        out.append(f"  v2: {e['year']} {e['office']} {e['person']} raw_office={e.get('raw_office')} page={e.get('book_page')}")
        # 在 v1 里找同源
        for o in v1:
            if o["year"] == e["year"] and o["person"] == e.get("raw_person") and o["office"] == e.get("raw_office"):
                out.append(f"    v1 源: {o['year']} {o['office']} {o['person']} src={o.get('src')}")
                break

out.append("")
out.append("## v1 里所有 office 为 總倉場/總督倉場/總會場 的条目（按年）")
import collections
c = collections.Counter((o["year"], o["office"]) for o in v1 if "倉場" in (o["office"] or "") or "會場" in (o["office"] or ""))
for (y, off), n in sorted(c.items()):
    out.append(f"  {y} {off}: {n}")

(ROOT / "docs/evidence/d04/_zongcc.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
