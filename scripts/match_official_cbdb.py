# -*- coding: utf-8 -*-
"""京卿/六科人物 CBDB 对齐：official_{jingqing,kejishizhong} 未对齐实体 → person_cbdb_v1.json。

判据同部院 match_buyuan_cbdb.py（规范 3.2 + match_cbdb 8 层思想，宁空勿误挂）：
  1. 候选集 = BIOG_MAIN 精确同名 ∪ ALTNAME_DATA 别名同名（本名+简/繁归一形）；
  2. 生卒与段 span 完全不相斥才入围（卒年早于段起点 40 年+ = 硬冲突，任职再像也不挂）；
  3. 打分 = 时间相容（生卒窗重叠/段长）+ 本衙任职记录（POSTED_TO_OFFICE_DATA 年份相交
     且官名含本表关键词）；
  4. 唯一候选 ≥0.5 或 分差 >0.4 且 ≥1.0 才挂；并列/不足 → unresolved（top-4 留档）；
  5. MANUAL_MAP 人工裁决优先（method=manual / manual-null，带 note 留痕）；
     旧映射文件存在则合并、不覆盖人工结果。

用法：PYTHONPATH=src python scripts/match_official_cbdb.py [--table jingqing|kejishizhong]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
CBDB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")

# 简体→繁体（同部院：只映射确证字形）
S2T = {"邓": "鄧", "刘": "劉", "冲": "沖", "赵": "趙", "凯": "凱", "万": "萬",
       "吴": "吳", "吕": "呂", "张": "張", "陈": "陳", "杨": "楊", "黄": "黃",
       "马": "馬", "许": "許", "冯": "馮", "蒋": "蔣", "韩": "韓", "孙": "孫",
       "郑": "鄭", "王": "王", "李": "李"}

# 表配置：输入 / 输出 / 本衙任职官名关键词（CBDB OFFICE_CODES 官名子串）/ 人工裁决
# 关键词精度原则：只认本表座主官（如「司通政使」不会命中右通政；「X科都給事中」不命中左右給事中）
TABLES: dict[str, dict] = {
    "jingqing": {
        "title": "京卿年表（京師）",
        "input": "official_jingqing.json",
        "out_map": "vol1_jingqing_person_cbdb_v1.json",
        "out_review": "vol1_jingqing_cbdb_unresolved.json",
        "old_maps": ["vol1_jingqing_person_cbdb_v1.json"],   # 自合并：重跑不覆盖人工/既有结果
        "office_hint": {
            "通政使": ["通政使司通政使"],
            "大理卿": ["大理寺卿", "大理卿"],
            "太常卿": ["太常寺卿", "太常卿"],
            "光祿卿": ["光祿寺卿", "光祿卿"],
            "太僕卿": ["太僕寺卿", "太僕卿"],
            "鴻臚卿": ["鴻臚寺卿", "鴻臚卿"],
            "尚寶卿": ["尚寶司卿", "尚寶卿"],
            "順天府府尹": ["順天府府尹", "府尹"],
        },
        "hint_fallback": ["卿", "府尹"],
        "keep_null": set(),       # 人工既定 NULL（如部院李本 D44），留待 review 后增补
        "manual": {               # person_id → {"id": int|None, "note": str}，人工裁决留痕
            # 曾秉正 66533：CBDB 通政使 1377–1382 任职记录 + 卒 1382，与段 [1382,1382] 吻合
            "曾秉正": {"id": 66533,
                      "note": "CBDB 通政使 1377–1382 任职记录 + 卒 1382，段 [1382,1382] 吻合"},
            # 汪宗尹：CBDB 无此人条目（收作汪宗伊 127510 别名），但书内 1570–71 尚寶卿与
            # 1573–74 光祿卿（汪宗伊）是相邻两任，同一人还是兄弟两人待考 → NULL 留待正字轮
            "汪宗尹": {"id": None,
                      "note": "CBDB 无条目（仅作汪宗伊别名收）；与汪宗伊 1573–74 是相邻两任，"
                              "同一人抑或两人待考，宁空勿误挂"},
        },
    },
    "kejishizhong": {
        "title": "六科都給事中年表",
        "input": "official_kejishizhong.json",
        "out_map": "vol2_kejishizhong_person_cbdb_v1.json",
        "out_review": "vol2_kejishizhong_cbdb_unresolved.json",
        "old_maps": ["vol2_kejishizhong_person_cbdb_v1.json"],   # 自合并
        "office_hint": {
            "吏科": ["吏科都給事中", "都給事中"],
            "戶科": ["戶科都給事中", "都給事中"],
            "禮科": ["禮科都給事中", "都給事中"],
            "兵科": ["兵科都給事中", "都給事中"],
            "刑科": ["刑科都給事中", "都給事中"],
            "工科": ["工科都給事中", "都給事中"],
        },
        "hint_fallback": ["都給事中"],
        "keep_null": set(),
        "manual": {
            # 凌義渠 34757：生卒 1593–1644 与史实吻合（甲申殉节），京卿表同名 scored-unique 同证
            "凌義渠": {"id": 34757,
                      "note": "生卒 1593–1644 与史实吻合；京卿表同名候选 scored-unique 同证"},
            # 薛國觀 362351：index 1589 与天啟/崇禎朝仕历相合（另一候选 133302 无任何年代信息）
            "薛國觀": {"id": 362351,
                      "note": "index 1589 与天啟/崇禎朝仕历相合；另一候选 133302 无任何年代信息"},
            # 范淑泰 360850：index 1598 与崇禎初工科給事中仕历相合（另一候选无年代信息）
            "范淑泰": {"id": 360850,
                      "note": "index 1598 与崇禎初工科給事中仕历相合；另一候选无年代信息"},
            # 張孔教 125527：卒 1644 + index 1581，与 吏科 1617 署–1622 遷 仕历相合；
            # 另一候选 345329 无任何年代/任职信息
            "張孔教": {"id": 125527,
                      "note": "卒 1644 + index 1581 与吏科 1617–1622 仕历相合；另一候选无年代信息"},
        },
    },
}


def t2s_norm(name: str) -> str:
    return "".join(S2T.get(ch, ch) for ch in name)


def span_compat(birth, death, iy, lo, hi) -> float:
    """生卒与段 span 的相容分：重叠年数/段长，无生卒给中性分 0.5。

    生卒窗 = birth+15 .. death（含端点，重叠按闭区间年数 +1 计——单年段与窗恰交
    是真重叠，不是 0）。
    无生卒但有 index_year（中举/入仕年代锚，软证据）：窗 iy−30..iy+50 命中给 0.7、
    未命中给 0.0——可拉开并列但不触发硬拒（宁空勿误挂仍由 ambiguous 兜底）。
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
    if we < lo - 40:
        return -1.0
    return 0.0


