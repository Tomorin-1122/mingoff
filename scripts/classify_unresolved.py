# -*- coding: utf-8 -*-
"""未决实体分类器：CBDB 真没有 vs Paddle 识别错误 vs 非人名垃圾。

输入：vol3_zongbing / vol4_buzhengshi 的 cbdb_unresolved + official 段（span/office）
判据：
  ambiguous 类（本名有候选但分差不足）→ **辖区-年代任职反查**：候选人在 CBDB 有
    本表辖区（office 关键词）任职记录且年份与段相交 → 命中唯一候选人 = 可裁决；
  no-candidate 类 → ①垃圾词（官职碎片/角标）= 非人名；②edit1 形讹 = 识别错误；
    ③同姓+年代相容反查 = 识别错误（弱）；④全无 = CBDB 真没有。
输出：_scratch/unresolved_classified.json + 控制台分档统计。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from match_official_cbdb import S2T  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
OUT = ROOT / "_scratch" / "unresolved_classified.json"
CBDB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")

RE_NOTE_POS = None  # 复用 ocr_zongdu 的职名词表
sys.path.insert(0, str(ROOT / "src"))
import re as _re
RE_JUNK = _re.compile(
    r"御史|侍郎|總兵|總督|巡撫|都御|經理|經略|布使|按察|參政|參議|副使|僉事|郎中|"
    r"员外|主事|督師|將軍|都督|指揮|轉運|糧儲|邊備|操江|守備|備禦|把總|遊擊|參將|"
    r"守禦|兵備|^兵|^副都|^右都|^左都|^年代|^官|^職|^都任|^官舍|^舍人|^指挥|"
    r"^署都|^都指揮|^同知|^知州|^知府|^推官|^經歷|^都事|^断事")

TABLES = {
    "总兵": {
        "unres": "vol3_zongbing_cbdb_unresolved.json",
        "official": "official_zongbing.json",
        # office → CBDB 任职记录关键词（辖区反查）
        "region_kw": {
            "薊州": ["蓟州", "蓟辽"], "宣府": ["宣府", "宣大"], "大同": ["大同"],
            "遼東": ["辽东"], "寧夏": ["宁夏"], "甘肅": ["甘肃"], "延綏": ["延绥"],
            "陕西": ["陝西"], "湖廣": ["湖廣"], "昌平": ["昌平"],
            "保定": ["保定"], "通州": ["通州"], "山東": ["山东"], "河南": ["河南"],
            "密雲": ["密云"], "雲南": ["云南"], "貴州": ["贵州"], "四川": ["四川"],
            "廣西": ["广西"], "浙江": ["浙江"], "福建": ["福建"], "凉州": ["凉州"],
            "兩廣": ["两广"], "廣東": ["广东"], "臨洮": ["临洮"], "松潘": ["松潘"],
            "京師": ["京营", "京师"], "漕運": ["漕运"],
            # 拼接带取首辖区
            "寧夏甘肅": ["宁夏", "甘肃"], "大同遼東": ["大同", "辽东"],
            "薊州山海": ["山海关", "蓟州"], "昌平易州": ["昌平"],
        },
        "default_kw": ["總兵", "副總兵", "參將", "遊擊", "協守", "分守"],
    },
    "布政使": {
        "unres": "vol4_buzhengshi_cbdb_unresolved.json",
        "official": "official_buzhengshi.json",
        "region_kw": {
            pr: [pr] for pr in ("北平", "山東", "山西", "河南", "四川",
                                "江西", "浙江", "福建", "廣東", "廣西", "湖廣",
                                "雲南", "貴州", "應天", "鳳陽", "南直隸蘇松")
        },
        "region_kw": {
            **{pr: [pr] for pr in ("北平", "山東", "山西", "河南", "四川",
                                   "江西", "浙江", "福建", "廣東", "廣西", "湖廣",
                                   "雲南", "貴州", "應天", "鳳陽", "南直隸蘇松")},
            "陕西": ["陝西"],
        },
        "default_kw": ["布政司", "承宣布政使司"],
    },
}


COMMON_CHARS = ('王李張劉陳楊黃趙吳周徐孫馬朱胡郭何高林鄭謝羅宋唐韓馮于董蕭程曹袁'
                '鄧許傅沈曾彭呂蘇盧蔣蔡賈丁魏薛葉閻余潘杜戴夏鍾汪田任姜范方石姚譚廖'
                '鄒熊金陸郝孔白崔康毛邱秦江史顧侯邵孟龍萬段雷錢湯尹黎易常武喬賀賴龔文')


def t2s(name: str) -> str:
    return "".join(S2T.get(ch, ch) for ch in name)


def edit1(a: str, b: str) -> bool:
    if a == b or len(a) != len(b):
        return False
    return sum(x != y for x, y in zip(a, b)) == 1


def main():
    con = sqlite3.connect(str(CBDB))
    # CBDB 索引：人名 → bio；任职 postings（带官名）；名字长度分桶（形讹查）
    postings = defaultdict(list)   # cpid → [(官名, 地址名, fy, ly)]
    for cpid, chn, fy, ly, aname in con.execute(
            "select p.c_personid,o.c_office_chn,p.c_firstyear,p.c_lastyear,a.c_name_chn "
            "from POSTED_TO_OFFICE_DATA p "
            "join OFFICE_CODES o on o.c_office_id=p.c_office_id "
            "left join POSTED_TO_ADDR_DATA pa on pa.c_personid=p.c_personid "
            "  and pa.c_posting_id=p.c_posting_id "
            "left join ADDR_CODES a on a.c_addr_id=pa.c_addr_id"):
        fy2 = fy or 0
        ly2 = ly if ly else (fy2 + 30 if fy2 else 9999)
        postings[cpid].append((chn or "", aname or "", fy2, min(ly2, 9999)))
    biog_by_name = defaultdict(list)
    for cpid, cn, b, d, iy in con.execute(
            "select c_personid,c_name_chn,c_birthyear,c_deathyear,c_index_year from BIOG_MAIN"):
        biog_by_name[cn].append((cpid, cn, b, d, iy))

    result = {}
    for tbl, cfg in TABLES.items():
        u = json.loads((DATA / cfg["unres"]).read_text(encoding="utf-8"))["unresolved"]
        ents = json.loads((DATA / cfg["official"]).read_text(encoding="utf-8"))["tenures"]
        span_of, office_of = {}, {}
        for t in ents:
            lo, hi = span_of.get(t["person"], (9999, 0))
            span_of[t["person"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
            office_of.setdefault(t["person"], t["office"])
        classes = defaultdict(list)
        for it in u:
            name = it["person_id"]
            reason = it["reason"]
            span = span_of.get(name)
            office = office_of.get(name, "")
            kws = cfg["region_kw"].get(office, cfg["default_kw"])
            lo, hi = span if span else (0, 9999)

            # —— no-candidate 类 ——
            if reason == "no-candidate":
                if RE_JUNK.search(name) or len(name) < 2:
                    classes["junk_非人名"].append({"name": name, "office": office,
                                                   "span": [lo, hi]})
                    continue
                # edit1 形讹：变体生成 → 名字典直查（快）
                hits = []
                seen = set()
                for target in (name, t2s(name)):
                    variants = {target}
                    for i in range(len(target)):
                        for ch in COMMON_CHARS:
                            variants.add(target[:i] + ch + target[i + 1:])
                    for v in variants:
                        for cpid, cn2, b, d, iy in biog_by_name.get(v, []):
                            if edit1(target, cn2) and (cpid, cn2) not in seen:
                                seen.add((cpid, cn2))
                                posts = postings.get(cpid, [])
                                region_hit = any(
                                    any(kw in ch or kw in ad for kw in kws)
                                    for ch, ad, _f, _l in posts)
                                era_hit = any(not (l2 < lo - 6 or f2 > hi + 6)
                                              for ch, ad, f2, l2 in posts)
                                if era_hit:
                                    hits.append((cpid, cn2, b, d, iy, region_hit))
                region_uniq = {(h[0], h[1]) for h in hits if h[5]}
                if len(region_uniq) == 1:
                    h0 = next(h for h in hits if h[5])
                    classes["misread_识别错误"].append(
                        {"name": name, "fix": h0[1], "id": h0[0],
                         "bio": f"{h0[2]}-{h0[3]},idx{h0[4]}", "office": office,
                         "span": [lo, hi], "evidence": "edit1+辖区任职"})
                elif not hits:
                    classes["cbdb_真没有"].append({"name": name, "office": office,
                                                   "span": [lo, hi]})
                else:
                    classes["misread_多候选待核"].append(
                        {"name": name, "cands": sorted({h[1] for h in hits})[:4],
                         "office": office, "span": [lo, hi]})
            # —— ambiguous 类：辖区-年代任职反查 ——
            else:
                scored = []
                for c in it.get("cands", []):
                    cpid = int(c["id"])
                    posts = postings.get(cpid, [])
                    hit = any(any(kw in ch or kw in ad for kw in kws) and
                              not (l2 < lo - 2 or f2 > hi + 2)
                              for ch, ad, f2, l2 in posts)
                    if hit:
                        scored.append((cpid, c.get("name")))
                if len(scored) == 1:
                    classes["ambiguous_辖区反查可决"].append(
                        {"name": name, "id": scored[0][0],
                         "cbdb_name": scored[0][1], "office": office,
                         "span": [lo, hi], "evidence": "辖区+年代任职唯一命中"})
                else:
                    classes["ambiguous_仍难决"].append(
                        {"name": name, "hits": len(scored), "office": office,
                         "span": [lo, hi]})
        result[tbl] = {k: v for k, v in classes.items()}
        print(f"=== {tbl} ===")
        for k, v in sorted(classes.items(), key=lambda kv: -len(kv[1])):
            print(f"  {k}: {len(v)}")
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
