# -*- coding: utf-8 -*-
"""实拍轮案件清单：形讹案 → 原书页码 + Paddle 行框坐标（供裁切）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

CASES = []
CONFIGS = (
    ("总兵", "official_zongbing", "raw_zongbing", 2215),
    ("布政使", "official_buzhengshi", "raw_buzhengshi", 3177),
)

def main():
    d = json.load(open("_scratch/unresolved_classified.json", encoding="utf-8"))
    ents = {}
    for tbl, offfix, _, _ in CONFIGS:
        e = json.load(open(ROOT / f"src/mingoff/data/{offfix}.json", encoding="utf-8"))["tenures"]
        for t in e:
            ents.setdefault((tbl, t["person"]), []).append(t)
    out = []
    for tbl, cfg_tag, rawdir, poff in CONFIGS:
        raw = ROOT / "_scratch/vol34" / rawdir
        for it in d[tbl].get("misread_识别错误", []):
            ts = ents.get((tbl, it["name"]), [])
            if not ts:
                continue
            t = ts[0]
            bp = t["start_book_page"]
            pdf = bp - poff
            box = None
            f = raw / f"p{pdf}.jsonl"
            if f.is_file():
                dd = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
                oc = dd["result"]["ocrResults"][0]["prunedResult"]
                for tt, b in zip(oc["rec_texts"], oc["rec_boxes"]):
                    if tt.strip() == it["name"]:
                        box = [int(v) for v in b]
                        break
            out.append({"tbl": tbl, "name": it["name"], "fix": it["fix"],
                        "id": it.get("id"), "bio": it.get("bio"),
                        "office": t["office"], "year": t["start_year"],
                        "book_page": bp, "pdf": pdf, "box": box})
    for c in out:
        print(f"{c['tbl']} {c['name']}→{c['fix']} #{c['id']} {c['bio']} "
              f"{c['office']} {c['year']} 页{c['book_page']} pdf{c['pdf']} box={c['box']}")
    Path("_scratch/shipai_cases.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("cases:", len(out), "有坐标:", sum(1 for c in out if c["box"]))

if __name__ == "__main__":
    main()
