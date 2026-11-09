# -*- coding: utf-8 -*-
"""京卿年表（京師）解析（试点，2026-11-01）。

输入：MinerU OCR 的 md（_scratch/mineru_nianbiao/out/vol1_jingqing_jingshi_{a,b}.md）
输出：src/mingoff/data/vol1_jingqing_entries.json（提取物，vol1_* 不入公开仓）
      src/mingoff/data/vol1_jingqing_review.json（待核清单）

版式事实（实拍 + Paddle 行框裁决，PDF 996–1281 / 正文 981–1266，277 年）：
  1. 一年一页，跨页成对：左页带「官/職 + 年/代」角标与官职标签列，右页无标签；
  2. 两页共用同一 8 行官职框架（通政使/大理卿/太常卿/光祿卿/太僕卿/鴻臚卿/尚寶卿/順天府府尹），
     无标签年的第 i 行 = 最近有标签年的第 i 个官职；空行 = 该官职无人；
  3. 行内可 1–3 格 = 一官职带内多人并排（各格各人），一格也可多人连写（注文不猜配）；
  4. 官职标签可带沿革括注（大理卿(洪武元年革大理寺,十四年復置。)）；
  5. 年份头两种形态：全式「隆慶四年 庚午 (1570)」/ 裸式「(1570)」（纪年文字被 OCR 丢）；
  6. MinerU 跨页并表（28+ 例）：两年压进一个 <table>，按年份头切回；
     另有 52 个无年份头续表，行归入当前年。

纪律（沿中书省试点）：人名可自动取；注文只在单人格且干净切分时采用；
多人同格注文不猜配标 review；无标签年全部标 review（行序可靠度较低）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MD = [ROOT / "_scratch" / "mineru_nianbiao" / "out" / f"vol1_jingqing_jingshi_{p}.md"
      for p in ("a", "b")]
OUT = ROOT / "src" / "mingoff" / "data" / "vol1_jingqing_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol1_jingqing_review.json"

OFFICES = ("通政使", "大理卿", "太常卿", "光祿卿", "太僕卿", "鴻臚卿", "尚寶卿", "順天府府尹")
# 官职别称（变体 OCR 形态），归一到正名
OFFICE_ALIASES = {"順天府尹": "順天府府尹", "尚賓卿": "尚寶卿"}

RE_YEAR_FULL = re.compile(
    r"(洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎|弘光)"
    r"[元一二三四五六七八九十廿卅]{1,3}年\s*[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s*[(（](\d{4})[)）]")
RE_YEAR_BARE = re.compile(r"[(（](\d{4})[)）]")
RE_NAME = re.compile(r"([\u4e00-\u9fff]{2,4})(?=[\s\u3000,，;；(（]|$)")
# 改名人括号形态：高(沈)禄 —— 原名/今名并列，括号保留在 person 里
RE_NAME_PAREN = re.compile(
    r"([\u4e00-\u9fff][（(][\u4e00-\u9fff]{1,2}[)）][\u4e00-\u9fff]{0,2})"
    r"(?=[\s\u3000,，;；]|$)")
RE_PAREN_NAME_LOOSE = re.compile(
    r"[\u4e00-\u9fff][（(][\u4e00-\u9fff]{1,2}[)）][\u4e00-\u9fff]{0,2}")
RE_MONTH_START = re.compile(r"(?:閏[正臘一二三四五六七八九十]{1,2}|正|閏|臘|[一二三四五六七八九十]{1,2})、")
RE_NOTE_START = re.compile(
    r"(?:閏[正臘一二三四五六七八九十]{1,2}|正|閏|臘|[一二三四五六七八九十]{1,2})、"
    r"|(?:閏[正臘一二三四五六七八九十]{1,2}|正|閏|臘|[一二三四五六七八九十]{1,2})月"
    r"|是年|同年|先是|尋|坐|卒|贈|加|兼|改|復|署|降|升|調|還|致仕|起|罷|任")
RE_CJK_HEAD = re.compile(r"^[\u4e00-\u9fff]{2,4}")

# 年号 → (起始年, 元年对应)；bare 年份头反查用，按序匹配（泰昌在萬曆后）
ERA_SPANS = (
    ("洪武", 1368, 1398), ("建文", 1399, 1402), ("永樂", 1403, 1424),
    ("洪熙", 1425, 1425), ("宣德", 1426, 1435), ("正統", 1436, 1449),
    ("景泰", 1450, 1456), ("天順", 1457, 1464), ("成化", 1465, 1487),
    ("弘治", 1488, 1505), ("正德", 1506, 1521), ("嘉靖", 1522, 1566),
    ("隆慶", 1567, 1572), ("萬曆", 1573, 1620), ("泰昌", 1620, 1620),
    ("天啟", 1621, 1627), ("崇禎", 1628, 1644),
)
CN_NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10}


def era_of_year(year: int) -> str | None:
    for era, y0, y1 in ERA_SPANS:
        if y0 <= year <= y1:
            return era
    return None


def text_of(cell: str) -> str:
    t = re.sub(r"<[^>]+>", "", cell)
    t = t.replace("\u3000", " ")
    return re.sub(r"\s+", " ", t).strip()


def label_of(head: str) -> tuple[str | None, str]:
    """行首格 → (正名官职, 沿革括注)。非标签行返回 (None, 原文)。"""
    m = re.match(r"([\u4e00-\u9fff]{2,6}?)[(（](.*)[)）]?\s*$", head)
    core, paren = (m.group(1), m.group(2)) if m else (head, "")
    core = OFFICE_ALIASES.get(core, core)
    if core in OFFICES:
        return core, paren
    return None, head


RE_DATE_HEAD = re.compile(
    r"^(?:洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎"
    r"|是年|同年|先是|尋|坐|卒|贈|加|兼|改|升|降|復|署|代|調|還|卒于)")


RE_NUMERIC = re.compile(r"^[一二三四五六七八九十廿卅正閏]+$")
RE_NUM_YEAR = re.compile(r"[一二三四五六七八九十廿卅]{1,3}年")
RE_DATEISH = re.compile(r"^[一二三四五六七八九十廿卅正閏]{1,2}月")


def _is_person(tok: str) -> bool:
    """过滤日期/虚词开头的假人名（吴元年、是年、洪武廿二、十二月、十五年六…）。

    「年」尾词只在紧邻数字/元时才判为日期（十五年六、吳元年）；
    梁有年、張堯年这类真人不误杀。
    """
    if not tok:
        return False
    if tok.endswith("年") and len(tok) >= 2 and tok[-2] in "一二三四五六七八九十廿卅零元":
        return False
    if tok.endswith("帝"):
        return False
    if RE_DATE_HEAD.match(tok) or RE_NUMERIC.match(tok) or RE_DATEISH.match(tok):
        return False
    if RE_NUM_YEAR.search(tok):
        return False
    return True


def split_persons(text: str, _no_fallback: bool = False) -> tuple[list[str], str]:
    """一格内从头切人名，返回 (names, 余注文)。

    _no_fallback：前瞻递归用——禁用兜底/前瞻，只认干净切分路径，
    防止「蘇應旻張堯年」被兜底切成「蘇應旻張/堯年」。
    """
    names: list[str] = []
    pos = 0
    while pos < len(text):
        m = RE_NAME.match(text, pos) or RE_NAME_PAREN.match(text, pos)
        if m:
            tok = m.group(1)
            # 名+注词直连（OCR 注文错位常态：蔡瑄是年，卒於官。= 蔡瑄 + 是年注文）
            # → 注词切点优先于整体人名
            cut = None
            for k in (2, 3):
                if k < len(tok) and RE_CJK_HEAD.fullmatch(tok[:k]) \
                        and RE_NOTE_START.match(tok, k):
                    cut = k
                    break
            if cut and _is_person(tok[:cut]):
                names.append(tok[:cut])
                pos += cut
                continue
        if m and _is_person(re.sub(r"[（(][\u4e00-\u9fff]{1,2}[)）]", "", m.group(1))):
            names.append(m.group(1))
            pos = m.end()
            while pos < len(text) and text[pos] in " \u3000":
                pos += 1
            continue
        # 粘连形态：名字直接贴注文（月令或任免动词起头：商敬四、… / 商暠是年,…）
        # 人名取 2–3 字（旻張堯年十、这类 4 字头是跨名粘连，不是名）
        glued = None
        for i in (2, 3):
            if pos + i > len(text):
                break
            head = text[pos:pos + i]
            if RE_CJK_HEAD.fullmatch(head) and RE_NOTE_START.match(text, pos + i):
                glued = head
                break
        if not glued:
            for trail in (0, 1, 2):
                mp = re.match(rf"[\u4e00-\u9fff][（(][\u4e00-\u9fff]{{1,2}}[)）][\u4e00-\u9fff]{{{trail}}}",
                              text[pos:])
                if mp and RE_NOTE_START.match(text, pos + mp.end()) and _is_person(
                        re.sub(r"[（(][\u4e00-\u9fff]{1,2}[)）]", "", mp.group())):
                    glued = mp.group()
                    break
        if glued and _is_person(glued) and (names or pos == 0):
            names.append(glued)
            pos += len(glued)
            continue
        break
    if names:
        return names, text[pos:].strip()
    # 名名直连（无空格、无月令界标）：蘇應旻張堯年十、… —— 试 2–4 字头，
    # 其余部须能按干净路径切出名才接受（一阶前瞻，递归合并）
    if pos == 0 and not _no_fallback:
        for hl in (2, 3, 4):
            if hl >= len(text):
                break
            head, rest = text[:hl], text[hl:]
            if not _is_person(head):
                continue
            rnames, rnote = split_persons(rest, _no_fallback=True)
            if rnames:
                return [head] + rnames, rnote
    # 两三字人名内嵌空格（解 繉 / 胡 漢，规范 §4 已知形态）
    m = re.match(r"^([\u4e00-\u9fff])\s+([\u4e00-\u9fff]{1,2})(?=$|[\s,，;；()（）])", text)
    if m and _is_person(m.group(1) + m.group(2)):
        return [m.group(1) + m.group(2)], text[m.end():].strip()
    # 兜底：开头 2–4 字当人名（日期/虚词已过滤，存疑仍由调用方标 review）；
    # 人名后不会直接跟标点，跟了就是注文（十五年六、辛巳…）
    if _no_fallback:
        return [], text
    m = RE_CJK_HEAD.match(text)
    if (m and text[m.end():m.end() + 1] not in ("、", "。", ",", "，", ";", "；")
            and _is_person(m.group(0))):
        return [m.group(0)], text[m.end():].strip()
    return [], text


# ==================== N1/N2：嵌套继任者拆分与多名按序绑定（2026-11-08） ====================
# 背景：年表「迁出/迁入双记」惯例下，继任者人名嵌在前任注文流内、无分隔符直连
# （1625 刑科「…遷太常少。陸文獻九、癸酉、廿八,兵左給遷。」）；此前 split_persons
# 只从格首切人，注文开始后不回看 → 嵌套条目整段丢失、多名格注文错配。

#: 月条目锚：[年前缀]、月数、干支（日数「廿三、」无干支不会误锚；跨年注
#: 「三年九、甲申」的年前缀并入锚，保证跨年 chunk 完整供 _cross_year 识别）
RE_ENTRY_SEG_STR = (r"(?:[一二三四五六七八九十]{1,3}年)?"
                    r"[一二三四五六七八九十]{1,2}、"
                    r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]")
RE_ENTRY_SEG = re.compile(RE_ENTRY_SEG_STR)
#: 候选人名中的动词性注文用字（出现即非人名）
_NESTED_VERB = set("奏遷任卒憂免冠起補管差給假銜候丁滿復改轉陞謫考察拾道署俸"
                   "註注病乞歸省祭終視事攝予告駁")
#: 纪年前缀（候选为年号纪年而非人名）
_NESTED_ERA = ("崇禎", "天啟", "泰昌", "萬曆", "隆慶", "嘉靖", "正德", "弘治",
               "成化", "天順", "景泰", "正統", "宣德", "永樂", "洪熙", "洪武",
               "建文", "順治")


def _nested_name_ok(name: str) -> bool:
    """嵌套候选人名合法性：须纯汉字；排纪年/纯数字/动词字，末字为数字者拒
    （「某某十」实为「某某+十月」的贪心误切）。"""
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
        return False
    if name.startswith(_NESTED_ERA) or name.endswith(("年", "閏")):
        return False
    if name[-1] in "一二三四五六七八九十":
        return False
    if any(ch in _NESTED_VERB for ch in name):
        return False
    return _is_person(name)


def split_note_segments(note: str) -> list[str]:
    """注文按「月数、干支」锚切段，每段一条年表注；无锚整段返回。"""
    cuts = [m.start() for m in RE_ENTRY_SEG.finditer(note)]
    if not cuts:
        return [note] if note else []
    segs = []
    if cuts[0] > 0:
        segs.append(note[:cuts[0]])
    for i, c in enumerate(cuts):
        segs.append(note[c:cuts[i + 1]] if i + 1 < len(cuts) else note[c:])
    return segs


def split_nested_successors(note: str, known: set[str] | None = None,
                            allow_head: bool = False):
    """N1：注文流内嵌套继任者拆分。

    锚 = 界标（。；）+ 2–4 字人名 + 月条目锚；界标处名长按 4→3→2 回退取
    首个合法者（「某某十一、」归 某某+十一月，不拆出「某某十」）。
    allow_head 供 N2 绑定后的余段用（首名前无界标， artificially 补界标）。
    返回 (首人截断 note, [ {person, note, known} ])；嵌套条目 note 自人名后起。
    """
    text = ("。" + note) if allow_head else note
    pad = 1 if allow_head else 0
    # 界标：句读 + 收束前任动作的功能字（遷/改/調/陞/任/起/補 后接官名，不入列——
    # 防「遷右副九、丁亥」类官名片段误切；2026-11-09 扩充，实证「疾歸劉斯潔五、」形态）
    cuts: list[tuple[int, str]] = []
    for m in re.finditer(r"[。；歸事卒免降罷憂]", text):
        p = m.end()
        while p < len(text) and text[p] in " \u3000":
            p += 1                      # 界标后的 OCR 空格不入名
        for L in (4, 3, 2):
            if p + L > len(text):
                continue
            name = text[p:p + L]
            if not _nested_name_ok(name):
                continue
            am = re.match(r"[ \u3000]*(" + RE_ENTRY_SEG_STR + r")", text[p + L:])
            if not am:
                continue
            if "年" in am.group(1):
                continue                # 锚带年前缀 = 纪年（天啟二年…），非人名条目
            cuts.append((p, name))
            break
    if not cuts:
        return note, []
    head = text[pad:cuts[0][0]]
    segs = []
    for i, (p, name) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        segs.append({
            "person": name,
            "note": text[p + len(name):end],
            "known": (known is None) or (name in known),
        })
    return head, segs


def _strip_head_names(raw: str, names: list[str]) -> str:
    """从格文本头部依次剥掉人名（emit 对多格清零了 note，注文从 raw 重构）。
    头部与预期不符（OCR 形态外）时返回空串，宁缺勿错。"""
    rest = raw
    for nm in names:
        s = rest.lstrip(" \u3000")
        if s.startswith(nm):
            rest = s[len(nm):]
        else:
            return ""
    return rest.lstrip(" \u3000")


def apply_note_repairs(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """N2 多名按序绑定 + N1 嵌套继任者拆分（两表共用，OCR 出条目后统一跑）。

    * N2：同格 k 名、注文月条目 ≥ k 段 → 按序 1:1 绑定（迁出注归前任、迁入注归
      继任）；段少于名维持原状不猜配（宁缺勿错）。
    * N1：单名格注文、及 N2 绑定后的余段，扫「界标+人名+月干支锚」拆出嵌套
      继任者：office/year 随格，人名已见表内 conf 0.6、未见 0.5，一律标 review
      留痕；余段无锚部分归还组内末名（跨年注「三年九、…」不丢）。

    返回 (entries', 变更报告 list[str])。
    """
    report: list[str] = []
    known = {e["person"] for e in entries}
    out: list[dict] = []
    i, n = 0, len(entries)
    while i < n:
        e = entries[i]
        if not e["raw"]:
            out.append(e)
            i += 1
            continue
        j = i + 1
        while j < n and not entries[j]["raw"]:
            j += 1
        group = entries[i:j]
        out.extend(group)
        i = j
        tail = None
        multi = len(group) > 1
        # emit 对多格清零 note（防月分误配）→ 多格从 raw 头部剥名重构注文
        note_full = (_strip_head_names(group[0]["raw"],
                                       [g["person"] for g in group])
                     if multi else group[0]["note"])
        if multi and note_full:
            segs = split_note_segments(note_full)
            if len(segs) >= len(group):
                for gi, g in enumerate(group):
                    g["note"] = segs[gi]
                    g["review"] = (g["review"] or "").replace(
                        f"多人同格({len(group)}人)，注文列对应丢失",
                        f"多人同格({len(group)}人)按序绑定")
                tail = "".join(segs[len(group):])
                report.append(f"{group[0]['year']} {group[0]['office']} "
                              f"{'、'.join(g['person'] for g in group)}"
                              f"：{len(group)}名×{len(segs)}段按序绑定")
        elif not multi:
            tail = note_full
        if not tail:
            continue
        head_note, nested = split_nested_successors(tail, known,
                                                    allow_head=multi)
        if not nested:
            if multi and tail:
                # 余段无嵌套锚（跨年注等）→ 归还末名，不丢数据
                last = group[-1]
                last["note"] = (last["note"] + "；" + tail) if last["note"] else tail
            continue
        carrier = group[-1] if multi else group[0]
        carrier["note"] = head_note
        for nd in nested:
            out.append({
                "year": group[0]["year"],
                "office": group[0]["office"],
                "person": nd["person"],
                "note": nd["note"],
                "raw": "",
                "conf": 0.6 if nd["known"] else 0.5,
                "review": "嵌套继任者拆分" + ("" if nd["known"] else "（人名未见表内，待核）"),
            })
            report.append(f"{group[0]['year']} {group[0]['office']} 嵌套拆出 "
                          f"{nd['person']}（{'见表内' if nd['known'] else '新名'}）：{nd['note'][:24]}")
    return out, report


def parse_tables(md: str) -> list[list[list[str]]]:
    out = []
    for tb in re.findall(r"<table>.*?</table>", md, re.S):
        rows = [[text_of(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                for r in re.findall(r"<tr>(.*?)</tr>", tb, re.S)]
        out.append(rows)
    return out


def row_years(cells: list[str]) -> list[int]:
    """一行里出现的全部年份头（宽幅双年页一行含两个年份头）。"""
    ys: list[int] = []
    for c in cells:
        m = RE_YEAR_FULL.search(c)
        if m:
            ys.append(int(m.group(2)))
            continue
        if len(c) <= 20:
            m = RE_YEAR_BARE.search(c)
            if m and 1368 <= int(m.group(1)) <= 1644:
                ys.append(int(m.group(1)))
    return ys


def row_year(cells: list[str]) -> int | None:
    ys = row_years(cells)
    return ys[0] if ys else None


def split_year_pages(tables_per_md: list[list[list[list[str]]]]) -> list[dict]:
    """全部 table → 年页序列；无年份头的表/行归入当前年（续表）；
    一行含两个年份头 = 宽幅双年页，两页共享同一份行数据（dual）。"""
    pages: list[dict] = []
    for tables in tables_per_md:
        for rows in tables:
            for cells in rows:
                ys = row_years(cells)
                if ys:
                    seen = [p for p in pages[-2:] if p.get("dual") and set(p["years"]) == set(ys)]
                    if seen:
                        continue  # 同一双年节重复年份头
                    if len(set(ys)) >= 2:
                        pages.append({"years": sorted(set(ys)), "rows": [], "dual": True})
                    else:
                        y = ys[0]
                        if pages and not pages[-1].get("dual") and pages[-1]["years"] == [y]:
                            continue
                        pages.append({"years": [y], "rows": [], "dual": False})
                elif cells and any(c for c in cells):
                    if not pages:
                        continue
                    pages[-1]["rows"].append(cells)
                elif pages:
                    pages[-1]["rows"].append([])  # 空行占位（空官职带）
    return pages


_PADDLE_LINES: dict[int, list[tuple[str, int]]] = {}


def paddle_lines(pdf_page: int) -> list[tuple[str, int]]:
    """该 PDF 页的 Paddle 行 (去空格文本, x0)，惰性加载。"""
    if pdf_page not in _PADDLE_LINES:
        f = ROOT / "_scratch" / "paddle_jingqing" / "raw_pages" / f"p{pdf_page}.jsonl"
        lines: list[tuple[str, int]] = []
        if f.exists():
            obj = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
            for r in obj.get("result", {}).get("ocrResults") or []:
                pr = r.get("prunedResult") or {}
                for t, box in zip(pr.get("rec_texts") or [], pr.get("rec_boxes") or []):
                    lines.append((re.sub(r"\s+", "", t), box[0]))
        _PADDLE_LINES[pdf_page] = lines
    return _PADDLE_LINES[pdf_page]


def find_dual_page(years: list[int]) -> int | None:
    """在 Paddle 页里找同时含两个年份头的那页。"""
    for p in range(996, 1282):
        texts = " ".join(t for t, _ in paddle_lines(p))
        if all(re.search(rf"[（(]{y}[)）]", texts) for y in years):
            return p
    return None


def resolve_dual_sides(page: dict, rows: list[list[str]]) -> dict[tuple[int, int], int]:
    """双年页：(行号,格号) → 年份。用 Paddle 行 x 坐标对右年份头裁决。"""
    years = page["years"]
    p = find_dual_page(years)
    out: dict[tuple[int, int], int] = {}
    if p is None:
        return out
    lines = paddle_lines(p)
    boundary = min((x for t, x in lines if re.search(rf"[（(]{years[1]}[)）]", t)),
                   default=None)
    if boundary is None:
        return out
    for ri, cells in enumerate(rows):
        head = cells[0] if cells else ""
        office, _ = label_of(head)
        for ci, cell in enumerate(cells[1:] if office else cells):
            if not cell:
                continue
            names, _ = split_persons(cell)
            if not names:
                continue
            n0 = names[0]
            hits = [(t, x) for t, x in lines
                    if t == n0 or (t.startswith(n0) and len(t) <= len(n0) + 2)]
            if len(hits) == 1:
                out[(ri, ci)] = years[0] if hits[0][1] < boundary else years[1]
    return out


def is_note_row(cells: list[str]) -> bool:
    """整行没有一个格子能切出人名、且至少一格有内容 = 上一官职带的换行注文行。"""
    if not any(cells):
        return False
    for c in cells:
        if not c:
            continue
        names, _ = split_persons(c)
        if names:
            return False
    return True


def structure_page(page: dict, ref_seq: list[str]) -> tuple[list[dict], list[str], list[str]]:
    """一页 → (条目, 本页官职序列(有标签年才更新参考), warnings)。"""
    entries: list[dict] = []
    seq: list[str] = []
    warns: list[str] = []
    labelled = False
    cur_office: str | None = None
    last_band: list[tuple[int, dict]] = []  # 上一带的 (格号, 条目)，供换行注文并入
    dual_side = resolve_dual_sides(page, page["rows"]) if page.get("dual") else {}
    attached = 0

    for ri, cells in enumerate(page["rows"]):
        head = cells[0].strip() if cells else ""
        office, paren = label_of(head)
        data_offset = 1
        if office:
            labelled = True
            cur_office = office
            seq.append(office)
        else:
            data_offset = 0
            if cells and is_note_row(cells) and last_band:
                # 换行注文行：按格号并入上一带，不占官职行号
                for ci, cell in enumerate(cells):
                    if not cell:
                        continue
                    band = [e for j, e in last_band if j == ci] or \
                           [e for _, e in last_band]
                    if not band:
                        warns.append(f"{page['years'][0]} 换行注文无归属: {cell[:30]}")
                        continue
                    for e in band:
                        e["note"] = (e["note"] + "；" + cell) if e["note"] else cell
                        e["review"] = ((e["review"] + "；") if e["review"] else "") + "换行注文残片并入"
                        e["conf"] = min(e["conf"], 0.5)
                        attached += 1
                continue
            if labelled and cur_office is None:
                continue
            if not labelled:
                i = len(seq)
                seq.append("")  # 占位，保持行号
                if i < len(ref_seq):
                    cur_office = ref_seq[i]
                else:
                    warns.append(f"{page['years'][0]} 行{ri + 1} 超出参考官职序列({len(ref_seq)}行)")
                    cur_office = None
        if cur_office is None:
            continue
        last_band = []
        for ci, cell in enumerate(cells[data_offset:]):
            if not cell:
                continue
            names, note = split_persons(cell)
            if not names:
                # 混合行里的注文格：并入上一带（同格号优先，其次单条目带）
                band = [e for j, e in last_band if j == ci]
                if not band and len(last_band) == 1:
                    band = [last_band[0][1]]
                if band:
                    for e in band:
                        e["note"] = (e["note"] + "；" + cell) if e["note"] else cell
                        e["review"] = ((e["review"] + "；") if e["review"] else "") + "换行注文残片并入"
                        e["conf"] = min(e["conf"], 0.5)
                    continue
                warns.append(f"{page['years'][0]} {cur_office} 格无法切出人名: {cell[:30]}")
                continue
            year = page["years"][0]
            review, conf, this_note = None, 0.8, note
            if page.get("dual"):
                if (ri, ci) in dual_side:
                    year = dual_side[(ri, ci)]
                else:
                    review = f"双年页({page['years']})列归属未定，暂归{year}"
                    conf = 0.3
            if len(names) > 1:
                review = (review + "；" if review else "") + f"多人同格({len(names)}人)，注文列对应丢失"
                conf, this_note = min(conf, 0.5), ""
            if not page.get("dual") and not labelled:
                review = (review + "；" if review else "") + "无标签年，官职按行序推"
                conf = min(conf, 0.6)
            if not note and not review:
                conf = 0.7
            for k, name in enumerate(names):
                e = {
                    "year": year,
                    "office": cur_office,
                    "person": name,
                    "note": this_note if (len(names) == 1 or k == 0) else "",
                    "raw": cell if k == 0 else "",
                    "conf": round(conf, 2),
                    "review": review,
                }
                entries.append(e)
                last_band.append((ci, e))
    if attached:
        warns.insert(0, f"本页换行注文残片并入 {attached} 处")
    return entries, seq, warns


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=1368)
    ap.add_argument("--to-year", type=int, default=1644)
    args = ap.parse_args()

    pages = split_year_pages([parse_tables(p.read_text(encoding="utf-8")) for p in MD])
    years = [y for p in pages for y in p["years"]]
    missing = [y for y in range(args.from_year, args.to_year + 1) if y not in years]
    dupes = [y for y in set(years) if years.count(y) > 1]

    entries: list[dict] = []
    all_warns: list[str] = []
    ref_seq: list[str] = []
    ref_year = None
    for page in pages:
        if not (args.from_year <= page["years"][0] <= args.to_year):
            continue
        es, seq, warns = structure_page(page, ref_seq)
        entries.extend(es)
        all_warns += warns
        if seq and seq[0]:  # 有标签年 → 更新参考序列
            ref_seq = [o for o in seq if o]
            ref_year = page["years"][0]

    entries, rep = apply_note_repairs(entries)
    if rep:
        print(f"N1/N2 注文修复 {len(rep)} 处：")
        for r in rep[:15]:
            print("  ·", r)

    review = [e for e in entries if e["review"]]
    got_years = sorted({e["year"] for e in entries})
    payload = {
        "meta": {
            "dataset": "京卿年表（京師）（试点）",
            "source": "张德信《明代職官年表》册1 正文 981–1266（PDF 996–1281）；MinerU OCR",
            "year_range": [min(got_years), max(got_years)] if got_years else None,
            "pilot_range": [args.from_year, args.to_year],
            "stats": {
                "entries": len(entries),
                "years": len(got_years),
                "year_pages": len([p for p in pages if args.from_year <= p["years"][0] <= args.to_year]),
                "missing_years": missing,
                "dup_years": dupes,
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "review": len(review),
                "warn": len(all_warns),
                "conf_avg": round(sum(e["conf"] for e in entries) / len(entries), 3) if entries else None,
            },
            "note": "无标签年官职按最近有标签年的行序推（8 行框架，实拍验证）；"
                    "多人同格注文不猜配；裸年份头纪年由年号表反查。均需回原书页核。",
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    st = payload["meta"]["stats"]
    print(f"年页 {st['year_pages']}（应 {args.to_year - args.from_year + 1}）；缺年 {missing or '无'}；重复年 {dupes or '无'}")
    print(f"条目 {st['entries']}；人数 {st['persons']}；有注 {st['with_note']}；待核 {st['review']}；警告 {st['warn']}")
    if ref_year:
        print(f"参考官职序列（{ref_year}）：{' / '.join(ref_seq)}")
    for w in all_warns[:15]:
        print("  ⚠", w)
    # 锚点抽印
    anchors = {"1386": ["蔡瑄", "趙勉", "商敬"], "1387": ["蔡瑄", "趙勉", "耿瑄"],
               "1570": ["楊思忠", "王正國", "董傳策"], "1368": ["周禎"]}
    for y, names in anchors.items():
        if args.from_year <= int(y) <= args.to_year:
            es = [e for e in entries if e["year"] == int(y)]
            tag = " ".join(f"{e['office']}:{e['person']}" for e in es)
            ok = all(any(n in e["person"] for e in es) for n in names)
            print(f"  锚点 {y} {'✓' if ok else '✗'} | {tag[:150]}")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
