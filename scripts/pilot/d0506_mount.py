# -*- coding: utf-8 -*-
"""D-05/D-06：CBDB 重挂 + 补映射 + 传记索引出处层。

D-06（42 个 NULL 实体重挂）：v3 里有键但 cbdb_id=null 的实体，
  用 CBDB 精确同名 + 强职记录 + span 相容打分重挂；挂不上的写明原因。
D-05（240 个实体无映射）：entries person_id 不在 v3 的，exact 名匹配同法；
  仍无 CBDB 的查《明人传记资料索引》(mrzj) 建出处层 vol1_buyuan_mrzj.json（L4，不入主数据）。

打分（与 D-04 前对齐管线同构）：exact +50、强职(尚书/都御史/御史大夫)任过 +40、
强职且 span 重叠 +20、部对口 +10、生卒相容 ±；apply 条件：top≥60 且（唯一 或 领先≥10）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"C:/Users/31698/projects/guji-pipeline")
DB = ROOT / "_cbdb/cbdb_20261010.sqlite3"
DATA = ROOT / "mingoff/src/mingoff/data"
MRZJ = ROOT / "_scratch/mineru_mrzj/person_db.json"

STRONG = ("尚書", "尚书", "都御史", "御史大夫")
GARBAGE = re.compile(r"[犭肛粑紅羥熾燦]$|^欠陽$|^至十$")
SKIP_REASONS = {"楊訓文": "CBDB 无此人（baike-only，10-18 已核）",
                "劉宇": "10 候选无可验证兵部记录（10-18 已核）",
                "陳清": "25 候选无可验证工部记录（10-18 已核）"}


def ov(fy, ly, lo, hi):
    if fy in (0, None) or ly in (0, None):
        return True
    return fy <= hi + 2 and ly >= lo - 2


def main():
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # ---- 预载 ----
    biog = defaultdict(list)
    for r in conn.execute("select c_personid, c_name_chn, c_birthyear, c_deathyear from BIOG_MAIN where c_name_chn is not null"):
        biog[r["c_name_chn"]].append(r["c_personid"])
    recs = defaultdict(list)
    for r in conn.execute("""select p.c_personid as pid, o.c_office_chn as o,
                                    p.c_firstyear as fy, p.c_lastyear as ly
                             from POSTED_TO_OFFICE_DATA p
                             join OFFICE_CODES o on o.c_office_id=p.c_office_id"""):
        recs[r["pid"]].append((r["o"], r["fy"], r["ly"]))
    print(f"CBDB 人名 {len(biog)}，任职记录 {sum(len(v) for v in recs.values())}")

    v3 = json.loads((DATA / "vol1_buyuan_person_cbdb_v3.json").read_text(encoding="utf-8"))
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
    span, offs = {}, defaultdict(set)
    for e in entries:
        pid = e["person_id"]
        span.setdefault(pid, [e["year"], e["year"]])
        span[pid][0] = min(span[pid][0], e["year"])
        span[pid][1] = max(span[pid][1], e["year"])
        if e.get("office"):
            offs[pid].add(e["office"])

    def try_mount(name, lo, hi, mins):
        cands = biog.get(name, [])
        scored = []
        for pid in cands:
            rs = recs.get(pid, [])
            cn, birth, death = None, None, None
            for r in conn.execute("select c_name_chn,c_birthyear,c_deathyear from BIOG_MAIN where c_personid=?", (pid,)).fetchone() and [] or []:
                pass
            b = conn.execute("select c_name_chn,c_birthyear,c_deathyear from BIOG_MAIN where c_personid=?", (pid,)).fetchone()
            cn, birth, death = b["c_name_chn"], b["c_birthyear"], b["c_deathyear"]
            strong_any = sum(1 for o, f, l in rs if o and any(k in o for k in STRONG))
            strong_ov = sum(1 for o, f, l in rs if o and any(k in o for k in STRONG) and ov(f, l, lo, hi))
            min_match = sum(1 for o, f, l in rs if o and any(m in o for m in mins) and ov(f, l, lo, hi))
            s = 50.0 + strong_any * 20 + strong_ov * 10 + min_match * 10
            if birth not in (0, None) and birth > hi:
                s -= 40
            if death not in (0, None) and death < lo - 1:
                s -= 60
            scored.append((s, pid, cn, birth, death, strong_any, strong_ov, min_match, len(rs)))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return None, "no-candidate"
        top = scored[0]
        margin = top[0] - (scored[1][0] if len(scored) > 1 else -999)
        if top[0] >= 60 and (len(scored) == 1 or margin >= 10):
            return top, None
        return None, f"multi-candidate({len(scored)})"

    # ---- D-06：42 NULL 重挂 ----
    d06_mounted, d06_skip = {}, {}
    for key in [k for k, v in v3.items() if not v.get("cbdb_id")]:
        if key in SKIP_REASONS:
            d06_skip[key] = SKIP_REASONS[key]
            continue
        if GARBAGE.search(key):
            d06_skip[key] = "OCR 碎片名，不可挂接（待 repair）"
            continue
        name = re.sub(r"#\d+$", "", key)
        lo, hi = span.get(key, (1368, 1644))
        top, why = try_mount(name, lo, hi, offs.get(key, set()))
        if top:
            s, pid, cn, birth, death, sa, sov, mm, nrec = top
            v3[key] = {**v3[key], "cbdb_id": pid, "cbdb_name": cn,
                       "method": "d06-remount", "score": round(s, 1),
                       "birth": birth or None, "death": death or None}
            d06_mounted[key] = (pid, cn, round(s, 1))
        else:
            d06_skip[key] = why

    # ---- D-05：未映射实体 exact 挂接 ----
    d05_mounted, d05_skip = {}, {}
    for key in sorted(set(span) - set(v3)):
        name = re.sub(r"#\d+$", "", key)
        if GARBAGE.search(name):
            d05_skip[key] = "OCR 碎片名"
            continue
        lo, hi = span[key]
        top, why = try_mount(name, lo, hi, offs.get(key, set()))
        if top:
            s, pid, cn, birth, death, sa, sov, mm, nrec = top
            v3[key] = {"cbdb_id": pid, "cbdb_name": cn, "method": "d05-exact",
                       "score": round(s, 1), "birth": birth or None,
                       "death": death or None, "span": [lo, hi]}
            d05_mounted[key] = (pid, cn, round(s, 1))
        else:
            d05_skip[key] = why

    (DATA / "vol1_buyuan_person_cbdb_v3.json").write_text(
        json.dumps(v3, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 出处层（L4）：mrzj 传记索引 ----
    mrzj = json.loads(MRZJ.read_text(encoding="utf-8"))
    by_name = defaultdict(list)
    for p in mrzj:
        by_name[p["name"]].append(p)
    src_layer = {}
    for key in sorted(set(span)):
        if v3.get(key, {}).get("cbdb_id"):
            continue
        name = re.sub(r"#\d+$", "", key)
        hits = by_name.get(name, [])
        if hits:
            p = hits[0]
            src_layer[key] = {"mrzj_name": p["name"], "birth": p.get("birth"),
                              "death": p.get("death"), "zi": p.get("zi"),
                              "hao": p.get("hao"), "native": p.get("native"),
                              "shi": p.get("shi"), "cites": p.get("cites", []),
                              "pages": [p.get("page")], "tier": p.get("tier")}
    (DATA / "vol1_buyuan_mrzj.json").write_text(
        json.dumps(src_layer, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n== D-06 重挂 {len(d06_mounted)} / 跳过 {len(d06_skip)} ==")
    for k, (pid, cn, s) in sorted(d06_mounted.items()):
        print(f"  ✓ {k} → {cn} ({pid}) score={s}")
    for k, why in sorted(d06_skip.items()):
        print(f"  ✗ {k}: {why}")
    print(f"\n== D-05 挂接 {len(d05_mounted)} / 跳过 {len(d05_skip)} ==")
    for k, (pid, cn, s) in sorted(d05_mounted.items())[:30]:
        print(f"  ✓ {k} → {cn} ({pid}) score={s}")
    print(f"  …（共 {len(d05_mounted)}）")
    total = sum(1 for k in span if v3.get(k, {}).get("cbdb_id"))
    print(f"\n终态: 实体 {len(span)}，有 cbdb_id {total} ({100*total/len(span):.0f}%)，mrzj 出处层 {len(src_layer)}")


if __name__ == "__main__":
    main()
