"""D-11 反向验证：对页年数据的当前 office 与「高置信人名锚建议」逐人比较（只读）。"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
d = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_d11_review.json").read_text(encoding="utf-8"))
cur = collections.defaultdict(list)
for r in e:
    cur[r["year"]].append(r)
mism, chk, ex = 0, 0, []
for r in d["rows"]:
    if r["how"] != "人名锚" or r["conf"] < 0.9:
        continue
    for name in r["names"]:
        for er in cur[r["year"]]:
            if er["person"] == name:
                chk += 1
                if er["office"] != r["suggest_office"]:
                    mism += 1
                    if len(ex) < 15:
                        ex.append({"year": r["year"], "person": name,
                                   "current": er["office"], "suggest": r["suggest_office"]})
out = {"checked": chk, "mismatch": mism, "examples": ex}
(ROOT / "docs/evidence/d11/_d11_crosscheck.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"checked={chk} mismatch={mism}")
for x in ex:
    print(x)
