# -*- coding: utf-8 -*-
"""跨表 CBDB 一致性检查：同一人名在多张表的 cbdb_id 必须一致。

输入：src/mingoff/data/*_person_cbdb*.json（各表映射）+ official_*.json（段）
输出：控制台异常清单（同名人多表 id 冲突 / 表内 person_id 分代 id 相异 / 同 id 异名）。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).resolve().parents[1] / "src" / "mingoff" / "data"

MAPS = {
    "部院": "vol1_buyuan_person_cbdb_v4.json",
    "京卿": "vol1_jingqing_person_cbdb_v1.json",
    "侍郎": "vol1_shilang_person_cbdb_v1.json",
    "六科": "vol2_kejishizhong_person_cbdb_v1.json",
    "京营": "vol3_jingying_person_cbdb_v1.json",
    "总督": "vol3_zongdu_person_cbdb_v1.json",
    "巡抚": "vol3_xunfu_person_cbdb_v1.json",
}


def main():
    person_ids = defaultdict(dict)   # name → {table: (cbdb_id, pid)}
    for tbl, f in MAPS.items():
        p = DATA / f
        if not p.is_file():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        # 映射形态：{name: {"cbdb_id":..., "person_id":...}} 或 {name: int}
        for name, v in m.items():
            if isinstance(v, dict):
                cid = v.get("cbdb_id")
                pid = v.get("person_id") or name
            else:
                cid, pid = v, name
            if cid is not None:
                person_ids[name][tbl] = (cid, pid)

    conflicts = []
    for name, per_tbl in sorted(person_ids.items()):
        ids = {cid for cid, _ in per_tbl.values()}
        if len(ids) > 1:
            conflicts.append((name, {t: c for t, (c, _) in per_tbl.items()}))
    print(f"跨表同名人对齐人数: {len(person_ids)}；id 冲突: {len(conflicts)}")
    for name, per in conflicts[:25]:
        print(f"  {name}: {per}")

    # 同 id 异名（一个 CBDB 人挂到多个显示名——可能正常（别名），列出人工复核）
    id_names = defaultdict(set)
    for name, per_tbl in person_ids.items():
        for cid, _ in per_tbl.values():
            id_names[cid].add(name)
    multi = {c: ns for c, ns in id_names.items() if len(ns) > 1}
    print(f"同 id 异名组: {len(multi)}（别名属正常，抽样列前 12）")
    for c, ns in list(multi.items())[:12]:
        print(f"  {c}: {sorted(ns)}")

    # 各表未对齐率
    for tbl, f in MAPS.items():
        p = DATA / f
        if not p.is_file():
            print(f"{tbl}: 映射缺失")
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        tot = len(m)
        ok = sum(1 for v in m.values()
                 if (v.get("cbdb_id") if isinstance(v, dict) else v) is not None)
        print(f"{tbl}: 对齐 {ok}/{tot}（{round(100*ok/max(tot,1))}%）")


if __name__ == "__main__":
    main()
