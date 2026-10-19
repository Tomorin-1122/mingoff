"""人工核验 6 条：定位相关条目（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))

out = []
# 1 天启七年 李國𣚴/李国楷（兵部尚书 1627）
for r in e:
    if r["year"] == 1627 and ("李" in r["person"]) and r["office"] == "兵部":
        out.append(f"1. 1627 兵部 {r['person']!r} raw={r.get('raw_person')!r} "
                   f"note={r.get('note','')[:30]!r} page={r.get('book_page')}")
# 2 钱溥/钱士升
for r in e:
    if r["person"] in ("錢溥", "錢士升", "钱溥", "钱士升"):
        out.append(f"2. {r['year']} {r['office']} {r['person']} note={r.get('note','')[:30]!r} page={r.get('book_page')}")
# 3 劉一燝（万历四十八年=1620 入阁→礼部尚书?）
for r in e:
    if "一燝" in r["person"] or "一焴" in r["person"] or "一㸅" in r["person"]:
        out.append(f"3. {r['year']} {r['office']} {r['person']} src={r.get('src')}")
# 4 翟鑾 1520-1542
for r in e:
    if r["person"] == "翟鑾" and 1520 <= r["year"] <= 1542:
        out.append(f"4. {r['year']} {r['office']} 翟鑾 note={r.get('note','')[:34]!r} page={r.get('book_page')}")
# 5 蔣冕 1518-1528
for r in e:
    if r["person"] == "蔣冕" and 1518 <= r["year"] <= 1528:
        out.append(f"5. {r['year']} {r['office']} 蔣冕 note={r.get('note','')[:34]!r} page={r.get('book_page')}")
# 6 劉翔/劉珝 成化 1460-1490
for r in e:
    if r["person"] in ("劉翔", "劉珝") and 1460 <= r["year"] <= 1490:
        out.append(f"6. {r['year']} {r['office']} {r['person']} note={r.get('note','')[:34]!r} page={r.get('book_page')}")

print("\n".join(out) if out else "（无命中）")
(ROOT / "docs/evidence/_renhe.locate.txt").write_text("\n".join(out), encoding="utf-8")
