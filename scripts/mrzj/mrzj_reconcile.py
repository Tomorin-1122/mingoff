# -*- coding: utf-8 -*-
"""人物表 × CBDB 逐字段对账。

目的不是「拿 CBDB 判本书对错」，而是分清三类：
  agree    两边都有且一致
  conflict 两边都有但不一致  → 需要仲裁，这才是真正要校的地方
  book_only 本书有、CBDB 无 → 本书的**新增价值**
  cbdb_only CBDB 有、本书无 → 可回填的空白

用法: python mrzj_reconcile.py
产物: _scratch/mineru_mrzj/reconcile.csv / reconcile_summary.md
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
DB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")

JINSHI_CODES = (36, 37, 44, 124, 187, 334, 348)  # 各类「進士」


def load_cbdb(ids: list[int]):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    out = {i: {"birth": None, "death": None, "addr": set(), "zi": set(), "hao": set(), "exam": []}
           for i in ids}
    for i in range(0, len(ids), 400):
        chunk = ids[i : i + 400]
        q = ",".join("?" * len(chunk))
        for pid, by, dy in cur.execute(
            f"select c_personid,c_birthyear,c_deathyear from BIOG_MAIN where c_personid in ({q})", chunk
        ):
            out[pid]["birth"], out[pid]["death"] = by, dy
        for pid, typ, nm in cur.execute(
            f"select a.c_personid,a.c_addr_type,d.c_name_chn from BIOG_ADDR_DATA a "
            f"join ADDR_CODES d on a.c_addr_id=d.c_addr_id where a.c_personid in ({q})", chunk
        ):
            if typ == 1 and nm:
                out[pid]["addr"].add(nm)
        for pid, nm, typ in cur.execute(
            f"select c_personid,c_alt_name_chn,c_alt_name_type_code from ALTNAME_DATA "
            f"where c_personid in ({q})", chunk
        ):
            if not nm:
                continue
            if typ == 4:
                out[pid]["zi"].add(nm)
            elif typ == 5:
                out[pid]["hao"].add(nm)
        for pid, code, yr in cur.execute(
            f"select c_personid,c_entry_code,c_year from ENTRY_DATA where c_personid in ({q})", chunk
        ):
            if code in JINSHI_CODES and yr:
                out[pid]["exam"].append(yr)
    con.close()
    return out


VAR = str.maketrans({"釆": "采", "靑": "青", "菴": "庵", "齋": "齊"})


def norm(x: str) -> str:
    return (x or "").translate(VAR)


def judge(ours, theirs, cmp=None):
    if ours in (None, "", 0) and not theirs:
        return None
    if ours in (None, "", 0):
        return "cbdb_only"
    if not theirs:
        return "book_only"
    if cmp(ours, theirs):
        return "agree"
    return "conflict"


def main():
    persons = json.loads((BASE / "person_db.json").read_text(encoding="utf-8"))
    ids = sorted({r["cbdb_id"] for r in persons if r["cbdb_id"]})
    cb = load_cbdb(ids)
    print(f"人物 {len(persons)}，其中带 cbdb_id {len(ids)}")

    rows = []
    stat = Counter()
    for r in persons:
        cid = r["cbdb_id"]
        if not cid:
            continue
        c = cb[cid]
        rec = {"name": r["name"], "page": r["page"], "cbdb_id": cid}
        # 生年 / 卒年
        for f, key in (("birth", "birth"), ("death", "death")):
            ours, theirs = r.get(f), c.get(key)
            rec[f] = judge(ours, theirs, lambda a, b: abs(a - b) <= 2)
        # 籍贯：包含即算一致（無錫 / 無錫縣）
        ours, theirs = norm(r.get("native")), {norm(x) for x in c.get("addr", set())}
        rec["native"] = (
            None if not ours and not theirs
            else "cbdb_only" if not ours
            else "book_only" if not theirs
            else "agree" if any(ours in t or t in ours for t in theirs) else "conflict"
        )
        # 字：集合命中
        ours = r.get("zi")
        theirs = c["zi"]
        rec["zi"] = (
            None if not ours and not theirs
            else "cbdb_only" if not ours
            else "book_only" if not theirs
            else "agree" if norm(ours) in {norm(x) for x in theirs} else "conflict"
        )
        # 号：集合命中
        ours = r.get("hao")
        theirs = c["hao"]
        rec["hao"] = (
            None if not ours and not theirs
            else "cbdb_only" if not ours
            else "book_only" if not theirs
            else "agree" if norm(ours) in {norm(x) for x in theirs} else "conflict"
        )
        # 科举：进士年 ±2
        ours = r.get("exam_gregorian")
        theirs = c["exam"]
        rec["exam"] = (
            None if not ours and not theirs
            else "cbdb_only" if not ours
            else "book_only" if not theirs
            else "agree" if any(abs(ours - y) <= 2 for y in theirs) else "conflict"
        )
        rows.append(rec)
        for f in ("birth", "death", "native", "zi", "hao", "exam"):
            if rec[f]:
                stat[(f, rec[f])] += 1

    import csv
    with (BASE / "reconcile.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        fields = ["birth", "death", "native", "zi", "hao", "exam"]
        w.writerow(["姓名", "正文页", "cbdb_id"] + [f"{x}" for x in fields])
        for r in rows:
            w.writerow([r["name"], r["page"], r["cbdb_id"]] + [r.get(x) or "" for x in fields])

    lines = ["# 人物表 × CBDB 逐字段对账", "", f"可比人物 {len(rows)}（带 cbdb_id）", "",
             "| 字段 | 一致 | 冲突 | 本书独有 | CBDB 独有 | 冲突率 |", "|---|---|---|---|---|---|"]
    for f in fields:
        a, c_, b, d = (stat[(f, k)] for k in ("agree", "conflict", "book_only", "cbdb_only"))
        both = a + c_
        lines.append(f"| {f} | {a} | {c_} | {b} | {d} | {c_/both*100 if both else 0:.1f}% |")
    (BASE / "reconcile_summary.md").write_text("\n".join(lines), encoding="utf-8")

    for f in fields:
        a, c_, b, d = (stat[(f, k)] for k in ("agree", "conflict", "book_only", "cbdb_only"))
        both = a + c_
        print(f"{f:7} 一致{a:5} 冲突{c_:5}({c_/both*100 if both else 0:5.1f}%) 本书独有{b:5} CBDB独有{d:5}")
    print("->", BASE / "reconcile.csv")


if __name__ == "__main__":
    main()
