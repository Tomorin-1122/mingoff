# -*- coding: utf-8 -*-
"""全量抽取人物表（带名称门槛）。

门槛：人名必须命中《明人傳記資料索引》目录 或 CBDB 明代库，否则丢弃
（试点实测：不过门槛的 40.6% 全是切分噪声）。

产物:
  _scratch/mineru_mrzj/person_db.json / person_db.csv
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mrzj_extract as ex  # noqa: E402

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")


def main():
    pages = json.loads((BASE / "corpus_corrected.json").read_text(encoding="utf-8"))
    catalog = {c["name"]: c for c in json.loads((BASE / "index_catalog.json").read_text(encoding="utf-8"))}
    final_cat = {}
    fp = BASE / "index_catalog_final.json"
    if fp.exists():
        final_cat = {c["name"]: c for c in json.loads(fp.read_text(encoding="utf-8"))}
    cbdb = json.loads((BASE / "cbdb_all.json").read_text(encoding="utf-8"))

    # 页 → 目录命中的人名（INDEX 给的页归属）
    by_page: dict[int, list[str]] = {}
    for c in catalog.values():
        for pg_ in c["pages"]:
            by_page.setdefault(pg_, []).append(c["name"])

    rows, dropped = [], 0
    for p in pages:
        t, pg = p["text"], p["printed_page"]
        # 混合定位：边界法 + 目录页归属法
        hs = list(ex.heads(t))
        seen = {n for _, n in hs}
        cursor = 0
        for nm in sorted(by_page.get(pg, []), key=len, reverse=True):
            if nm in seen:
                continue
            i = t.find(nm, cursor)
            if i < 0:
                i = t.find(nm)
            if i >= 0:
                hs.append((i, nm))
                seen.add(nm)
                cursor = i + len(nm)
        hs.sort()
        # 去嵌套
        merged = []
        for s_, n_ in hs:
            if merged and s_ < merged[-1][0] + len(merged[-1][1]):
                continue
            merged.append((s_, n_))
        hs = merged
        for i, (s, name) in enumerate(hs):
            e = hs[i + 1][0] if i + 1 < len(hs) else len(t)
            if name not in catalog and name not in cbdb:
                dropped += 1
                continue
            r = ex.extract_one(name, t[s:e], pg)
            c = cbdb.get(name, {})
            r["cbdb_kind"] = c.get("kind", "none")
            r["cbdb_id"] = c["id"] if c.get("kind") == "unique" else None
            r["cbdb_multi"] = c.get("n") if c.get("kind") == "multi" else None
            r["tier"] = final_cat.get(name, {}).get("tier", "")
            rows.append(r)

    # 去重：同名同页只留最长正文（避免跨栏重复）
    best: dict[tuple, dict] = {}
    for r in rows:
        k = (r["name"], r["page"])
        if k not in best or r["raw_len"] > best[k]["raw_len"]:
            best[k] = r
    persons = sorted(best.values(), key=lambda r: (r["page"], r["name"]))
    (BASE / "person_db.json").write_text(
        json.dumps(persons, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    import csv
    with (BASE / "person_db.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["姓名", "正文页", "生", "卒", "名", "字", "号", "籍贯", "科举年号",
                    "科举年", "科举年(公元)", "科举类型", "谥", "出处数", "CBDB", "cbdb_id", "置信层级"])
        for r in persons:
            w.writerow([r["name"], r["page"], r["birth"] or "", r["death"] or "", r["ming"] or "",
                        r["zi"] or "", r["hao"] or "", r["native"] or "", r["exam_era"] or "",
                        r["exam_year"] or "", r.get("exam_gregorian") or "", r["exam_type"] or "", r["shi"] or "",
                        len(r["cites"]), r["cbdb_kind"], r["cbdb_id"] or "", r["tier"]])

    n = len(persons)
    print(f"全量：原始条目 {len(rows) + dropped}，过门槛 {len(best)}（丢 {dropped}，"
          f"{dropped/max(1,len(rows)+dropped)*100:.1f}%）")
    for k in ("birth", "death", "zi", "hao", "native", "exam_era", "shi"):
        v = sum(1 for r in persons if r[k])
        print(f"  {k:9} {v:5}  {v/n*100:5.1f}%")
    print(f"  出处      {sum(1 for r in persons if r['cites']):5}  {sum(1 for r in persons if r['cites'])/n*100:5.1f}%")
    print("CBDB:", dict(Counter(r["cbdb_kind"] for r in persons)))
    print("层级:", dict(Counter(r["tier"][:1] for r in persons)))
    print("->", BASE / "person_db.csv")


if __name__ == "__main__":
    main()
