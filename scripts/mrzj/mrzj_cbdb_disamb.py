# -*- coding: utf-8 -*-
"""对 CBDB 同名多人的存疑名做消歧，并落最终裁决表。

消歧优先级：
  1. MingOff 已对齐的 cbdb_id（部院/内阁，已人工校过）——最高；
  2. 正文该页条目里的生卒括号，与 CBDB 候选比对（±2 年）；
  3. 仍不唯一 → ambiguous，不合并。

产物: _scratch/mineru_mrzj/cbdb_final.json / cbdb_final.csv
"""
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
DB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")
MING = 19
BORN = re.compile(r"[（(](\d{3,4})\s*[—–\-]+\s*(\d{3,4})?[）)]")


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    by_name = defaultdict(list)
    by_id = {}
    for pid, name, by, dy in cur.execute(
        "select c_personid,c_name_chn,c_birthyear,c_deathyear from BIOG_MAIN where c_dy=?", (MING,)
    ):
        if name:
            rec = {"id": pid, "name": name, "birth": by, "death": dy}
            by_name[name].append(rec)
            by_id[pid] = rec
    con.close()

    ours = {}
    for fn in ("official_buyuan.json", "official_cabinet.json"):
        d = json.loads(
            (Path(r"C:\Users\31698\projects\guji-pipeline\mingoff\src\mingoff\data") / fn).read_text(
                encoding="utf-8"
            )
        )
        for t in d["tenures"]:
            if t.get("cbdb_id"):
                ours.setdefault(t["person"], t["cbdb_id"])

    verdicts = json.loads((BASE / "cbdb_verdict.json").read_text(encoding="utf-8"))
    corpus = {p["printed_page"]: p["text"] for p in
              json.loads((BASE / "corpus_corrected.json").read_text(encoding="utf-8"))}

    out, stat = [], Counter()
    for v in verdicts:
        name = v["name"]
        kinds = v["cbdb"]["kind"]
        chosen, why = None, ""
        if name in ours:
            cid = ours[name]
            rec = by_id.get(cid)
            if rec:
                chosen, why = rec, "mingoff_id"
        if not chosen and kinds == "cbdb_exact":
            chosen, why = v["cbdb"], "cbdb_unique"
        if not chosen and kinds in ("cbdb_multi", "cbdb_alias_multi", "cbdb_alias"):
            cands = v["cbdb"].get("cands") or ([v["cbdb"]] if kinds == "cbdb_alias" else [])
            m = BORN.search(corpus.get(v["pages"][0], "")[max(0, corpus.get(v["pages"][0], "").find(name)):][:80]) if name in corpus.get(v["pages"][0], "") else None
            if m:
                by_ = int(m.group(1)); dy_ = int(m.group(2)) if m.group(2) else None
                hit = [c for c in cands
                       if (c.get("birth") and abs(c["birth"] - by_) <= 2)
                       or (dy_ and c.get("death") and abs(c["death"] - dy_) <= 2)]
                if len(hit) == 1:
                    chosen, why = hit[0], "year_match"
            if not chosen and len(cands) == 1:
                chosen, why = cands[0], "single_cand"
        if chosen:
            stat[why] += 1
        else:
            stat["unresolved" if kinds != "cbdb_none" else "not_in_cbdb"] += 1
        out.append({**v, "verdict": {"id": chosen["id"], "name": chosen["name"],
                                     "birth": chosen.get("birth"), "death": chosen.get("death"),
                                     "why": why} if chosen else None})

    (BASE / "cbdb_final.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    import csv
    with (BASE / "cbdb_final.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["目录名", "正文页", "原对校状态", "CBDB id", "CBDB 正名", "生", "卒", "裁决依据"])
        for x in out:
            vd = x["verdict"] or {}
            w.writerow([x["name"], x["pages"][0], x["status"], vd.get("id", ""), vd.get("name", ""),
                        vd.get("birth", ""), vd.get("death", ""), vd.get("why", x["cbdb"]["kind"])])
    print(dict(stat))
    print("可裁决", sum(v for k, v in stat.items() if k in ("mingoff_id", "cbdb_unique", "year_match", "single_cand")))
    print("->", BASE / "cbdb_final.csv")


if __name__ == "__main__":
    main()
