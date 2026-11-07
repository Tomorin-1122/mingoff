# -*- coding: utf-8 -*-
"""部院人物 CBDB 增量对齐：official_buyuan 未对齐人名 → vol1_buyuan_person_cbdb_v4.json。

判据（规范 3.2 + match_cbdb 8 层思想，宁空勿误挂）：
  1. 候选集 = BIOG_MAIN 精确同名 ∪ ALTNAME_DATA 别名同名；
  2. 简体/异体名先经归一表（add 补行里的简体名，如 邓愈→鄧愈）；
  3. 唯一候选 + 明代 + 生卒与任期不相斥 → 挂（exact-unique）；
  4. 多候选打分：时间相容（index_year/生卒 与段 span 重叠）+ 部院任职记录
     （POSTED_TO_OFFICE_DATA 任过本部尚书/侍郎/都御史等且年份相交）；
     唯一最高分且 ≥ 2 分才挂，并列/不足 → NULL + discrepancy；
  5. 输出合并 v3 旧映射（不覆盖人工结果），新记录带 method/score 依据。

用法：PYTHONPATH=src python scripts/match_buyuan_cbdb.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
CBDB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")
OUT_V4 = DATA / "vol1_buyuan_person_cbdb_v4.json"
OUT_REVIEW = DATA / "vol1_buyuan_cbdb_unresolved.json"

# 简体→繁体（校记 add 人名归一；只映射确证字形，不做整表转换）
S2T = {"邓": "鄧", "刘": "劉", "冲": "沖", "赵": "趙", "凯": "凱", "万": "萬",
       "吴": "吳", "吕": "呂", "张": "張", "陈": "陳", "杨": "楊", "黄": "黃",
       "马": "馬", "许": "許", "冯": "馮", "蒋": "蔣", "韩": "韓", "孙": "孫",
       "郑": "鄭", "王": "王", "李": "李"}

# 部院任职判定：office → CBDB 任职表可采信的官名关键词
OFFICE_HINT = {
    "吏部": ["吏部尚書", "吏部侍郎"], "戶部": ["戶部尚書", "戶部侍郎"],
    "禮部": ["禮部尚書", "禮部侍郎"], "兵部": ["兵部尚書", "兵部侍郎"],
    "刑部": ["刑部尚書", "刑部侍郎"], "工部": ["工部尚書", "工部侍郎"],
    "都察院": ["左都御史", "右都御史", "左副都御史", "右副都御史", "都御史"],
    "御史臺": ["御史大夫", "御史中丞", "治書侍御史"],
    "御史府": ["御史大夫", "御史中丞"],
    "總督倉場": ["總督倉場"], "總倉場": ["總督倉場"], "總督京儲": ["總督京儲"],
}
HINT_FALLBACK = ["尚書", "都御史", "侍郎", "御史"]
# 仕历链证据（2026-11-07 自 match_official_cbdb.py 同步）：本衙系统内任意职
# （部郎中/主事、监察御史等迁转链）±6 年 → +0.5，同姓守卫下唯一强分差才挂
CAREER_HINT = {
    "吏部": ["吏部"], "戶部": ["戶部"], "禮部": ["禮部"], "兵部": ["兵部"],
    "刑部": ["刑部"], "工部": ["工部"],
    "都察院": ["御史"], "御史臺": ["御史"], "御史府": ["御史"],
    "總督倉場": ["總督倉場"], "總倉場": ["總督倉場"], "總督京儲": ["總督京儲"],
}
CAREER_FALLBACK = ["尚書", "侍郎", "御史"]


def t2s_norm(name: str) -> str:
    return "".join(S2T.get(ch, ch) for ch in name)


def span_compat(birth, death, iy, lo, hi) -> float:
    """生卒与段 span 的相容分：闭区间重叠年数/段长（含端点 +1——单年段与窗恰交是
    真重叠，旧式把「卒年=任末」误判硬冲突，曾秉正案例），无生卒给中性分 0.5。
    无生卒但有 index_year（软证据）：窗 iy−30..iy+50 命中 0.7 / 未中 0.0，
    可拉开并列但不触发硬拒（宁空勿误挂由 ambiguous 兜底）。
    """
    if birth is None and death is None:
        if iy:
            wb, we = iy - 30, iy + 50
            return 0.7 if (min(hi, we) - max(lo, wb) + 1) > 0 else 0.0
        return 0.5
    b = birth if birth is not None else -9999
    d = death if death is not None else 9999
    wb, we = b + 15, d
    ov = max(0, min(hi, we) - max(lo, wb) + 1)
    if ov > 0:
        return min(1.0, ov / max(1, hi - lo + 1))
    # 完全不相交：卒年早于段起点 40 年以上 → 硬冲突
    if we < lo - 40:
        return -1.0
    return 0.0


def main() -> int:
    doc = json.loads((DATA / "official_buyuan.json").read_text(encoding="utf-8"))
    tenures = doc["tenures"]
    old_map = {}
    for v in ("vol1_buyuan_person_cbdb_v4.json", "vol1_buyuan_person_cbdb_v3.json",
              "vol1_buyuan_person_cbdb.json"):
        p = DATA / v
        if p.is_file():
            old_map.update(json.loads(p.read_text(encoding="utf-8")))
            break
    con = sqlite3.connect(str(CBDB))

    # 预载内存索引（一次全扫，避免逐实体查询全表扫）
    print("预载 CBDB 索引…", flush=True)
    postings: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for cpid, chn, fy, ly in con.execute(
            "select p.c_personid, o.c_office_chn, p.c_firstyear, p.c_lastyear "
            "from POSTED_TO_OFFICE_DATA p join OFFICE_CODES o on o.c_office_id=p.c_office_id"):
        # 年份缺失时有限外推（±30 年），绝不当作无限窗——否则生卒冲突的人会假相交
        fy2 = fy or 0
        ly2 = ly if ly else (fy2 + 30 if fy2 else 9999)
        postings[cpid].append((chn, fy2, min(ly2, 9999)))
    altnames: dict[str, set[int]] = defaultdict(set)
    for cpid, alt in con.execute("select c_personid, c_alt_name_chn from ALTNAME_DATA"):
        if alt:
            altnames[alt].add(cpid)
    print(f"  任职记录 {sum(len(v) for v in postings.values())} 条 / 别名 {len(altnames)} 项", flush=True)

    # 按 person_id 聚合段（span + office 集合）
    by_pid: dict[str, dict] = {}
    for t in tenures:
        pid = t["person_id"]
        e = by_pid.setdefault(pid, {"person": t["person"], "span": [t["start_year"], t["end_year"]],
                                    "offices": set(), "aligned": bool(t.get("cbdb_id"))})
        e["span"][0] = min(e["span"][0], t["start_year"])
        e["span"][1] = max(e["span"][1], t["end_year"])
        e["offices"].add(t["office"])
    todo = [p for p, e in by_pid.items() if not e["aligned"]]
    # 人工既定 NULL 名单（D44：嘉靖李本与洪武呂本非一人，李本 CBDB 身份未核定保持 NULL；
    # CBDB 把「李本」收作呂本 128301 的别名形态，打分制会误挂）
    KEEP_NULL = {"李本"}
    todo = [p for p in todo if p not in KEEP_NULL]
    print(f"未对齐实体 {len(todo)} 个（人名 {len({by_pid[p]['person'] for p in todo})}），开始对齐")

    new_map: dict[str, dict] = {}
    unresolved = []
    for pid in todo:
        e = by_pid[pid]
        name, (lo, hi), offices = e["person"], e["span"], e["offices"]
        qname = t2s_norm(name)
        # 候选集：本名 + 别名
        cands = {r[0]: r[1:] for r in con.execute(
            "select c_personid, c_name_chn, c_birthyear, c_deathyear, c_index_year "
            "from BIOG_MAIN where c_name_chn in (?, ?)", (name, qname))}
        for cpid in (altnames.get(name, set()) | altnames.get(qname, set())):
            if cpid in cands:
                continue
            r = con.execute("select c_name_chn, c_birthyear, c_deathyear, c_index_year "
                            "from BIOG_MAIN where c_personid=?", (cpid,)).fetchone()
            if r:
                cands[cpid] = r
        if not cands:
            unresolved.append({"person_id": pid, "name": name, "reason": "no-candidate"})
            continue

        hints = sorted({h for o in offices for h in OFFICE_HINT.get(o, HINT_FALLBACK)})
        career_stems = sorted({s for o in offices for s in CAREER_HINT.get(o, CAREER_FALLBACK)})
        sur = t2s_norm(name)[0]  # 同姓守卫：任职证据要求候选与本实体同姓（S2T 归一）
        scored = []
        for cpid, (cn, birth, death, iy) in cands.items():
            s_time = span_compat(birth, death, iy, lo, hi)
            # 生卒明确且与段完全不相交 = 硬冲突：任职记录再像也不挂
            # （外推 30 年仍可能假相交，如翁正春 1545-1607 vs 段 1610-1613）
            if s_time <= 0 and (birth is not None or death is not None):
                continue
            if s_time < 0:
                continue
            # 任职记录分：任过本衙相关官且年份相交（同姓守卫——前任/继任同名不同姓
            # 是高发混淆，如 趙榮 大理寺卿 1461-63 vs 王榮 大理卿 1465）
            s_office = 0.0
            sur_ok = bool(cn) and t2s_norm(cn)[0] == sur
            if sur_ok:
                for chn, fy, ly in postings.get(cpid, ()):
                    if fy <= hi and ly >= lo and any(h in chn for h in hints):
                        s_office = 1.0
                        break
            # 仕历链分：本衙系统内任意职、窗 ±6 年
            s_career = 0.0
            if sur_ok:
                for chn, fy, ly in postings.get(cpid, ()):
                    if fy <= hi + 6 and ly >= lo - 6 and any(s in chn for s in career_stems):
                        s_career = 0.5
                        break
            score = s_time + s_office + s_career
            scored.append({"id": cpid, "name": cn, "birth": birth, "death": death,
                           "iy": iy, "s_time": round(s_time, 2), "s_office": s_office,
                           "s_career": s_career, "score": round(score, 2)})
        if not scored:
            unresolved.append({"person_id": pid, "name": name, "reason": "time-conflict"})
            continue
        scored.sort(key=lambda s: -s["score"])
        top, second = scored[0], (scored[1] if len(scored) > 1 else None)
        if len(scored) == 1 and top["score"] >= 0.5:
            m = "exact-unique"
        elif second is None or (top["score"] - second["score"] > 0.4
                                and top["score"] >= 1.0):
            m = "scored-unique"
        elif (top["score"] == 0.7 and second["score"] == 0.0
              and all(s["score"] == 0.0 for s in scored[1:])):
            # era-unique：无生卒，唯一年代锚合窗，其余候选全部年代相斥
            m = "era-unique"
        else:
            unresolved.append({"person_id": pid, "name": name, "reason": "ambiguous",
                               "cands": scored[:4]})
            continue
        new_map[pid] = {"cbdb_id": top["id"], "cbdb_name": top["name"], "method": m,
                        "score": top["score"], "birth": top["birth"], "death": top["death"],
                        "span": [lo, hi]}
    merged = dict(old_map)
    merged.update(new_map)
    OUT_V4.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_REVIEW.write_text(json.dumps({"unresolved": unresolved}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print(f"新增对齐 {len(new_map)}；仍未决 {len(unresolved)}（→ {OUT_REVIEW.name}）；"
          f"总映射 {len(merged)} → {OUT_V4.name}")
    print("方法分布:", defaultdict(int, {m.split('-')[0]: sum(1 for v in new_map.values()
          if v['method'].startswith(m.split('-')[0])) for m in {v['method'] for v in new_map.values()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
