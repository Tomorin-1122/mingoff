"""D-04 模式判定：把已验证行×衙不一致的年份翻译成「同一姓名的多个行被并到同一衙」的证据（只读）。"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

out = []
for y in (1546, 1547, 1548):
    by = collections.defaultdict(list)
    for r in rows:
        if r["year"] == y:
            by[r["office"]].append(r["person"])
    out.append(f"## {y}")
    for k in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督京儲", "總督倉場", "都察院"):
        if by.get(k):
            out.append(f"  {k}: {sorted(by[k])}")
    # 同一年里同一姓名出现在多衙？
    person_offices = collections.defaultdict(set)
    for r in rows:
        if r["year"] == y:
            person_offices[r["person"]].add(r["office"])
    multi = {p: sorted(o) for p, o in person_offices.items() if len(o) > 1}
    out.append(f"  同年在多衙: {json.dumps(multi, ensure_ascii=False)}")

(ROOT / "_d04_pattern.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
