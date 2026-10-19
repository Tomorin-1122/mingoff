"""D-04 探针：把争议条目写成 UTF-8 文件（PowerShell 回显中文不可靠，改用文件读）。"""
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
lines = []
for y, off in TARGETS:
    hit = [r for r in rows if r.get("year") == y and r.get("office") == off]
    lines.append(f"== {y} {off} ({len(hit)}) ==")
    for r in hit:
        lines.append(
            f"  {r.get('person')} | note={r.get('note')} | raw_office={r.get('raw_office')}"
            f" | flag={r.get('flag')} | src={r.get('src')} | page={r.get('book_page')}"
        )
(ROOT / "_d04_probe.txt").write_text("\n".join(lines), encoding="utf-8")
print("written", len(lines), "lines")
