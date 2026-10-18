# -*- coding: utf-8 -*-
"""部院数据修复 v2：人名归一、伪名清理、注文隔离、衙署分期、CBDB 重挂。

输入：`vol1_buyuan_entries.json`（v1，3353 条）+ `vol1_buyuan_person_cbdb.json`（v1）
输出：
  `vol1_buyuan_entries_v2.json`     规范化条目（保留 raw_person/raw_office/raw_note）
  `vol1_buyuan_person_cbdb_v2.json` 修复后的 CBDB 映射
  `vol1_buyuan_repair.json`         修复清单（计数 + 抽样 + 理由）

原则（见《数据接入规范》3.6 / 3.7，部院 v1 复盘）：
  * 多格注文不猜配：无法确定归属的注文→ `note=""` + `note_status="quarantined"`，原文留 raw_note；
  * 伪人名/碎片不入库；简繁/异体统一正字；
  * 衙署分期归并（御史臺/御史府→都察院；總督京儲/總倉場→總督倉場）；
  * 同 CBDB id 多正名→只保留 CBDB 正名相符者，其余 NULL；生卒/任期冲突→NULL；
  * 已知原书可定的错配（1431/1432/1433/1449/1399/1400）按原书页补注。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------- 人名归一
# 语料/报告已实证的讹写：正名 ← 变体（见 docs/部院人名讹误订正报告.md）
NAME_ALIAS = {
    "胡渙": "胡濙", "胡潑": "胡濙", "胡淺": "胡濙", "胡澆": "胡濙",
    "胡澐": "胡濙", "胡澱": "胡濙", "胡濛": "胡濙", "胡濼": "胡濙",
    "宋縉": "宋纁", "宋繙": "宋纁", "宋繡": "宋纁", "宋繻": "宋纁",
    "孫籬": "孫鑨", "孫鑼": "孫鑨",
    "汪銉": "汪俊", "汪銘": "汪俊", "汪銥": "汪俊",
    "李鏟": "李鐩", "李鏉": "李鐩",
    "費宗": "費寀", "費衆": "費寀",
    "郭璉": "郭琎", "郭璀": "郭琎",
    "茹瑞": "茹瑺", "茹瑋": "茹瑺",
    "洪鐘": "洪鍾", "温純": "溫純",
    "屠湧": "屠滽", "屠漑": "屠滽", "屠瀟": "屠滽",
    "董分": "董份",
    "呂本": "李本",
    "趙羥": "趙羾",
    "何鱉": "何鰲", "劉訡": "劉訒", "張聰": "張璁", "白鈦": "白鉞",
    "王岩": "王鈍", "王峯": "王鈍", "周潯": "周肅", "麥至德": "麥志德",
    "李遷桂": "李廷桂", "傣斯": "偰斯", "黃克瓚": "黃克纘",
    "夏原吉閤": "夏原吉", "蹇義閤": "蹇義", "耿裕閻": "耿裕",
    "翔南居益": "南居益", "吴山袁煒": "袁煒", "周時中朱斌": "周時中",
    "寇深羅通": "寇深", "張瓊翟鑾": "張瓊",
    "于谦": "于謙", "杨巍": "楊巍", "杨兆": "楊兆",
    "溫仁和": "温仁和", "黃珂": "黄珂",
}
# 简→繁（只收名字里常见字；改完再与索引表合并）
S2T = str.maketrans({
    "吴": "吳", "吕": "呂", "赵": "趙", "刘": "劉", "张": "張", "陈": "陳",
    "杨": "楊", "黄": "黃", "郑": "鄭", "冯": "馮", "蒋": "蔣", "钱": "錢",
    "韩": "韓", "孙": "孫", "马": "馬", "谢": "謝", "龚": "龔", "费": "費",
    "万": "萬", "时": "時", "陆": "陸", "顾": "顧", "苏": "蘇", "罗": "羅",
    "谭": "譚", "钟": "鐘", "邓": "鄧", "邹": "鄒", "龙": "龍", "卢": "盧",
    "严": "嚴", "华": "華", "叶": "葉", "汤": "湯", "许": "許", "欧": "歐",
    "阳": "陽", "诸": "諸", "温": "溫", "习": "習", "国": "國", "宁": "寧",
    "宝": "寶", "献": "獻", "举": "舉", "义": "義", "礼": "禮", "乐": "樂",
    "长": "長", "门": "門", "书": "書", "实": "實", "应": "應", "传": "傳",
    "杰": "傑", "卿": "卿", "晋": "晉", "资": "資", "赞": "贊", "渊": "淵",
    "问": "問", "让": "讓", "贞": "貞", "运": "運", "远": "遠", "达": "達",
    "进": "進", "连": "連", "选": "選", "逊": "遜", "适": "適", "钟": "鍾",
})
GARBAGE = {"井九年", "井八年閏", "井八年", "欠陽", "屈駕", "扈駕", "右侍", "左侍",
           "尚書", "侍郎", "都御史", "御史", "禦史"}
SUFFIXES = ("扈駕", "閤", "閏")
# 名字第 2 字起出现这些「官署/任免」字，几乎都是 OCR 名注错切（如 南兵/都遷戶/參軍/屯戍）；
# 首字可能是真实姓氏（郎/都/任…），不查；白名单（CBDB 映射名 + 内阁人物名）不受影响。
PSEUDO_CHARS = set("遷改罷卒致仕吏戶兵刑工都察御史侍郎參布按總督巡撫軍屯戍餉糧鹽漕"
                   "閣殿陞降謫")
AMBIG_NAMES = {"張鳳", "李敏", "王佐", "顧佐", "吳山", "胡松", "李本"}
PROTECT: set[str] = set()


def normalize_name(raw: str) -> str:
    s = re.sub(r"\s", "", raw or "")
    for suf in SUFFIXES:
        if len(s) > 2 and s.endswith(suf):
            s = s[: -len(suf)]
    if s in GARBAGE:
        return ""
    if s in NAME_ALIAS:
        s = NAME_ALIAS[s]
    s = s.translate(S2T)
    if s in NAME_ALIAS:
        s = NAME_ALIAS[s]
    return s


def canon_person(raw: str) -> str:
    s = normalize_name(raw)
    if not s:
        return ""
    if s not in PROTECT and any(ch in PSEUDO_CHARS for ch in s[1:]):
        return ""
    return s

# ---------------------------------------------------------------- 衙署分期
# raw label -> (office_id, period label)
OFFICE_MAP = {
    "吏部": ("吏部", "吏部"), "戶部": ("戶部", "戶部"), "户部": ("戶部", "戶部"),
    "禮部": ("禮部", "禮部"), "礼部": ("禮部", "禮部"),
    "兵部": ("兵部", "兵部"), "刑部": ("刑部", "刑部"), "工部": ("工部", "工部"),
    "都察院": ("都察院", "都察院"), "御史臺": ("都察院", "御史臺"),
    "御史台": ("都察院", "御史臺"), "御史府": ("都察院", "御史府"),
    "總督京儲": ("總督倉場", "總督京儲"), "总督京储": ("總督倉場", "總督京儲"),
    "總倉場": ("總督倉場", "總倉場"), "总仓场": ("總督倉場", "總倉場"),
    "總督倉場": ("總督倉場", "總督倉場"), "督倉場": ("總督倉場", "總倉場"),
}

# ---------------------------------------------------------------- 原书页可定错配
# (year, canonical person, office_id) -> corrected note（原书页核对：p466/467/468/484/建文页）
BOOK_PATCH = {
    (1431, "郭敦", "戶部"): ("四、乙巳、十一,卒。", "book-p466"),
    (1431, "胡濙", "戶部"): ("正、己卯、十四,禮尚兼掌。", "book-p466"),
    (1431, "胡濙", "禮部"): ("正、己卯、十四,兼掌戶部。", "book-p466"),
    (1432, "黃福", "戶部"): ("八、己亥、十三,改南京戶部。", "book-p467"),
    (1432, "胡濙", "戶部"): ("", "book-p467"),
    (1433, "郭資", "戶部"): ("十二、甲寅、五,卒,追封湯陰伯,謚忠襄。", "book-p468"),
    (1433, "胡濙", "戶部"): ("", "book-p468"),
    (1434, "胡濙", "禮部"): ("", "book-p468"),
    (1449, "于謙", "兵部"): (
        "七、癸巳、十五,扈從;八、戊辰、廿,兵右侍遷;十、壬戌、十五,遷少保,兼兵尚。", "book-p484"),
    (1449, "鄺埜", "兵部"): ("七、癸巳、十五,扈從;八、壬戌、十五,死難。", "book-p484"),
    (1399, "景清", "都察院"): ("二月,左僉都遷,尋改北平參議。", "book-jiwen1"),
    (1399, "練子寧", "都察院"): ("二月,任。", "book-jiwen1"),
    (1400, "景清", "都察院"): ("三、辛巳、十六,北平參議遷御史大夫。", "book-jiwen2"),
    (1400, "練子寧", "都察院"): ("三、辛巳,十六,改御史中丞。", "book-jiwen2"),
}

# ---------------------------------------------------------------- CBDB 修复
SHARED_ID_OWNER = {  # 同一 id 只允许这些正名保留；其余置 NULL
    30847: {"高拱"}, 34421: {"劉崧"}, 34637: {"劉麟"}, 34732: {"溫純"},
    66341: set(), 66439: set(), 66544: {"侯泰"}, 66668: {"趙羾"},
    66720: {"茹瑺"}, 66873: {"陳鎰"}, 67072: {"李裕"}, 67450: {"張瓚"},
    67477: set(), 67650: {"李秉"}, 67968: set(), 67998: {"何鑑"},
    68016: {"洪鍾"}, 131299: {"屠滽"}, 131989: {"董份"}, 201490: set(),
    223131: {"李本"},
}
CBDB_ID_OVERRIDE = {"李鐩": 128075, "趙羾": 66668}
CBDB_NULL = {"宋冕", "張鳳", "李敏", "顧佐", "李信", "胡濙", "陳珮", "陳璟",
             "趙仁", "趙勉", "趙本", "趙犏", "趙犭", "趙粑", "趙紅", "趙肛",
             "陳智", "李暹", "張遇", "王儁", "王壱", "王晉", "李昶", "何鈞",
             "李瓊", "李瓚", "高燿", "劉仁", "劉訥", "侯庸", "茹瑞"}
# 需要改名的个体（同人不同人共用正名时拆分）
PERSON_RENAME = {("張鳳", 1629, "工部"): "張鳳翔"}


def canon_person_old(raw: str) -> str:
    s = re.sub(r"\s", "", raw or "")
    for suf in SUFFIXES:
        if len(s) > 2 and s.endswith(suf):
            s = s[: -len(suf)]
    if s in GARBAGE:
        return ""
    if s in NAME_ALIAS:
        s = NAME_ALIAS[s]
    s = s.translate(S2T)
    if s in NAME_ALIAS:
        s = NAME_ALIAS[s]
    return s


def repair_entries(entries: list[dict]) -> tuple[list[dict], dict]:
    out, dropped = [], []
    changed = Counter()
    for e in entries:
        raw = e.get("person", "")
        person = canon_person(raw)
        if not person:
            dropped.append({"year": e.get("year"), "office": e.get("office"), "raw": raw})
            continue
        if person != raw:
            changed[(raw, person)] += 1
        office_raw = e.get("office") or ""
        office, period = OFFICE_MAP.get(office_raw, (None, None))
        if not office:
            dropped.append({"year": e.get("year"), "office": office_raw, "raw": raw,
                            "reason": "office-unmapped"})
            continue
        note = e.get("note", "") or ""
        out.append({
            "year": e["year"], "office": office, "office_period": period,
            "person": person, "note": note, "raw_person": raw,
            "raw_office": office_raw, "src": e.get("src", "table"),
            "flag": e.get("flag"),
        })
    return out, {"dropped": dropped, "renamed": [
        {"raw": a, "person": b, "count": n} for (a, b), n in changed.most_common()]}


def apply_book_patch(entries: list[dict], report: dict) -> None:
    by_key = defaultdict(list)
    for e in entries:
        by_key[(e["year"], e["person"], e["office"])].append(e)
    applied = []
    for (year, person, office), (note, source) in BOOK_PATCH.items():
        rows = by_key.get((year, person, office), [])
        if rows:
            rows[0]["note"] = note
            rows[0]["note_status"] = "book-patched"
            rows[0]["note_source"] = source
            for extra in rows[1:]:
                extra["note"] = ""
                extra["note_status"] = "dup"
            applied.append({"year": year, "person": person, "office": office,
                            "source": source})
        elif note:
            entries.append({"year": year, "office": office, "office_period": "",
                            "person": person, "note": note, "note_status": "book-patched",
                            "note_source": source, "raw_person": person,
                            "raw_office": office, "src": "book-patch"})
            applied.append({"year": year, "person": person, "office": office,
                            "source": source, "added": True})
    report["book_patch"] = applied


def quarantine_notes(entries: list[dict], report: dict) -> None:
    names = {e["person"] for e in entries if len(e["person"]) >= 2}
    leave_hard = ("卒", "死於難", "死難", "棄市", "伏誅", "自盡", "殉難", "正法")
    # 死/伏诛后仍有同年更晚或后世条目的，注文必为错挂（或同人起复不可能）
    by_person = defaultdict(list)
    for e in entries:
        by_person[e["person"]].append(e["year"])
    flagged = []
    for e in entries:
        note = e["note"]
        if not note:
            continue
        other = next((n for n in names if n != e["person"] and n in note), None)
        if other:
            e["raw_note"] = note
            e["note"] = ""
            e["note_status"] = "quarantined"
            e["note_quarantine_reason"] = f"contains-other-name:{other}"
            flagged.append({"year": e["year"], "person": e["person"], "office": e["office"],
                            "reason": f"contains-other-name:{other}", "note": note[:60]})
            continue
        if any(v in note for v in leave_hard) and max(by_person[e["person"]]) > e["year"] \
                and e["person"] not in AMBIG_NAMES:
            e["raw_note"] = note
            e["note"] = ""
            e["note_status"] = "quarantined"
            e["note_quarantine_reason"] = "death-note-but-later-entries"
            flagged.append({"year": e["year"], "person": e["person"], "office": e["office"],
                            "reason": "death-note-but-later-entries", "note": note[:60]})
    report["note_quarantine"] = flagged


def dedupe_entries(entries: list[dict], report: dict) -> list[dict]:
    groups = defaultdict(list)
    for e in entries:
        groups[(e["year"], e["person"], e["office"])].append(e)
    out, conflicts = [], []
    for key, rows in groups.items():
        year, person, office = key
        rows.sort(key=lambda r: (r.get("note_status") not in ("book-patched",),))
        notes = [r["note"] for r in rows if r["note"]]
        if not notes:
            base = dict(rows[0]); base["note"] = ""
            out.append(base)
        elif len(set(notes)) == 1:
            base = dict(next(r for r in rows if r["note"]))
            out.append(base)
        else:
            base = dict(rows[0])
            base["raw_note"] = " ｜ ".join(notes)
            base["note"] = ""
            base["note_status"] = "conflict"
            out.append(base)
            conflicts.append({"year": year, "person": person, "office": office,
                              "notes": notes})
    report["dup_conflicts"] = conflicts
    return out


def repair_mapping(mapping: dict, persons: set[str], report: dict) -> dict:
    # 1) 键按同一规则归一；合并同键
    merged: dict[str, dict] = {}
    merges = []
    for raw, val in mapping.items():
        canon = canon_person(raw)
        if not canon:
            continue
        if canon not in persons:
            # 人物已被合并/删除；仍记录供审计
            pass
        if canon in merged:
            merges.append({"from": raw, "to": canon})
            if merged[canon].get("cbdb_id") is None and val.get("cbdb_id"):
                merged[canon] = val
            continue
        merged[canon] = dict(val)
    # 2) 同 id 多正名：只留 owner
    id_names = defaultdict(set)
    for n, v in merged.items():
        if v.get("cbdb_id"):
            id_names[v["cbdb_id"]].add(n)
    nulled = []
    for pid, names in id_names.items():
        owners = SHARED_ID_OWNER.get(pid)
        if owners is None:
            continue
        for n in names - owners:
            merged[n]["cbdb_id"] = None
            merged[n]["cbdb_name"] = None
            merged[n]["repair"] = f"shared-id-{pid}-not-owner"
            nulled.append({"person": n, "id": pid})
    for n in CBDB_NULL:
        if n in merged and merged[n].get("cbdb_id"):
            old = merged[n]["cbdb_id"]
            merged[n]["cbdb_id"] = None
            merged[n]["cbdb_name"] = None
            merged[n]["repair"] = f"date-conflict-or-ambiguous:{old}"
            nulled.append({"person": n, "id": old})
    for n, pid in CBDB_ID_OVERRIDE.items():
        if n in merged:
            merged[n]["cbdb_id"] = pid
            merged[n]["repair"] = f"override:{pid}"
    report["mapping"] = {"merges": merges, "nulled": nulled}
    return merged


def recover_from_pages(entries: list[dict], report: dict) -> list[dict]:
    """从 OCR 原文页补回「同人同衙、中间缺年、姓名仍见于该年页」的条目。

    部院 v1 的早期无标签页丢行严重（如 郭資 户部 1404–1419 整段缺行）。
    年表为逐年名单：若该年原文页仍能检索到该人姓名，且此人当年没有其他衙署条目，
    则补一条空注条目（src=page-recovered）；不做任何跨年插值。
    """
    cands = [DATA.parents[3] / "_scratch" / "mineru_buyuan",
             Path.cwd() / "_scratch" / "mineru_buyuan"]
    md_dir = next((p for p in cands if p.is_dir()), None)
    if not md_dir:
        report["page_recovery"] = {"status": "skipped(no-md)"}
        return entries
    text = ""
    for f in sorted(md_dir.glob("*.md")):
        text += f.read_text(encoding="utf-8")
    # 年段索引：以 (YYYY) 为界；一个年份可能多次出现，取第一次出现后到下一年的文本
    marks = [(int(m.group(1)), m.start()) for m in re.finditer(r"[（(](1[3-6]\d\d)[）)]", text)]
    year_text: dict[int, str] = {}
    for i, (y, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        year_text.setdefault(y, text[pos:end])
    # 人名别名集合（同一个人可能以 raw/别名出现）
    alias_of: dict[str, set[str]] = defaultdict(set)
    for e in entries:
        alias_of[e["person"]].add(e["person"])
        alias_of[e["person"]].add(e["raw_person"])
    have = {(e["year"], e["person"], e["office"]) for e in entries}
    other_office = {(e["year"], e["person"]) for e in entries}
    by_po = defaultdict(list)
    for e in entries:
        by_po[(e["person"], e["office"])].append(e["year"])
    added = []
    for (person, office), years in sorted(by_po.items()):
        ys = sorted(set(years))
        for a, b in zip(ys, ys[1:]):
            if b - a - 1 <= 0 or b - a - 1 > 20:
                continue
            for y in range(a + 1, b):
                if (y, person, office) in have or (y, person) in other_office:
                    continue
                blob = year_text.get(y, "")
                if not blob:
                    continue
                if any(alias and alias in blob for alias in alias_of[person]):
                    entries.append({"year": y, "office": office,
                                    "office_period": next(
                                        (e.get("office_period") for e in entries
                                         if e["person"] == person and e["office"] == office),
                                        office),
                                    "person": person, "note": "",
                                    "note_status": "page-recovered",
                                    "raw_person": person, "raw_office": office,
                                    "src": "page-recovered"})
                    have.add((y, person, office))
                    added.append({"year": y, "person": person, "office": office})
    report["page_recovery"] = {"status": "ok", "added": len(added),
                               "samples": added[:20]}
    return entries


def main() -> None:
    global PROTECT
    entries = json.loads((DATA / "vol1_buyuan_entries.json").read_text(encoding="utf-8"))
    mapping = json.loads((DATA / "vol1_buyuan_person_cbdb.json").read_text(encoding="utf-8"))
    cabinet = json.loads((DATA / "official_cabinet.json").read_text(encoding="utf-8"))
    PROTECT = {normalize_name(k) for k in mapping} | {t["person"] for t in cabinet["tenures"]}
    PROTECT |= {"高尚", "李賢", "王尚", "陳尚"}  # 防误伤（如有真名含伪字）

    report: dict = {}
    entries, info = repair_entries(entries)
    report.update(info)
    persons = {e["person"] for e in entries}
    # 个体改名（同正名不同人）
    renamed = []
    for e in entries:
        new = PERSON_RENAME.get((e["person"], e["year"], e["office"]))
        if new:
            renamed.append({"from": e["person"], "to": new, "year": e["year"],
                            "office": e["office"]})
            e["person"] = new
    report["person_rename"] = renamed
    persons = {e["person"] for e in entries}

    apply_book_patch(entries, report)
    quarantine_notes(entries, report)
    entries = dedupe_entries(entries, report)
    # 页内补行（recover_from_pages）暂不启用：姓名出现在年份页 ≠ 该衙在职，
    # 必须先逐页核对（部院 v1 教训）；长缺口用 gap_after 显式登记，不做插值。
    report["page_recovery"] = {"status": "disabled(需逐页核对，不插值)"}
    entries.sort(key=lambda e: (e["year"], e["office"], e["person"]))
    new_mapping = repair_mapping(mapping, persons, report)

    out_entries = DATA / "vol1_buyuan_entries_v2.json"
    out_mapping = DATA / "vol1_buyuan_person_cbdb_v2.json"
    out_entries.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    out_mapping.write_text(json.dumps(new_mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    report["counts"] = {
        "entries_in": 3353, "entries_out": len(entries),
        "persons": len({e["person"] for e in entries}),
        "dropped": len(report.get("dropped", [])),
        "quarantined": len(report.get("note_quarantine", [])),
        "dup_conflicts": len(report.get("dup_conflicts", [])),
        "book_patch": len(report.get("book_patch", [])),
        "mapping_out": len(new_mapping),
        "mapping_ids": sum(1 for v in new_mapping.values() if v.get("cbdb_id")),
    }
    (DATA / "vol1_buyuan_repair.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=1))
    print("quarantine reasons:", dict(Counter(q["reason"] for q in report["note_quarantine"]).most_common(10)))
    print("dropped:", report.get("dropped", [])[:10])


if __name__ == "__main__":
    main()
