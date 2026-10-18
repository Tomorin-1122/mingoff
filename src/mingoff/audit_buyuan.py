# -*- coding: utf-8 -*-
"""部院数据质量审计（可复现门槛，v1）。

用途：在把 official_buyuan.json 接入站点或扩展前，跑一遍"本会话已犯过的错误"清单：
  1. 结构：段年连续、月合法、D15 断限、重复段；
  2. 覆盖：年份/衙署缺行、全年份条目骤降；
  3. 断段：同人同衙「无法解释的中间缺年」（吴道南类）与多余分段；
  4. 人名：伪人名（尾部閏/扈駕/右侍…）、简繁/异体残留、未能映射人数；
  5. 注文错挂：一条注文里出现另一人名、同一 (年,人,衙) 重复条目；
  6. CBDB：生卒/任期冲突、同一 id 挂到多个不同正名；
  7. 声明一致性：manifest 统计 vs 实际数据。

用法：
  python -m mingoff.audit_buyuan            # 控制台摘要
  python -m mingoff.audit_buyuan --json out.json

注意：v1 数据已知不达标（2026-10-18 接收报告），本脚本用退出码 0 只表示"审计跑完"，
不表示质量通过；阻断项见输出 BLOCKERS。
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
# CBDB 快照在会话工作区（仓库外）；仓库单独存放时允许从 CWD 查找
_CBDB_CANDIDATES = [DATA.parents[3] / "_cbdb" / "cbdb_20261010.sqlite3",
                    Path.cwd() / "_cbdb" / "cbdb_20261010.sqlite3",
                    Path("_cbdb/cbdb_20261010.sqlite3")]
CBDB = next((p for p in _CBDB_CANDIDATES if p.is_file()), _CBDB_CANDIDATES[-1])

LEAVE = ("罷", "卒", "致仕", "削籍", "下獄", "被執", "戍", "謫", "丁憂", "憂去",
         "乞歸", "乞休", "養病", "免", "回籍", "為民", "降", "死於難", "死難", "歿於",
         "正法", "自盡", "殉難", "棄市", "革職", "奪官", "奔喪", "守制", "出", "調", "改除")
ENTER = ("入", "任", "起復", "起", "召", "視事", "至京", "復官", "復", "掌", "陞", "升", "遷")
PSEUDO_RE = re.compile(r"(閏|扈駕|右侍|左侍|尚書|侍郎)$")


def _chunks(note: str) -> list[str]:
    return [c.strip() for c in re.split(r"[；;。\n]", note or "") if c.strip()]


def load() -> dict:
    files = {
        "entries": DATA / "vol1_buyuan_entries.json",
        "doc": DATA / "official_buyuan.json",
        "mapping": DATA / "vol1_buyuan_person_cbdb.json",
        "review": DATA / "vol1_buyuan_review.json",
        "manifest": DATA / "vol1_buyuan_manifest.json",
    }
    out = {}
    for k, p in files.items():
        out[k] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    return out


def audit() -> dict:
    d = load()
    entries, doc, mapping = d["entries"], d["doc"], d["mapping"]
    tenures = doc.get("tenures", [])
    report: dict = {}

    # 1 结构
    dup_seg = [k for k, v in Counter(
        (t["person"], t["office"], t["start_year"], t["end_year"]) for t in tenures
    ).items() if v > 1]
    bad_years = [t for t in tenures if t["years"] != list(range(t["start_year"], t["end_year"] + 1))]
    bad_month = [t for t in tenures if any(
        m is not None and not 1 <= m <= 12 for m in (t["start_month"], t["end_month"]))]
    d15 = [t for t in tenures if t["end_year"] > CUT_Y
           or (t["start_year"] == CUT_Y and (t["start_month"] or 1) > 3)
           or (t["end_year"] == CUT_Y and not (t["end_clamped"] and t["end_month"] == 3))]
    report["structure"] = dict(
        tenures=len(tenures), persons=len({t["person"] for t in tenures}),
        person_years=sum(len(t["years"]) for t in tenures),
        dup_segments=len(dup_seg), bad_years=len(bad_years),
        bad_month=len(bad_month), d15=len(d15))

    # 2 覆盖
    years = {e["year"] for e in entries}
    office_years = defaultdict(set)
    for e in entries:
        if e.get("office"):
            office_years[e["office"]].add(e["year"])
    missing_years = [y for y in range(1368, CUT_Y + 1) if y not in years]
    office_gaps = {}
    for o, ys in sorted(office_years.items()):
        lo, hi = min(ys), max(ys)
        office_gaps[o] = [y for y in range(lo, hi + 1) if y not in ys]
    per_year = Counter(e["year"] for e in entries)
    med = sorted(per_year.values())[len(per_year) // 2]
    lows = [(y, c) for y, c in sorted(per_year.items()) if c < med * 0.6]
    report["coverage"] = dict(missing_years=missing_years, office_gaps=office_gaps,
                              per_year_median=med, low_years=lows)

    # 3 断段
    by_po = defaultdict(list)
    for t in tenures:
        by_po[(t["person"], t["office"])].append(t)
    frag, extra = [], 0
    for (p, o), ts in by_po.items():
        if len(ts) < 2:
            continue
        ts.sort(key=lambda x: x["start_year"])
        extra += len(ts) - 1
        gaps = []
        for a, b in zip(ts, ts[1:]):
            gap = b["start_year"] - a["end_year"] - 1
            if gap <= 0:
                continue
            an = " ".join(_chunks(a["note"]))
            bn = " ".join(_chunks(b["note"]))
            explained = any(v in an for v in LEAVE) or any(v in bn for v in ENTER)
            gaps.append(dict(gap=gap, after=a["end_year"], before=b["start_year"],
                             explained=explained))
        unexplained = sum(1 for g in gaps if not g["explained"])
        if gaps:
            frag.append(dict(person=p, office=o, segments=len(ts), gaps=gaps,
                             unexplained=unexplained))
    frag.sort(key=lambda x: (-x["unexplained"], -x["segments"]))
    report["fragmentation"] = dict(multi_groups=len(frag), extra_segments=extra,
                                   unexplained_groups=sum(1 for f in frag if f["unexplained"]),
                                   samples=frag[:15])

    # 4 人名
    persons = {e["person"] for e in entries}
    pseudo = sorted(n for n in persons if PSEUDO_RE.search(n) or len(n) >= 5)
    unmapped = [(n, c) for n, c in Counter(e["person"] for e in entries).most_common()
                if n not in mapping]
    report["names"] = dict(persons=len(persons), pseudo=pseudo,
                           pseudo_entries=sum(1 for e in entries if e["person"] in set(pseudo)),
                           unmapped=unmapped[:30], unmapped_persons=len(unmapped))

    # 5 注文错挂 / 重复条目
    hits = []
    for e in entries:
        note = e.get("note") or ""
        for nm in persons:
            if nm != e["person"] and len(nm) >= 2 and nm in note:
                hits.append((e["year"], e["office"], e["person"], nm))
                break
    dup_entry = [(k, v) for k, v in Counter(
        (e["year"], e["person"], e.get("office")) for e in entries).items() if v > 1]
    report["notes"] = dict(note_with_other_name=len(hits), samples=hits[:15],
                           duplicate_entries=len(dup_entry), dup_samples=dup_entry[:15],
                           empty_start_note=sum(1 for t in tenures if not t["note"].strip()))

    # 6 CBDB
    date_bad, shared = [], {}
    if CBDB.is_file():
        conn = sqlite3.connect(f"file:{CBDB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        def row(pid):
            return conn.execute("SELECT c_name_chn,c_birthyear,c_deathyear FROM BIOG_MAIN "
                                "WHERE c_personid=?", (pid,)).fetchone()

        ids = defaultdict(set)
        for n, v in mapping.items():
            pid = v.get("cbdb_id")
            if not pid:
                continue
            ids[pid].add(n)
        for t in tenures:
            pid = t["cbdb_id"]
            if not pid:
                continue
            r = row(pid)
            if not r:
                date_bad.append((t["person"], pid, "no-row"))
                continue
            b, de = r["c_birthyear"], r["c_deathyear"]
            if (de and de < t["start_year"] - 1) or (b and b > t["end_year"] + 1):
                date_bad.append((t["person"], pid,
                                 f"b={b} d={de} span={t['start_year']}-{t['end_year']}"))
        shared = {str(i): sorted(ns) for i, ns in ids.items() if len(ns) > 1}
        conn.close()
    report["cbdb"] = dict(date_conflicts=date_bad, shared_ids=shared,
                          aligned_tenures=sum(1 for t in tenures if t["cbdb_id"]))

    # 7 manifest 一致性
    manifest = d["manifest"]
    mstats = manifest.get("stats", {})
    report["manifest"] = dict(
        entries_claimed=mstats.get("entries"), entries_actual=len(entries),
        persons_claimed=mstats.get("persons_unique"), persons_actual=len(persons),
        tenure_claimed=manifest.get("tenure_assembly", {}).get("stats", {}).get("tenures"),
        tenure_actual=len(tenures),
        gates=manifest.get("tenure_assembly", {}).get("gates", {}),
        known_limits=manifest.get("tenure_assembly", {}).get("known_limits", []),
    )

    # 阻断项
    blockers = []
    if report["structure"]["dup_segments"] or report["structure"]["bad_years"] \
            or report["structure"]["d15"]:
        blockers.append("结构层有硬错误")
    if report["fragmentation"]["unexplained_groups"] > 0:
        blockers.append(f"无法解释的断段 {report['fragmentation']['unexplained_groups']} 组"
                        f"（多余分段 {report['fragmentation']['extra_segments']}）")
    if report["names"]["pseudo"]:
        blockers.append(f"伪人名 {len(report['names']['pseudo'])} 个")
    if report["notes"]["note_with_other_name"]:
        blockers.append(f"注文疑似错挂 {report['notes']['note_with_other_name']} 条")
    if report["cbdb"]["date_conflicts"]:
        blockers.append(f"CBDB 生卒/任期冲突 {len(report['cbdb']['date_conflicts'])} 人")
    if report["cbdb"]["shared_ids"]:
        blockers.append(f"同一 CBDB id 多正名 {len(report['cbdb']['shared_ids'])} 组")
    report["blockers"] = blockers
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    r = audit()
    s = r["structure"]
    print(f"结构: {s['tenures']} 段 / {s['persons']} 人 / {s['person_years']} 人-年；"
          f"重复段 {s['dup_segments']}，段年不连续 {s['bad_years']}，D15 违规 {s['d15']}")
    c = r["coverage"]
    print(f"覆盖: 缺年 {len(c['missing_years'])}；各衙缺年 "
          + "，".join(f"{o}:{len(g)}" for o, g in c["office_gaps"].items()))
    print(f"断段: 多段组 {r['fragmentation']['multi_groups']}，多余分段 "
          f"{r['fragmentation']['extra_segments']}，无法解释组 {r['fragmentation']['unexplained_groups']}")
    print(f"人名: 伪人名 {len(r['names']['pseudo'])}（条目 {r['names']['pseudo_entries']}）；"
          f"未映射 {r['names']['unmapped_persons']} 人")
    print(f"注文: 含他人名 {r['notes']['note_with_other_name']} 条；"
          f"重复(年,人,衙)条目 {r['notes']['duplicate_entries']}；空段首注 {r['notes']['empty_start_note']}")
    print(f"CBDB: 生卒冲突 {len(r['cbdb']['date_conflicts'])}；同 id 多正名 {len(r['cbdb']['shared_ids'])}；"
          f"段级对齐 {r['cbdb']['aligned_tenures']}/{s['tenures']}")
    print(f"manifest: 条目 {r['manifest']['entries_claimed']} vs {r['manifest']['entries_actual']}；"
          f"人物 {r['manifest']['persons_claimed']} vs {r['manifest']['persons_actual']}")
    print("\n阻断项 BLOCKERS:")
    for b in r["blockers"]:
        print("  ✗", b)
    if "--json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--json") + 1])
        path.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n明细写入 {path}")


if __name__ == "__main__":
    main()
