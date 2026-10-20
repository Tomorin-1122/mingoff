# -*- coding: utf-8 -*-
"""最终对齐管线（生产版）：把 8 层判据固化成可复用的模块。

层序（每层只在前面未决时生效）：
  L1 原名唯一命中
  L2 别名表（人工核定的形近/异体）
  L3 简繁归一
  L4 时间消歧（生卒 + index_year 打分）
  L5 官职履历（内阁/殿阁/翰林类任职）
  L6 CBDB 内部重复归一 + 唯一非空壳
  L7 明代限定过滤
  L8 形近模糊（同姓等长编辑距离 1 + 履历 + 时间，唯一最高分）
未决者写 discrepancy 清单，cbdb_id 留 NULL（D6 纪律：宁留空不误挂）。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CBDB = Path(r"_cbdb/cbdb_20261010.sqlite3")
ENTRIES = Path(r"mingoff/src/mingoff/data/neige_entries.json")
OUT = Path(r"mingoff/src/mingoff/data/person_cbdb.json")
REVIEW = Path(r"mingoff/src/mingoff/data/cbdb_unresolved.json")

# ---------- 人工核定映射（逐条核验，理由见注释）----------
MANUAL_ALIAS = {
    # 简繁/异体
    "吴": "吳", "张": "張", "温": "溫", "黄": "黃", "吕": "呂", "万": "萬",
    # 形近 OCR 错字（核验：原文上下文 + CBDB 履历 + 时间吻合）
    "李國檜": "李國𣚴",   # 崇祯内阁
    "韓燷": "韓爌", "韓煖": "韓爌", "韓煥": "韓爌", "韓燥": "韓爌", "韓瘠": "韓爌",
    "林釘": "林釬", "林鈺": "林釬",       # 崇祯礼部/国子监
    "石珔": "石珤", "石珘": "石珤",
    "吳蛍": "吳甡",                       # 崇祯内阁
    "商軫": "商輅", "商輔": "商輅",
    "謝邋": "謝遷", "郭鑿": "郭樸", "馮鈴": "馮銓", "馮鉓": "馮銓",
    "孫應縈": "孫應鰲", "孫應繁": "孫應鰲", "王錫衰": "王錫爵", "汪鎧": "汪諧",
    "江如璧": "江瀾", "解繒": "解縉", "費案": "費宏",
    "陳於陛": "陳于陛", "陳於陞": "陳于陛", "趙志皐": "趙志皋",
    "沈滇": "沈㴶", "沈滙": "沈㴶", "沈滥": "沈㴶",   # 万历末入阁沈㴶，同格三变体
    "閔汝霖": "閔如霖",   # 嘉靖礼尚
    "袁宗皋": "袁宗臯",   # 正德嘉靖大学士
    "向有年": "向永年",   # 崇祯南祭酒
    "蘭從善": "蘭從政",
    "鄧以瓚": "鄧以讚",
    "朱統鈔": "朱統鉓",
    "全天叙": "全天敘",
    "孔貞运": "孔貞運", "萧雲舉": "蕭雲舉", "方从哲": "方從哲",
    # 「以字行」型：金幼孜名善，字幼孜（CBDB 别名表有「幼孜」）——必须查别名表
    "金幼孜": "金善",
}

REAL_OFFICE_FILTER = """
    c_office_chn LIKE '%大學士%' OR c_office_chn LIKE '%內閣%'
    OR c_office_chn LIKE '%翰林%' OR c_office_chn LIKE '%殿%'