def match_table(key: str, cfg: dict, con: sqlite3.Connection,
                postings: dict[int, list[tuple[str, int, int]]],
                altnames: dict[str, set[int]],
                biog_by_name: dict[str, list[tuple]],
                biog_by_id: dict[int, tuple]) -> tuple[dict, list[dict]]:
    doc = json.loads((DATA / cfg["input"]).read_text(encoding="utf-8"))
    by_pid: dict[str, dict] = {}
    for t in doc["tenures"]:
        pid = t["person_id"]
        e = by_pid.setdefault(pid, {"person": t["person"],
                                    "span": [t["start_year"], t["end_year"]],
                                    "offices": set(), "aligned": bool(t.get("cbdb_id"))})
        e["span"][0] = min(e["span"][0], t["start_year"])
        e["span"][1] = max(e["span"][1], t["end_year"])
        e["offices"].add(t["office"])

    old_map: dict[str, dict] = {}
    for v in cfg["old_maps"]:
        p = DATA / v
        if p.is_file():
            old_map.update(json.loads(p.read_text(encoding="utf-8")))
            break

    keep_null = cfg["keep_null"]
    manual: dict[str, dict] = cfg["manual"]
    todo = [p for p, e in by_pid.items()
            if not e["aligned"] and p not in keep_null and p not in manual]
    print(f"[{key}] {cfg['title']}：未对齐实体 {len(todo)} 个"
          f"（keep_null {len(keep_null)} / manual {len(manual)}），开始对齐")

    new_map: dict[str, dict] = {}
    unresolved: list[dict] = []

    # 人工裁决优先
    for pid, spec in manual.items():
        e = by_pid.get(pid)
        if e is None:
            continue
        lo, hi = e["span"]
        if spec["id"] is None:
            new_map[pid] = {"cbdb_id": None, "cbdb_name": e["person"],
                            "method": "manual-null", "score": None,
                            "birth": None, "death": None, "span": [lo, hi],
                            "note": spec.get("note", "")}
            continue
        r = biog_by_id.get(spec["id"])
        if not r:
            unresolved.append({"person_id": pid, "name": e["person"],
                               "reason": "manual-id-not-found", "manual_id": spec["id"]})
            continue
        new_map[pid] = {"cbdb_id": spec["id"], "cbdb_name": r[0],
                        "method": "manual", "score": None,
                        "birth": r[1], "death": r[2], "span": [lo, hi],
                        "note": spec.get("note", "")}

    for pid in todo:
        e = by_pid[pid]
        name, (lo, hi), offices = e["person"], e["span"], e["offices"]
        qname = t2s_norm(name)
        cands = {r[0]: r[1:] for r in
                 biog_by_name.get(name, []) + biog_by_name.get(qname, [])}
        for cpid in (altnames.get(name, set()) | altnames.get(qname, set())):
            if cpid in cands:
                continue
            r = biog_by_id.get(cpid)
            if r:
                cands[cpid] = r
        if not cands:
            unresolved.append({"person_id": pid, "name": name, "reason": "no-candidate"})
            continue

        hints = sorted({h for o in offices for h in
                        cfg["office_hint"].get(o, cfg["hint_fallback"])})
        scored = []
        for cpid, (cn, birth, death, iy) in cands.items():
            s_time = span_compat(birth, death, iy, lo, hi)
            if s_time <= 0 and (birth is not None or death is not None):
                continue
            if s_time < 0:
                continue
            s_office = 0.0
            for chn, fy, ly in postings.get(cpid, ()):
                if fy <= hi and ly >= lo and any(h in chn for h in hints):
                    s_office = 1.0
                    break
            score = s_time + s_office
            scored.append({"id": cpid, "name": cn, "birth": birth, "death": death,
                           "iy": iy, "s_time": round(s_time, 2), "s_office": s_office,
                           "score": round(score, 2)})
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
            # era-unique：无生卒，唯一年代锚合窗，其余候选全部年代相斥——
            # 1.0 门槛是为有生卒/任职分的候选定的；纯 index_year 案例里
            # 「合窗 vs 相斥」对比即强证据。任一候选未相斥（≥0.5）则仍拒绝。
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
    (DATA / cfg["out_map"]).write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / cfg["out_review"]).write_text(
        json.dumps({"unresolved": unresolved}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    dist = Counter(v["method"] for v in new_map.values())
    print(f"[{key}] 新增对齐 {len(new_map)}；仍未决 {len(unresolved)}"
          f"（→ {cfg['out_review']}）；总映射 {len(merged)} → {cfg['out_map']}")
    print(f"[{key}] 方法分布: {dict(dist)}")
    return merged, unresolved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=sorted(TABLES), default=None,
                    help="只跑指定表；缺省两表都跑")
    args = ap.parse_args()
    if not CBDB.is_file():
        print(f"CBDB 库缺失: {CBDB}", file=sys.stderr)
        return 1
    con = sqlite3.connect(str(CBDB))

    print("预载 CBDB 索引…", flush=True)
    postings: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for cpid, chn, fy, ly in con.execute(
            "select p.c_personid, o.c_office_chn, p.c_firstyear, p.c_lastyear "
            "from POSTED_TO_OFFICE_DATA p join OFFICE_CODES o on o.c_office_id=p.c_office_id"):
        fy2 = fy or 0
        ly2 = ly if ly else (fy2 + 30 if fy2 else 9999)
        postings[cpid].append((chn, fy2, min(ly2, 9999)))
    altnames: dict[str, set[int]] = defaultdict(set)
    for cpid, alt in con.execute("select c_personid, c_alt_name_chn from ALTNAME_DATA"):
        if alt:
            altnames[alt].add(cpid)
    # BIOG_MAIN 也一次全扫进内存（c_name_chn 无索引，逐候选查询 = 每次全表扫 66 万行）
    biog_by_name: dict[str, list[tuple]] = defaultdict(list)
    biog_by_id: dict[int, tuple] = {}
    for cpid, cn, b, d, iy in con.execute(
            "select c_personid, c_name_chn, c_birthyear, c_deathyear, c_index_year "
            "from BIOG_MAIN"):
        row = (cn, b, d, iy)
        biog_by_name[cn].append((cpid,) + row)
        biog_by_id[cpid] = row
    print(f"  任职记录 {sum(len(v) for v in postings.values())} 条 / 别名 {len(altnames)} 项 / "
          f"人名 {len(biog_by_name)} 项", flush=True)

    for key, cfg in TABLES.items():
        if args.table and key != args.table:
            continue
        match_table(key, cfg, con, postings, altnames, biog_by_name, biog_by_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
