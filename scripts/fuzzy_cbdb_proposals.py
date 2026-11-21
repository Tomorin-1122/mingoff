# -*- coding: utf-8 -*-
"""CBDB 形讹反查：Paddle 人名识别错误（束/東、進/邊、簡繁混）→ 编辑距离≤1 检索。

输入：src/mingoff/data/vol{3_zongbing,4_buzhengshi}_cbdb_unresolved.json（matcher 未决）
判据（高置信才采纳）：
  1. CBDB BIOG_MAIN 中与该名（简→繁归一后）同长且编辑距离 ≤1 的名字；
  2. 生卒窗**硬包含**段区间（birth+15 ≤ span_lo 且 death ≥ span_hi）或唯一候选且
     index_year 落段窗内；
  3. 唯一命中才输出提案（多于一个候选 → 留 unresolved 不动）。
输出：_scratch/cbdb_fuzzy_proposals.json（提案清单，不改映射——人工复核后并入 manual）。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from match_official_cbdb import S2T, CBDB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
OUT = ROOT / "_scratch" / "cbdb_fuzzy_proposals.json"

TABLES = {
    "总兵": ("vol3_zongbing_cbdb_unresolved.json", "official_zongbing.json"),
    "布政使": ("vol4_buzhengshi_cbdb_unresolved.json", "official_buzhengshi.json"),
}


def t2s(name: str) -> str:
    return "".join(S2T.get(ch, ch) for ch in name)


def edit1(a: str, b: str) -> bool:
    if a == b or len(a) != len(b):
        return False
    return sum(x != y for x, y in zip(a, b)) == 1


def main():
    con = sqlite3.connect(str(CBDB))
    biog = []
    for cpid, cn, b, d, iy in con.execute(
            "select c_personid,c_name_chn,c_birthyear,c_deathyear,c_index_year from BIOG_MAIN"):
        biog.append((cpid, cn, b, d, iy))
    proposals = {}
    for tbl, (unres, official) in TABLES.items():
        ents = json.loads((DATA / official).read_text(encoding="utf-8"))["tenures"]
        span_of: dict[str, tuple[int, int]] = {}
        for t in ents:
            lo, hi = span_of.get(t["person"], (9999, 0))
            span_of[t["person"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
        u = json.loads((DATA / unres).read_text(encoding="utf-8"))
        items = u.get("unresolved") or []
        names = sorted({it["person_id"] for it in items})
        out = []
        for name in names:
            span = span_of.get(name)
            if not span:
                continue
            lo, hi = span
            cands = []
            for target in (name, t2s(name)):
                for cpid, cn, b, d, iy in biog:
                    if edit1(target, cn):
                        if b is not None and d is not None:
                            if b + 15 <= lo and d >= hi:
                                cands.append((cpid, cn, b, d, iy, "hard"))
                        elif iy and lo - 25 <= iy <= hi + 10:
                            cands.append((cpid, cn, b, d, iy, "index"))
            uniq = {(c[0], c[1]) for c in cands}
            if len(uniq) == 1:
                cpid, cn, b, d, iy, kind = cands[0]
                out.append({"name": name, "cbdb_name": cn, "id": cpid,
                            "bio": f"{b}-{d},idx{iy}", "kind": kind, "span": [lo, hi]})
        proposals[tbl] = out
        print(f"{tbl}: 未决 {len(names)} → 形讹唯一提案 {len(out)}")
        for pr in out[:15]:
            print(f"  {pr['name']} → {pr['cbdb_name']} #{pr['id']} {pr['bio']} "
                  f"[{pr['kind']}] 段{pr['span']}")
    OUT.write_text(json.dumps(proposals, ensure_ascii=False, indent=1),
                   encoding="utf-8")


if __name__ == "__main__":
    main()