"""

FAKE = __import__("re").compile(
    r"^(明代職官年表|年官代職|官\\?代職|官職\\年代|學士承旨|東閣|中極殿|建極殿|"
    r"文華殿|武英殿|文淵閣|華蓋殿|謹身殿|"
    r"[洪武建文永樂洪熙宣德正統景泰天順成化弘治正德嘉靖隆慶萬曆泰昌天啟崇禎]"
    r"[元一二三四五六七八九十廿卅零]{0,6}年?|"
    r"[甲乙丙丁戊己庚辛壬癸]?[子丑寅卯辰巳午未申酉戌亥])$"
)

# 分词器用的人名别名（含未入库的 OCR 变体，确保多人同行能切开）
SPLIT_ALIAS = {
    "龔敎": "龔教", "劉羽吉": "劉宇亮", "陳於陛": "陳于陛", "全天叙": "全天敘",
    "費閭": "費誾", "費間": "費宏", "胡季安": "胡季安", "沈潑": "沈㶆",
}

S2T = str.maketrans("吴张温黄吕万刘乔韦宋陈杨赵郑冯蒋钱韩马高谢龚与费间",
                    "吳張溫黃呂萬劉喬韋宋陳楊趙鄭馮蔣錢韓馬高謝龔與費間")


def connect():
    c = sqlite3.connect(f"file:{CBDB}?mode=ro", uri=True)
    c.execute(f"CREATE TEMP TABLE rel_office AS SELECT c_office_id AS oid FROM OFFICE_CODES "
              f"WHERE {REAL_OFFICE_FILTER}")
    return c


def by_name(c, name):
    return c.execute("SELECT c_personid,c_birthyear,c_deathyear,c_index_year FROM BIOG_MAIN "
                     "WHERE c_name_chn=?", (name,)).fetchall()


def by_altname(c, name):
    """别名表查（覆盖『以字行』型，如 金幼孜→金善）。"""
    return c.execute("""SELECT b.c_personid,b.c_birthyear,b.c_deathyear,b.c_index_year
                        FROM ALTNAME_DATA a JOIN BIOG_MAIN b ON b.c_personid=a.c_personid
                        WHERE a.c_alt_name_chn=?""", (name,)).fetchall()


def rel_count(c, pid):
    return c.execute("SELECT COUNT(*) FROM POSTED_TO_OFFICE_DATA WHERE c_personid=? "
                     "AND c_office_id IN (SELECT oid FROM rel_office)", (pid,)).fetchone()[0]


def score_row(c, row, lo, hi):
    pid, b, d, idx = row
    s = 0
    if idx and lo - 20 <= idx <= hi + 20:
        s += 3
    elif idx:
        s -= 3
    if b and b <= hi + 5:
        s += 2
    elif b:
        s -= 4
    if d and d + 5 >= lo:
        s += 2
    elif d:
        s -= 4
    if not b and not d and not idx:
        s -= 2
    return s


def ed1(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for i in range(len(a)) if a[i] != b[i]) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))


def main():
    c = connect()
    # 性能：rel_count 会被 L5/L6/L8 反复调用，预计算「有内阁/翰林履历的人」集合。
    # 不预计算的话 L8 对「朱」姓要扫 1.1 万行逐一查履历（实测跑 10 分钟未完成）。
    rel_persons = {pid for (pid,) in c.execute(
        "SELECT DISTINCT c_personid FROM POSTED_TO_OFFICE_DATA "
        "WHERE c_office_id IN (SELECT oid FROM rel_office)")}
    print(f"有内阁/殿阁/翰林履历者 {len(rel_persons)} 人")
    # 全库人名词典加速 L8：按 (姓氏) 分桶
    name_by_surname: dict[str, list] = defaultdict(list)
    for (pid, nm, b, d, idx) in c.execute(
            "SELECT c_personid,c_name_chn,c_birthyear,c_deathyear,c_index_year FROM BIOG_MAIN "
            "WHERE c_name_chn IS NOT NULL AND length(c_name_chn) BETWEEN 2 AND 4"):
        name_by_surname[nm[0]].append((pid, nm, b, d, idx))

    def rel_of(pid):
        return 1 if pid in rel_persons else 0

    entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    span = {}
    for e in entries:
        p = e["person"]
        lo, hi = span.get(p, (e["year"], e["year"]))
        span[p] = (min(lo, e["year"]), max(hi, e["year"]))

    result, unresolved = {}, {}
    for p, (lo, hi) in sorted(span.items()):
        # 伪人名：不参与对齐，也不进 unresolved（直接标记）
        if FAKE.match(p) or len(p) < 2:
            result[p] = {"cbdb_id": None, "method": "fake-name",
                         "span": [lo, hi], "note": "非人名（页眉/表头/干支/年号）"}
            continue

        # L1/L2/L3：原名 → 人工别名 → 简繁
        rows, method = None, None
        for cand, m in ((p, "name"), (MANUAL_ALIAS.get(p), "manual-alias"),
                        (p.translate(S2T), "simp-trad"),
                        (MANUAL_ALIAS.get(p.translate(S2T)), "manual-alias")):
            if not cand:
                continue
            r = by_name(c, cand)
            if r:
                rows, method = r, m
                break
        # L2b：别名表（以字行）
        if not rows:
            r = by_altname(c, p)
            if r:
                rows, method = r, "altname"
        if not rows:
            r = by_altname(c, MANUAL_ALIAS.get(p, ""))
            if r:
                rows, method = r, "altname"

        if not rows:
            unresolved[p] = {"span": [lo, hi], "reason": "CBDB 无此名（含别名表）"}
            result[p] = {"cbdb_id": None, "method": "unmatched", "span": [lo, hi]}
            continue
        if len(rows) == 1:
            result[p] = {"cbdb_id": rows[0][0], "method": method, "span": [lo, hi]}
            continue

        # L4：时间消歧
        scored = sorted(((score_row(c, r, lo, hi), r[0]) for r in rows), reverse=True)
        top = scored[0][0]
        winners = [pid for s, pid in scored if s == top]
        if len(winners) == 1 and top > 0:
            result[p] = {"cbdb_id": winners[0], "method": "time-disambig", "span": [lo, hi]}
            continue

        # L5：官职履历
        cands = [pid for s, pid in scored if s >= top - 1][:6]
        rels = sorted(((rel_of(pid), pid) for pid in cands), reverse=True)
        if rels and rels[0][0] > 0 and (len(rels) == 1 or rels[1][0] < rels[0][0]):
            result[p] = {"cbdb_id": rels[0][1], "method": "office-history", "span": [lo, hi]}
            continue

        # L6：内部重复归一 / 唯一非空壳
        infos = {}
        for pid in cands:
            r = c.execute("SELECT c_birthyear,c_deathyear,c_index_year FROM BIOG_MAIN "
                          "WHERE c_personid=?", (pid,)).fetchone()
            n_off = c.execute("SELECT COUNT(*) FROM POSTED_TO_OFFICE_DATA WHERE c_personid=?",
                              (pid,)).fetchone()[0]
            infos[pid] = {"b": r[0], "d": r[1], "idx": r[2], "off": n_off,
                          "rel": rel_of(pid)}
        groups = defaultdict(list)
        for pid, i in infos.items():
            if i["b"] or i["d"]:
                groups[(i["b"], i["d"])].append(pid)
        if len(groups) == 1:
            pids = next(iter(groups.values()))
            best = max(pids, key=lambda x: (infos[x]["rel"], infos[x]["off"]))
            result[p] = {"cbdb_id": best, "method": "cbdb-dup-merge", "span": [lo, hi]}
            continue
        full = [pid for pid, i in infos.items()
                if i["b"] or i["d"] or i["idx"] or i["off"]]
        if len(full) == 1:
            result[p] = {"cbdb_id": full[0], "method": "unique-nonempty", "span": [lo, hi]}
            continue

        # L7：明代限定
        surv = []
        for pid in cands:
            i = infos[pid]
            if i["idx"] and not (1338 <= i["idx"] <= 1665):
                continue
            if i["b"] and i["b"] > hi + 15:
                continue
            if i["d"] and i["d"] < lo - 15:
                continue
            surv.append(pid)
        if len(surv) == 1:
            result[p] = {"cbdb_id": surv[0], "method": "ming-filter", "span": [lo, hi]}
            continue

        # L8：形近模糊（同姓 + 等长 + 编辑距离 1 + 履历 + 时间）
        fuzzy = []
        for (pid, nm, b, d, idx) in name_by_surname.get(p[0], ()):
            if len(nm) != len(p) or not ed1(nm, p):
                continue
            if not rel_of(pid):
                continue
            ok_time = (not idx or lo - 40 <= idx <= hi + 40) and \
                      (not b or b <= hi + 20) and (not d or d >= lo - 20)
            if ok_time:
                fuzzy.append((rel_of(pid), pid, nm))
        fuzzy.sort(reverse=True)
        if len(fuzzy) == 1:
            result[p] = {"cbdb_id": fuzzy[0][1], "method": "fuzzy-name", "span": [lo, hi]}
            continue

        unresolved[p] = {"span": [lo, hi], "reason": "多解未决（CBDB 内同名空壳/重录）",
                         "cands": [pid for _, pid in scored[:5]],
                         "cand_detail": [
                             {"id": pid,
                              "birth": c.execute("SELECT c_birthyear FROM BIOG_MAIN WHERE c_personid=?", (pid,)).fetchone()[0],
                              "death": c.execute("SELECT c_deathyear FROM BIOG_MAIN WHERE c_personid=?", (pid,)).fetchone()[0],
                              "index_year": c.execute("SELECT c_index_year FROM BIOG_MAIN WHERE c_personid=?", (pid,)).fetchone()[0],
                              "rel_offices": rel_of(pid)}
                             for pid in [x for _, x in scored[:5]]]}
        result[p] = {"cbdb_id": None, "method": "ambiguous", "span": [lo, hi],
                     "cands": [pid for _, pid in scored[:5]]}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps(unresolved, ensure_ascii=False, indent=1), encoding="utf-8")

    st = Counter(v["method"] for v in result.values())
    ok = sum(1 for v in result.values() if v["cbdb_id"])
    real = [p for p, v in result.items() if v["method"] != "fake-name"]
    ok_real = sum(1 for p in real if result[p]["cbdb_id"])
    print("方法分布:", dict(st.most_common()))
    print(f"\n全部人名 {len(result)}（含伪人名 {len(result)-len(real)}）")
    print(f"真实人名 {len(real)}：已对齐 {ok_real}（{100*ok_real/len(real):.1f}%）")
    print(f"未决 {len(unresolved)} → {REVIEW}")
    for p, v in list(unresolved.items())[:20]:
        print(f"  {p} {v['reason']} {v.get('span')}")
    c.close()


if __name__ == "__main__":
    main()
