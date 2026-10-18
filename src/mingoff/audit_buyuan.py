# -*- coding: utf-8 -*-
"""部院数据质量审计（v2，可复现门槛）。

对应《数据接入规范》G6 / 《年表PDF_OCR规范》O7：
  1. 结构：段年连续、月合法、D15、重复段；
  2. 覆盖：年份/衙署缺行、全年份条目骤降；
  3. 断段：同人同衙缺口是否都有解释（离任/入场注文，或 gap_years 显式记录）；
  4. 人名：伪人名（閏/扈駕/右侍/官署字碎片）、未映射；
  5. 注文：活跃注文中不得出现另一人名；同 (年,人,衙) 不得重复；
  6. CBDB：生卒/任期冲突；同一 id 多正名；
  7. 衙署：不得合并不同衙署（御史臺/都察院/御史府、總督京儲/總督倉場各自独立）；
  8. manifest：统计与实测一致。

用法：
  python -m mingoff.audit_buyuan            # 摘要
  python -m mingoff.audit_buyuan --json out.json
blockers 非空时，数据状态只能标 review，不得接站点。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mingoff.official import CUT_Y

DATA = Path(__file__).resolve().parent / "data"
_CBDB = [DATA.parents[3] / "_cbdb" / "cbdb_20261010.sqlite3",
         Path.cwd() / "_cbdb" / "cbdb_20261010.sqlite3"]
CBDB = next((p for p in _CBDB if p.is_file()), _CBDB[-1])

CANON_OFFICES = {"吏部", "戶部", "禮部", "兵部", "刑部", "工部",
                 "御史臺", "都察院", "御史府", "總督京儲", "總督倉場"}
LEAVE = ("罷", "卒", "致仕", "削籍", "下獄", "被執", "戍", "謫", "丁憂", "憂去",
         "乞歸", "乞休", "養病", "免", "回籍", "為民", "降", "死於難", "死難", "歿於",
         "正法", "自盡", "殉難", "棄市", "革職", "奪官", "奔喪", "守制", "出", "調", "改除")
ENTER = ("入", "任", "起復", "起", "召", "視事", "至京", "復官", "復", "掌", "陞", "升", "遷")
PSEUDO_RE = re.compile(r"(閏|扈駕|右侍|左侍|尚書|侍郎)$")
PSEUDO_CHARS = set("遷改罷卒致仕吏戶兵刑工都察御史侍郎參布按總督巡撫軍屯戍餉糧鹽漕閣殿")


def load() -> dict:
    files = {
        "entries": DATA / "vol1_buyuan_entries_v2.json",
        "doc": DATA / "official_buyuan.json",
        "mapping": DATA / "vol1_buyuan_person_cbdb_v3.json",
        "repair": DATA / "vol1_buyuan_repair.json",
        "manifest": DATA / "vol1_buyuan_manifest.json",
    }
    out = {}
    for k, p in files.items():
        if not p.is_file() and k in ("entries", "mapping"):
            p = DATA / f"vol1_buyuan_{'entries' if k == 'entries' else 'person_cbdb'}.json"
        out[k] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else (
            [] if k in ("entries",) else {})
    return out


def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


def audit() -> dict:
    d = load()
    entries, doc, mapping = d["entries"], d["doc"], d["mapping"]
    tenures = doc.get("tenures", [])
    repair = d.get("repair") or {}
    r: dict = {}

    # 1 结构
    dup_seg = [k for k, v in Counter(
        (t["person_id"], t["office"], t["start_year"], t["end_year"]) for t in tenures
    ).items() if v > 1]
    bad_years = [t for t in tenures if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    bad_month = [t for t in tenures if any(
        m is not None and not 1 <= m <= 12 for m in (t["start_month"], t["end_month"]))]
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > 3)
           or (t["end_year"] == CUT_Y and not (t["end_clamped"] and t["end_month"] == 3))]
    r["structure"] = dict(tenures=len(tenures),
                          persons=len({t["person_id"] for t in tenures}),
                          display_persons=len({t["person"] for t in tenures}),
                          person_years=sum(len(t["years"]) for t in tenures),
                          dup_segments=len(dup_seg), bad_years=len(bad_years),
                          bad_month=len(bad_month), d15=len(d15),
                          gap_merged=sum(1 for t in tenures if t.get("gap_years")),
                          gap_years=sum(len(t.get("gap_years") or []) for t in tenures))

    # 2 覆盖
    years = {e["year"] for e in entries}
    missing = [y for y in range(1368, CUT_Y + 1) if y not in years]
    office_years = defaultdict(set)
    for e in entries:
        if e.get("office"):
            office_years[e["office"]].add(e["year"])
    office_gaps = {}
    for o, ys in sorted(office_years.items()):
        lo, hi = min(ys), max(ys)
        office_gaps[o] = [y for y in range(lo, hi + 1) if y not in ys]
    per_year = Counter(e["year"] for e in entries)
    med = sorted(per_year.values())[len(per_year) // 2] if per_year else 0
    lows = [(y, c) for y, c in sorted(per_year.items()) if c < med * 0.6]
    r["coverage"] = dict(missing_years=missing, office_gaps=office_gaps,
                         per_year_median=med, low_years=lows,
                         page_covered=sum(1 for e in entries if e.get("book_page")),
                         page_total=len(entries))

    # 3 断段：剩余多段缺口是否都有解释
    by_po = defaultdict(list)
    for t in tenures:
        by_po[(t["person_id"], t["office"])].append(t)
    gaps = []
    for (p, o), ts in by_po.items():
        if len(ts) < 2:
            continue
        ts.sort(key=lambda x: x["start_year"])
        for a, b in zip(ts, ts[1:]):
            gap = b["start_year"] - a["end_year"] - 1
            if gap <= 0:
                continue
            explained = (a["leave"] != "未載"
                         or any(v in (b["note"] or "") for v in ENTER)
                         or a.get("gap_years") or a.get("gap_after")
                         or a.get("same_name_risk"))
            gaps.append(dict(person=p, office=o, gap=gap,
                             after=a["end_year"], before=b["start_year"],
                             explained=explained))
    unexplained = [g for g in gaps if not g["explained"]]
    short_unexplained = [g for g in unexplained if g["gap"] <= 2]
    r["fragmentation"] = dict(multi_groups=sum(1 for v in by_po.values() if len(v) > 1),
                              gaps=len(gaps), unexplained=len(unexplained),
                              short_unexplained=len(short_unexplained),
                              samples=unexplained[:15])

    # 4 人名 / 身份
    persons = {e["person"] for e in entries}
    person_ids = {e.get("person_id") for e in entries}
    pseudo = sorted(n for n in persons
                    if PSEUDO_RE.search(n) or len(n) >= 5
                    or (n not in mapping and any(ch in PSEUDO_CHARS for ch in n[1:])))
    unmapped = [(pid, c) for pid, c in Counter(e.get("person_id") for e in entries).most_common()
                if pid not in mapping]
    name_entities = defaultdict(set)
    for e in entries:
        name_entities[e["person"]].add(e.get("person_id"))
    split_names = {n: sorted(v) for n, v in name_entities.items() if len(v) > 1}
    spans = defaultdict(list)
    for t in tenures:
        spans[t["person_id"]].append((t["start_year"], t["end_year"]))
    bad_identity = []
    for pid, ss in spans.items():
        lo, hi = min(a for a, _ in ss), max(b for _, b in ss)
        if hi - lo > 80:
            bad_identity.append({"person_id": pid, "span": [lo, hi]})
    missing_identity = [e for e in entries if not e.get("person_id")]
    r["names"] = dict(persons=len(persons), person_ids=len(person_ids),
                      split_names=split_names, pseudo=pseudo,
                      pseudo_entries=sum(1 for e in entries if e["person"] in set(pseudo)),
                      unmapped_persons=len(unmapped), unmapped=unmapped[:30],
                      missing_identity=len(missing_identity),
                      bad_identity=bad_identity)

    # 5 注文 / 重复
    hits = []
    for e in entries:
        note = e.get("note") or ""
        if not note:
            continue
        for nm in persons:
            if nm != e["person"] and len(nm) >= 2 and nm in note:
                hits.append((e["year"], e["office"], e["person"], nm))
                break
    dup_entry = [(k, v) for k, v in Counter(
        (e["year"], e.get("person_id"), e.get("office")) for e in entries).items() if v > 1]
    r["notes"] = dict(active_note_with_other_name=len(hits), samples=hits[:15],
                      duplicate_entries=len(dup_entry), dup_samples=dup_entry[:15],
                      quarantined=(repair.get("counts") or {}).get("quarantined"),
                      resolution=repair.get("note_resolution_counts", {}),
                      book_patches=(repair.get("counts") or {}).get("book_patch"))

    # 6 CBDB
    date_bad, shared = [], {}
    if CBDB.is_file():
        conn = sqlite3.connect(f"file:{CBDB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        def row(pid):
            return conn.execute("SELECT c_name_chn,c_birthyear,c_deathyear FROM BIOG_MAIN "
                                "WHERE c_personid=?", (pid,)).fetchone()

        ids = defaultdict(set)
        for pid, v in mapping.items():
            cid = v.get("cbdb_id")
            if not cid:
                continue
            ids[cid].add(pid)
        for t in tenures:
            cid = t["cbdb_id"]
            if not cid:
                continue
            q = row(cid)
            if not q:
                date_bad.append((t["person_id"], cid, "no-row"))
                continue
            b, de = q["c_birthyear"], q["c_deathyear"]
            if (de and de < t["start_year"] - 1) or (b and b > t["end_year"] + 1):
                date_bad.append((t["person_id"], cid,
                                 f"b={b} d={de} span={t['start_year']}-{t['end_year']}"))
        shared = {str(i): sorted(ns) for i, ns in ids.items() if len(ns) > 1}
        conn.close()
    r["cbdb"] = dict(date_conflicts=date_bad, shared_ids=shared,
                     aligned_tenures=sum(1 for t in tenures if t["cbdb_id"]))

    # 7 衙署
    canon_bad = sorted({t["office"] for t in tenures} - CANON_OFFICES)
    r["offices"] = dict(canon_bad=canon_bad,
                        offices=sorted({t["office"] for t in tenures}))

    # 8 manifest
    manifest = d.get("manifest") or {}
    mstats = manifest.get("stats", {})
    r["manifest"] = dict(entries_claimed=mstats.get("entries"), entries_actual=len(entries),
                         persons_claimed=mstats.get("persons_unique"),
                         persons_actual=len(person_ids),
                         tenure_claimed=(manifest.get("tenure_assembly", {})
                                         .get("stats", {}).get("tenures")),
                         tenure_actual=len(tenures))

    blockers = []
    st = r["structure"]
    if st["dup_segments"] or st["bad_years"] or st["bad_month"] or st["d15"]:
        blockers.append("结构硬错误")
    if r["names"]["pseudo"]:
        blockers.append(f"伪人名 {len(r['names']['pseudo'])}")
    if r["notes"]["active_note_with_other_name"]:
        blockers.append(f"活跃注文含他人名 {r['notes']['active_note_with_other_name']}")
    if r["notes"]["duplicate_entries"]:
        blockers.append(f"重复(年,人,衙)条目 {r['notes']['duplicate_entries']}")
    if r["fragmentation"]["short_unexplained"]:
        blockers.append(f"未解释短缺口 {r['fragmentation']['short_unexplained']}")
    cov = r["coverage"]
    if cov["page_total"] and cov["page_covered"] / cov["page_total"] < 0.9:
        blockers.append(f"页码覆盖不足 {cov['page_covered']}/{cov['page_total']}")
    if r["cbdb"]["date_conflicts"]:
        blockers.append(f"CBDB 生卒/任期冲突 {len(r['cbdb']['date_conflicts'])}")
    if r["cbdb"]["shared_ids"]:
        blockers.append(f"同一 id 多正名 {len(r['cbdb']['shared_ids'])}")
    if r["offices"]["canon_bad"]:
        blockers.append("衙署未登记（不同衙署必须各自独立）")
    if r["names"]["missing_identity"]:
        blockers.append(f"条目缺 person_id {r['names']['missing_identity']}")
    if r["names"]["bad_identity"]:
        blockers.append(f"人物实体跨度异常 {len(r['names']['bad_identity'])}")
    if r["manifest"]["entries_claimed"] not in (None, len(entries)):
        blockers.append("manifest 条目数与实测不一致")
    if r["manifest"]["persons_claimed"] not in (None, len(person_ids)):
        blockers.append("manifest 人物实体数与实测不一致")
    r["blockers"] = blockers
    return r


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = audit()
    s = r["structure"]
    print(f"结构: {s['tenures']} 段 / {s['persons']} 实体（{s['display_persons']} 姓名）/ "
          f"{s['person_years']} 人-年；"
          f"重复段 {s['dup_segments']}，不连续 {s['bad_years']}，D15 {s['d15']}；"
          f"gap 合并 {s['gap_merged']} 段（缺年 {s['gap_years']}）")
    c = r["coverage"]
    print(f"覆盖: 缺年 {len(c['missing_years'])}；各衙缺年 "
          + "，".join(f"{o}:{len(g)}" for o, g in c["office_gaps"].items())
          + f"；页码 {c['page_covered']}/{c['page_total']}")
    print(f"断段: 多段组 {r['fragmentation']['multi_groups']}；未解释缺口 "
          f"{r['fragmentation']['unexplained']}（其中短缺口 {r['fragmentation']['short_unexplained']}）")
    print(f"人名: 伪名 {len(r['names']['pseudo'])}；未映射实体 {r['names']['unmapped_persons']}；"
          f"同名拆分 {len(r['names']['split_names'])} 组")
    res = r["notes"].get("resolution") or {}
    print(f"注文: 活跃注含他人名 {r['notes']['active_note_with_other_name']}；"
          f"重复条目 {r['notes']['duplicate_entries']}；"
          f"隔离 {r['notes']['quarantined']}（推断补注 {res.get('reassigned-inferred',0)} / "
          f"前缀推断 {res.get('restored-prefix-inferred',0)} / "
          f"人工待核 {res.get('manual-review',0)}）；原书补注 {r['notes']['book_patches']}")
    print(f"CBDB: 生卒冲突 {len(r['cbdb']['date_conflicts'])}；同 id 多正名 {len(r['cbdb']['shared_ids'])}；"
          f"对齐 {r['cbdb']['aligned_tenures']}/{s['tenures']}")
    print(f"衙署: {r['offices']['offices']}；非法 {r['offices']['canon_bad']}")
    print(f"manifest: 条目 {r['manifest']['entries_claimed']} vs {r['manifest']['entries_actual']}；"
          f"人物 {r['manifest']['persons_claimed']} vs {r['manifest']['persons_actual']}")
    print("\n阻断项 BLOCKERS:")
    for b in r["blockers"] or ["（无）"]:
        print("  ✗" if r["blockers"] else "  ✓", b)
    if "--json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--json") + 1])
        path.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n明细写入 {path}")


if __name__ == "__main__":
    main()
