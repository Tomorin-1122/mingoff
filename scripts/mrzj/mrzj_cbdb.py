# -*- coding: utf-8 -*-
"""用本地 CBDB 裁决《明人傳記資料索引》人名目录的存疑条目。

口径：
  - 只认 c_dy = 19（明，1368–1644），其他朝代一律不采；
  - 先正名（BIOG_MAIN.c_name_chn），再别名（ALTNAME_DATA，字/號/室名）；
  - 同名多人不合并，标 ambiguous 并给出候选；
  - 同时校验 MingOff 已对齐的 cbdb_id 与 CBDB 正名是否一致。

用法: python mrzj_cbdb.py
产物: _scratch/mineru_mrzj/cbdb_verdict.json / cbdb_verdict.md
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
DB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")
MING = 19


def load():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    persons: dict[str, list[dict]] = defaultdict(list)
    by_id: dict[int, dict] = {}
    for pid, name, by, dy, iy, addr in cur.execute(
        "select c_personid,c_name_chn,c_birthyear,c_deathyear,c_index_year,c_index_addr_id "
        "from BIOG_MAIN where c_dy=?", (MING,)
    ):
        if not name:
            continue
        rec = {"id": pid, "name": name, "birth": by, "death": dy, "index_year": iy, "addr": addr}
        persons[name].append(rec)
        by_id[pid] = rec
    alt: dict[str, list[dict]] = defaultdict(list)
    for pid, an, code in cur.execute(
        "select a.c_personid,a.c_alt_name_chn,a.c_alt_name_type_code "
        "from ALTNAME_DATA a join BIOG_MAIN b on a.c_personid=b.c_personid "
        "where b.c_dy=? and a.c_alt_name_chn is not null", (MING,)
    ):
        rec = by_id.get(pid)
        if rec:
            alt[an].append({**rec, "type": code})
    con.close()
    return persons, alt, by_id


def main():
    persons, alt, by_id = load()
    print(f"CBDB 明代人物 {len(persons):,} 名（去重名） / 别名 {len(alt):,}")

    checks = json.loads((BASE / "index_check_after.json").read_text(encoding="utf-8"))
    unresolved = [x for x in checks if x["status"] in ("ocr_variant", "name_missing", "page_mismatch")]

    verdicts = []
    stat = Counter()
    for x in unresolved:
        name = x["name"]
        ex = persons.get(name, [])
        al = alt.get(name, [])
        if len(ex) == 1:
            stat["cbdb_exact"] += 1
            v = {"kind": "cbdb_exact", **ex[0]}
        elif len(ex) > 1:
            stat["cbdb_multi"] += 1
            v = {"kind": "cbdb_multi", "cands": ex[:5]}
        elif len(al) == 1:
            stat["cbdb_alias"] += 1
            v = {"kind": "cbdb_alias", **al[0]}
        elif len(al) > 1:
            stat["cbdb_alias_multi"] += 1
            v = {"kind": "cbdb_alias_multi", "cands": al[:5]}
        else:
            stat["cbdb_none"] += 1
            v = {"kind": "cbdb_none"}
        verdicts.append({**x, "cbdb": v})

    (BASE / "cbdb_verdict.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 反向校验：MingOff 已对齐的 cbdb_id 与 CBDB 正名是否一致
    mism = []
    for fn, label in [("official_buyuan.json", "部院"), ("official_cabinet.json", "内阁")]:
        d = json.loads(
            (Path(r"C:\Users\31698\projects\guji-pipeline\mingoff\src\mingoff\data") / fn).read_text(
                encoding="utf-8"
            )
        )
        for t in d["tenures"]:
            cid = t.get("cbdb_id")
            if not cid or cid not in by_id:
                continue
            if by_id[cid]["name"] != t.get("cbdb_name", t["person"]):
                mism.append((label, t["person"], cid, by_id[cid]["name"], t.get("cbdb_name")))

    lines = [
        "# CBDB 裁决（仅明代 c_dy=19）",
        "",
        f"存疑条目 {len(unresolved)}；CBDB 命中分布：",
        "",
        "| 判定 | 条数 |",
        "|---|---|",
    ]
    for k in ("cbdb_exact", "cbdb_multi", "cbdb_alias", "cbdb_alias_multi", "cbdb_none"):
        lines.append(f"| {k} | {stat[k]} |")
    lines += ["", "## 别名命中（字号 → 正名）", ""]
    for v in [y for y in verdicts if y["cbdb"]["kind"] == "cbdb_alias"][:40]:
        c = v["cbdb"]
        lines.append(f"- {v['name']}（目录 p{v['pages'][0]}）→ **{c['name']}** id={c['id']}")
    lines += ["", "## 同名多人（不合并）", ""]
    for v in [y for y in verdicts if y["cbdb"]["kind"] == "cbdb_multi"][:20]:
        ids = "、".join(f"{c['id']}({c['birth'] or '?'}-{c['death'] or '?'})" for c in v["cbdb"]["cands"])
        lines.append(f"- {v['name']}：{ids}")
    lines += ["", "## MingOff 已对齐 id 的正名一致性", ""]
    if mism:
        for m in mism[:30]:
            lines.append(f"- [{m[0]}] {m[1]} id={m[2]}：CBDB 作 {m[3]}，我们记 {m[4]}")
    else:
        lines.append("- 全部一致。")
    (BASE / "cbdb_verdict.md").write_text("\n".join(lines), encoding="utf-8")

    print(dict(stat))
    print("id 正名不一致：", len(mism))
    print("->", BASE / "cbdb_verdict.md")


if __name__ == "__main__":
    main()
