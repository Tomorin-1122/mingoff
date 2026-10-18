# -*- coding: utf-8 -*-
"""正文条目 → 人物结构化字段（试点）。

输入: _scratch/mineru_mrzj/corpus_corrected.json
输出: person_pilot.json（逐人一条）+ 控制台统计

切分：上一条出处以 `)` 或 `卷/页` 收尾，紧跟「人名 + （生卒）/字/號/名/，X人」即新条目。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
CJK = r"\u4e00-\u9fff"

TAIL = re.compile(r"[)）]|/\d+[下上]?|[^\s（）()]{1,10}\d+[/／]\d+[上下]?")
NAME_RE = re.compile(rf"[{CJK}]{{2,4}}")
CITE_TAIL = re.compile(r"(?:[)）]|/\d+[下上]?|\d+[下上]|[。】])$")
DATE_PAREN = re.compile(r"[（(]\d{3,4}\s*[—–\-]*\s*\d{0,4}[）)]$")
TITLE_TAIL = set("碑銘傳序表狀錄志記集稿考略說議疏跋贊頌賦詩文書公君母太父")
NAME_STOP = set("字號初以改別晚又自人氏妻母父弟男")

BORN = re.compile(r"[（(](\d{3,4})\s*[—–\-]+\s*(\d{3,4})?[）)]")
ZI = re.compile(rf"字([{CJK}]{{1,2}})")
HAO = re.compile(rf"號([{CJK}]{{1,4}})")
MING = re.compile(rf"(?:^|[，。])名([{CJK}])(?:[，。]|以字行)")
NATIVE = re.compile(rf"([{CJK}]{{2,7}})人[。，]")
ERA = "洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬[曆歷爵层]|万[曆歷]|泰昌|天啟|崇禎"
EXAM = re.compile(rf"({ERA})(元|[一二三四五六七八九十卅卌]+)年(進士|舉人|貢生)")
ERA_START = {
    "洪武": 1368, "建文": 1399, "永樂": 1403, "洪熙": 1425, "宣德": 1426,
    "正統": 1436, "景泰": 1450, "天順": 1457, "成化": 1465, "弘治": 1488,
    "正德": 1506, "嘉靖": 1522, "隆慶": 1567, "萬曆": 1573, "泰昌": 1620,
    "天啟": 1621, "崇禎": 1628,
}
CN_NUM = {"元": 1}


def cn2int(s: str) -> int:
    """一~卅九 的简单中文数字；无法解析返回 0（由调用方当无效处理）。"""
    if s in CN_NUM:
        return 1
    digits = "〇一二三四五六七八九"
    try:
        if "卌" in s:
            a, _, b = s.partition("卌")
            return 40 + (digits.index(b) if b else 0)
        if "卅" in s:
            a, _, b = s.partition("卅")
            return 30 + (digits.index(b) if b else 0)
        if "十" in s:
            a, _, b = s.partition("十")
            tens = digits.index(a) if a else 1
            ones = digits.index(b) if b else 0
            return tens * 10 + ones
        return digits.index(s) if s in digits else 0
    except ValueError:
        return 0


def norm_era(era: str) -> str:
    return era.replace("万", "萬").replace("歷", "曆").replace("爵", "曆").replace("层", "曆")


def era_gregorian(era: str, year_cn: str) -> int | None:
    key = norm_era(era)
    base = ERA_START.get(key)
    if base is None:
        return None
    n = cn2int(year_cn)
    return base + n - 1 if n else None
SHI = re.compile(rf"諡([{CJK}]{{1,2}})")
CITE = re.compile(r"([^()（）]{2,20})[(（]([^()（）/／]{2,16})[/／](\d+)([上下])?[)）]")


def heads(text: str) -> list[tuple[int, str]]:
    """从引文收尾之后读人名：避免把「19下」的「下」粘进姓名。"""
    out = []
    pos = [0] + [m.end() for m in TAIL.finditer(text)]
    for s in pos:
        for L in (3, 2, 4):
            nm = text[s : s + L]
            if len(nm) != L or not NAME_RE.fullmatch(nm):
                continue
            if nm[0] in NAME_STOP or nm[-1] in TITLE_TAIL:
                continue
            nxt = text[s + L : s + L + 1]
            ok = nxt in "，字號名"
            if nxt in "(（":
                ok = bool(re.match(r"[（(]\d{3}", text[s + L : s + L + 5]))
            if ok:
                out.append((s, nm))
                break
    # 去重、去嵌套
    dedup = []
    for s, n in out:
        if dedup and s < dedup[-1][0] + len(dedup[-1][1]):
            continue
        dedup.append((s, n))
    return dedup


def story_region(body: str) -> str:
    """小传区：从姓名到第一个出处括号之前。避免把下一条人物的科举读进来。"""
    m = CITE.search(body)
    return body[: m.start()] if m else body


def extract_one(name: str, body: str, page: int) -> dict:
    m = BORN.search(body[:24])
    birth = int(m.group(1)) if m else None
    death = int(m.group(2)) if (m and m.group(2)) else None
    story = story_region(body)
    head40 = body[:40]
    zi = ZI.search(head40)
    zi_v = zi.group(1) if zi else None
    if zi_v and zi_v.startswith("行"):
        zi = ZI.search(head40, zi.end())
        zi_v = zi.group(1) if zi else None
    hao = HAO.search(story) or HAO.search(body)
    ming = MING.search(body)
    nat = NATIVE.search(story) or NATIVE.search(body)
    era = EXAM.search(story)
    # 生年一致性：中进士最早也得十几岁；与生卒冲突的一律判为串行
    exam_g = era_gregorian(era.group(1), era.group(2)) if era else None
    if exam_g and birth and (exam_g < birth + 12 or (death and exam_g > death + 2)):
        era, exam_g = None, None
    shi = SHI.search(body)
    cites = []
    for a, b, c, d in CITE.findall(body[:900]):
        m2 = re.match(r"^(.*?)(\d+)$", b)
        book, vol = (m2.group(1), int(m2.group(2))) if m2 else (b, int(c))
        if not book:
            book, vol = b, int(c)
        cites.append({"title": a, "book": book, "vol": vol, "page": d or ""})
    # 「同上」承接上一条书名
    last_book = ""
    for c in cites:
        if c["book"].startswith("同上") and last_book:
            c["book"] = last_book
        else:
            last_book = c["book"]
    return {
        "name": name,
        "page": page,
        "birth": birth,
        "death": death,
        "ming": ming.group(1) if ming else None,
        "zi": zi_v,
        "hao": hao.group(1) if hao else None,
        "native": nat.group(1) if nat else None,
        "exam_era": norm_era(era.group(1)) if era else None,
        "exam_year": era.group(2) if era else None,
        "exam_type": era.group(3) if era else None,
        "exam_gregorian": exam_g,
        "shi": shi.group(1) if shi else None,
        "cites": cites,
        "raw_len": len(body),
    }


def main():
    pages = json.loads((BASE / "corpus_corrected.json").read_text(encoding="utf-8"))
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    picked = pages[::step]
    rows = []
    for p in picked:
        t, pg = p["text"], p["printed_page"]
        hs = heads(t)
        for i, (s, name) in enumerate(hs):
            e = hs[i + 1][0] if i + 1 < len(hs) else len(t)
            rows.append(extract_one(name, t[s:e], pg))
    (BASE / "person_pilot.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    n = len(rows)
    fill = {k: sum(1 for r in rows if r[k]) for k in
            ("birth", "death", "ming", "zi", "hao", "native", "exam_era", "shi")}
    has_cite = sum(1 for r in rows if r["cites"])
    print(f"抽样 {len(picked)} 页（每 {step} 页取 1）→ 条目 {n}，平均 {n/len(picked):.1f}/页")
    for k, v in fill.items():
        print(f"  {k:9} {v:5}  {v/n*100:5.1f}%")
    print(f"  出处(卷页) {has_cite:5}  {has_cite/n*100:5.1f}%  平均 {sum(len(r['cites']) for r in rows)/n:.1f} 条")
    print("\n样例：")
    for r in rows[:6]:
        print(f"  p{r['page']} {r['name']} ({r['birth']}-{r['death']}) 字{r['zi']} 號{r['hao']} "
              f"{r['native']} {r['exam_era'] or ''}{r['exam_year'] or ''}{r['exam_type'] or ''} 出处{len(r['cites'])}")


if __name__ == "__main__":
    main()
