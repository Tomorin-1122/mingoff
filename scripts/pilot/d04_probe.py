"""D-04 探针：看争议年份条目的注文与 raw_office（只读）。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
d = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = d if isinstance(d, list) else d["entries"]

TARGETS = [
    (1549, "總督京儲"), (1550, "總督倉場"), (1551, "總督倉場"), (1552, "總督倉場"),
    (1553, "總督京儲"), (1556, "刑部"), (1556, "總督倉場"), (1557, "總督倉場"),
    (1398, "御史臺"), (1399, "御史府"), (1400, "御史府"), (1401, "御史府"), (1402, "御史府"),
]
out = []
for y, off in TARGETS:
    hit = [r for r in rows if r.get("year") == y and r.get("office") == off]
    out.append(f"== {y} {off} ({len(hit)}) ==")
    for r in hit:
        out.append(
            f"  {r.get('person')} | note={r.get('note')!r} | raw_office={r.get('raw_office')!r}"
            f" | flag={r.get('flag')!r} | src={r.get('src')!r} | page={r.get('book_page')}"
        )
print("\n".join(out))
