# -*- coding: utf-8 -*-
"""册1 部院大臣年表（京師）OCR → 结构化提取物。

输入: _scratch/mineru_buyuan/vol1_buyuan_{a,b}.md（MinerU 输出，不入仓）
输出: src/mingoff/data/vol1_buyuan_entries.json   源提取物（入仓）
      src/mingoff/data/vol1_buyuan_review.json    待校清单（入仓）
      src/mingoff/data/vol1_buyuan_manifest.json  溯源与校验（入仓）

解析策略（docs/部院OCR形态普查.md 第八节，v3）：
  分年 → 逐格 → 贪心名串分解（词典最长匹配 + 注文起始特征边界）：
    - "茹瑞張紳杜澤九、丁亥…" → 茹瑞/張紳/杜澤 + 注（词典驱动，标点不再是屏障）；
    - 标签行 = office；rowspan 标签组续行（名行/注行）并入该组；
    - 无标签年：纯名行开新组、纯注行并上一组、混合行开新组逐格切；
    - office 三级锚定（①人名锚 ②组数对齐按序 ③顺序兜底）；组数>行数的多行组合法；
    - 1644 纯文本段：据原书 PDF 694 人工定 office（BOOK_PATCH）。

运行:  PYTHONPATH=src python -m mingoff.ocr_buyuan
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[3]            # guji-pipeline/
MD_DIR = REPO / "_scratch" / "mineru_buyuan"
OUT_DIR = Path(__file__).resolve().parent / "data"

# ---- 标签词表（census6 实测）----
LABEL_SET = {
    "吏部", "戶部", "户部", "禮部", "兵部", "刑部", "工部", "都察院",
    "御史臺", "御史府", "總督京儲", "總倉場", "總督倉場", "督倉場",
    "御史臺大夫", "御史府大夫",
}
LABEL_CANON = {
    "户部": "戶部", "總督倉場": "總倉場", "督倉場": "總倉場",
    "御史臺大夫": "御史臺", "御史府大夫": "御史府",
}
YEAR_RE = re.compile(r"[（(](\d{4})[）)]")
YEAR_MIN, YEAR_MAX = 1368, 1644
NOTE_START = re.compile(
    r"^(?:是年|卒|免|尋|寻|後无|後無|扈駕|扈從|署|正|"
    r"[一二三四五六七八九十廿卅卌]+、|\d+、|[一二三四五六七八九十廿卅卌]+年|"
    r"[一二三四五六七八九十]+月)"
)
# 年号屏蔽：绝不能当人名
ERAS = {"洪武", "建文", "永樂", "洪熙", "宣德", "正統", "景泰", "天順",
        "成化", "弘治", "正德", "嘉靖", "隆慶", "萬曆", "万历",
        "泰昌", "天啟", "天启", "崇禎", "崇祯", "弘光", "南明", "閏月"}
HAS_PUNCT = re.compile(r"[，。、；：,;？！]")
CJK = r"\u4e00-\u9fff"
NAME_RE = re.compile(rf"^[{CJK}]+$")
ROWSPAN_RE = re.compile(r'rowspan="(\d+)"')


def norm(t: str) -> str:
    return re.sub(r"\s+", "", t)


def cell_tokens(cell: str):
    return [norm(t) for t in re.split(r"\s+", cell.strip()) if norm(t)]


# ---------- 贪心名串分解 ----------

def split_token(tok: str, names: set):
    """一个 token → [[person, note, flag], ...]"""
    if not tok:
        return []
    if tok in names:
        return [[tok, "", ""]]
    if NOTE_START.match(tok) or HAS_PUNCT.search(tok[:1]):
        return [["", tok, ""]]
    res = []
    i = 0
    while i < len(tok):
        rest = tok[i:]
        m = NOTE_START.match(rest)
        if m:
            if res:
                res[-1][1] += rest
            else:
                res.append(["", rest, "orphan?"])
            return res
        hit = None
        for n in (4, 3, 2):
            if len(rest) >= n and rest[:n] in names:
                hit = (n, "")
                break
        if hit is None:
            for n in (2, 3, 4):
                if (len(rest) >= n and NAME_RE.match(rest[:n])
                        and rest[:n] not in ERAS):
                    after = rest[n:]
                    if not after or NOTE_START.match(after) or _starts_with_name(after, names):
                        hit = (n, "split?")
                        break
        if hit is None:
            if res:
                res[-1][1] += rest
                res[-1][2] = (res[-1][2] + ";note?").strip(";")
            else:
                res.append(["", rest, "note?"])
            return res
        n, flag = hit
        res.append([rest[:n], "", flag])
        i += n
    return res


def _starts_with_name(t: str, names: set) -> bool:
    return any(len(t) >= n and t[:n] in names for n in (4, 3, 2))


STOP_PERSONS = {"署", "兼署", "協理", "卒", "免", "任", "試", "扈駕", "扈從"}


def split_cell(cell: str, names: set):
    """一格 → [[person, note, flag]]；跨 token 共享当前人（注文接前名）。"""
    out, cur = [], None
    for tok in cell_tokens(cell):
        if len(tok) > 260:  # 巨型格内容（OCR 吞页），标记后仍切
            flag = "giant-cell"
        else:
            flag = ""
        parts = split_token(tok, names)
        for j, (p, n, f) in enumerate(parts):
            fl = f or flag
            if p:
                if cur:
                    out.append(cur)
                cur = [p, n, fl]
            elif cur is not None:
                cur[1] += n
                if fl:
                    cur[2] = (cur[2] + ";" + fl).strip(";")
            elif j > 0 and out:
                out[-1][1] += n
            else:
                out.append(["", n, fl or "orphan"])
            # 纯功能词人名 → 降为注
    if cur:
        out.append(cur)
    # 过滤功能词/纪年碎片"人名"
    fixed = []
    for p, n, f in out:
        if p and (p in STOP_PERSONS or any(p.startswith(e) for e in ERAS)
                  or re.match(r"^玄?[\d一二三四五六七八九十]+年$", p)):
            n = p + n
            p = ""
        fixed.append([p, n, f])
    return fixed


def cell_is_pure_note(cell: str, names: set) -> bool:
    toks = cell_tokens(cell)
    if not toks:
        return False
    return all(not split_token(t, names)[0][0] for t in toks)


def cell_is_pure_name(cell: str, names: set) -> bool:
    toks = cell_tokens(cell)
    if not toks:
        return False
    items = []
    for t in toks:
        items.extend(split_token(t, names))
    return all(p and not n for p, n, f in items)


# ---------- pass A：分年取行 ----------

def segment_rows(md: str):
    out, cur, jumps = [], None, []
    for t in re.findall(r"<table>.*?</table>", md, re.S):
        for row in re.findall(r"<tr.*?</tr>", t, re.S):
            cells = [re.sub(r"<[^>]+>", "", c) for c in
                     re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            ym = None
            for c in cells:
                m = YEAR_RE.search(c)
                if m and YEAR_MIN <= int(m.group(1)) <= YEAR_MAX:
                    ym = int(m.group(1))
                    break
            if ym is not None:
                if cur is None or ym > cur:
                    if cur is not None and ym - cur > 2:
                        jumps.append((cur, ym))
                    cur = ym
                continue
            if cur is None or not any(c.strip() for c in cells):
                continue
            out.append((cur, cells, row))
    return out, jumps


# ---------- pass B：人名词典 ----------

def build_names(rows) -> set:
    names = set()
    for _ in range(3):
        added = set()
        for _, cells, _r in rows:
            for c in cells:
                for tok in cell_tokens(c):
                    if (NAME_RE.match(tok) and 2 <= len(tok) <= 5
                            and not HAS_PUNCT.search(tok) and not NOTE_START.match(tok)):
                        if tok.endswith("署"):
                            tok = tok[:-1]
                        added.add(tok)
                    else:
                        for p, _n, _f in split_token(tok, names):
                            if p:
                                added.add(p)
        if added <= names:
            break
        names |= added
    # 清洗：年号/月份屏蔽；可分解为两个已知名的连串剔除（劉觀王彰类）
    names = {n for n in names if n not in ERAS and not NOTE_START.match(n)}
    drop = set()
    for n in names:
        if len(n) >= 4:
            for k in (2, 3):
                if n[:k] in names and n[k:] in names:
                    drop.add(n)
                    break
    # 清洗后激活启发式屏蔽
    return names - drop


# ---------- pass C：组装名行组 ----------

def build_groups(rows, names):
    groups = []
    last_group = None
    pending = None  # {"group": g, "rows_left": n} 标签 rowspan 续行
    for year, cells, raw in rows:
        head = norm(cells[0])
        if head in LABEL_SET:
            g = {"year": year, "office": LABEL_CANON.get(head, head), "items": [],
                 "labeled": True, "raw": raw}
            for c in cells[1:]:
                if not c.strip():
                    g["items"].append(["", "", ""])
                    continue
                g["items"].extend(split_cell(c, names))
            groups.append(g)
            last_group = g
            m = ROWSPAN_RE.search(raw[:raw.find(">") + 1] if ">" in raw else raw)
            m2 = ROWSPAN_RE.search(raw.split("</td>")[0])
            n = None
            for mm in (m2, m):
                if mm and int(mm.group(1)) > 1:
                    n = int(mm.group(1)) - 1
                    break
            pending = {"group": g, "rows_left": n} if n else None
            continue
        # 标签 rowspan 续行：并入该组
        if pending and pending["rows_left"] > 0:
            g = pending["group"]
            pending["rows_left"] -= 1
            for i, c in enumerate(cells):
                if not c.strip():
                    continue
                if cell_is_pure_note(c, names):
                    note = norm(c)
                    if i < len(g["items"]):
                        g["items"][i][1] += note
                    elif g["items"]:
                        g["items"][-1][1] += note
                    else:
                        g["items"].append(["", note, "orphan"])
                else:
                    g["items"].extend(split_cell(c, names))
            continue
        pure_name = all(cell_is_pure_name(c, names) for c in cells if c.strip())
        pure_note = all(cell_is_pure_note(c, names) for c in cells if c.strip())
        if pure_note and last_group is not None and last_group["year"] == year:
            for i, c in enumerate(cells):
                if not c.strip():
                    continue
                note = norm(c)
                if i < len(last_group["items"]):
                    last_group["items"][i][1] += note
                elif last_group["items"]:
                    last_group["items"][-1][1] += note
                else:
                    last_group["items"].append(["", note, "orphan"])
            continue
        # 名行或混合行 → 新组
        g = {"year": year, "office": None, "items": [], "labeled": False, "raw": raw}
        for c in cells:
            if not c.strip():
                g["items"].append(["", "", ""])  # 空位占位保列对齐
                continue
            if cell_is_pure_name(c, names):
                for p, n, f in split_cell(c, names):
                    if not p:
                        continue
                    flag = f
                    if p.endswith("署"):
                        p, flag = p[:-1], "署"
                    g["items"].append([p, n, flag])
            else:
                g["items"].extend(split_cell(c, names))
        groups.append(g)
        last_group = g
    return groups


# ---------- office 锚定 ----------

def anchor_offices(groups):
    poffice = defaultdict(lambda: defaultdict(list))
    for g in groups:
        if g["office"] and g["labeled"]:
            for it in g["items"]:
                if it[0]:
                    poffice[it[0]][g["office"]].append(g["year"])
    labeled_by_year = defaultdict(list)   # year → [group…]（按出现序）
    for g in groups:
        if g["office"] and g["labeled"]:
            labeled_by_year[g["year"]].append(g)
    unlabeled = defaultdict(list)
    for g in groups:
        if g["office"] is None:
            unlabeled[g["year"]].append(g)

    stats = Counter()
    for y, gs in sorted(unlabeled.items()):
        ref = None
        for d in (1, -1, 2, -2, 3, -3, 4, -4):
            if y + d in labeled_by_year:
                ref = labeled_by_year[y + d]
                break
        ref_offices = [g["office"] for g in ref] if ref else []
        anchored = []
        for g in gs:
            cand = Counter()
            for it in g["items"]:
                if not it[0]:
                    continue
                for off, ys in poffice.get(it[0], {}).items():
                    if any(abs(yy - y) <= 6 for yy in ys):
                        cand[off] += 1
            if cand:
                off, n = cand.most_common(1)[0]
                if n / sum(cand.values()) >= 0.5:
                    g["office"] = off
                    anchored.append(off)
                    stats["①人名锚"] += 1
        if ref and len(gs) == 1:
            pass
        if ref and len(gs) == len(ref_offices):
            remaining = [o for o in ref_offices if o not in anchored]
            empties = [g for g in gs if g["office"] is None]
            if len(empties) == len(remaining):
                for g, o in zip(empties, remaining):
                    g["office"] = o
                    stats["②按序补"] += 1
        if any(g["office"] is None for g in gs) and ref:
            used = [g["office"] for g in gs if g["office"]]
            remaining = [o for o in ref_offices if o not in used]
            for g in gs:
                if g["office"] is None and remaining:
                    g["office"] = remaining.pop(0)
                    g["flag"] = (g.get("flag") or "") + ";③顺序兜底"
                    stats["③兜底"] += 1
        offs = [g["office"] for g in gs if g["office"]]
        # 组数 == 参照行数时，office 重复才是异常；多行组（组数>行数）合法
        if ref and len(gs) == len(ref_offices) and len(offs) != len(set(offs)):
            for g in gs:
                if g["office"]:
                    g["flag"] = (g.get("flag") or "") + ";office重复"
                    stats["office重复"] += 1
        for g in gs:
            if g["office"] is None:
                stats["未定office"] += 1
    return stats


# ---------- 1644 纯文本段 ----------

def parse_text_1644(md_b: str):
    tail = md_b[md_b.rfind("</table>") + len("</table>"):]
    heads = [h.strip() for h in re.findall(r"^#{1,6} *(.+)$", tail, re.M) if h.strip()]
    ym = YEAR_RE.search(heads[0]) if heads else None
    if not ym or int(ym.group(1)) != 1644:
        return []
    persons = [norm(h) for h in heads[1:]]
    # 原书 PDF 694（正文 679）人工核对：8 行 10 人
    mapping = [
        ("吏部", ["李遇知"]), ("戶部", ["倪元璐"]), ("禮部", ["王鐸"]),
        ("兵部", ["張縉彥"]), ("刑部", ["張忻"]), ("工部", ["范景文"]),
        ("總倉場", ["吴履中", "陳必謙"]), ("都察院", ["党崇雅", "李邦華"]),
    ]
    got = [p for _, ps in mapping for p in ps]
    flag = "BOOK_PATCH"
    if got != persons:
        flag += ";names-mismatch"
    out = []
    for off, ps in mapping:
        items = [[p, "", flag if p not in persons else ""] for p in ps]
        out.append({"year": 1644, "office": off, "items": items,
                    "labeled": False, "raw": "text-1644", "flag": flag})
    return out


# ---------- 主流程 ----------

def main():
    md_a = (MD_DIR / "vol1_buyuan_a.md").read_text(encoding="utf-8")
    md_b = (MD_DIR / "vol1_buyuan_b.md").read_text(encoding="utf-8")
    md = md_a + md_b

    rows, jumps = segment_rows(md)
    names = build_names(rows)
    groups = build_groups(rows, names)
    groups += parse_text_1644(md_b)
    stats = anchor_offices(groups)

    entries, review = [], []
    seen = set()
    for g in groups:
        for it in g["items"]:
            person, note, flag = it
            if not person:
                if note.strip():
                    review.append({"year": g["year"], "office": g["office"],
                                   "issue": "orphan-note", "raw": note[:80]})
                continue
            key = (g["year"], g["office"], person)
            e = {"year": g["year"], "office": g["office"], "person": person,
                 "note": note,
                 "src": "text-1644" if g["raw"] == "text-1644" else "table",
                 "raw_person": person}
            flags = []
            if flag:
                flags.append(flag)
            if g.get("flag"):
                flags.append(g["flag"])
            if key in seen:
                flags.append("dup")
            if flags:
                e["flag"] = ";".join(dict.fromkeys(flags))
            if "dup" in e.get("flag", ""):
                review.append({"year": g["year"], "office": g["office"],
                               "issue": "dup-person", "raw": person})
            if e["office"] is None:
                review.append({"year": g["year"], "office": None,
                               "issue": "no-office", "raw": person})
            if "split?" in e.get("flag", "") or "note?" in e.get("flag", ""):
                review.append({"year": g["year"], "office": g["office"],
                               "issue": "split?", "raw": person + "|" + note[:60]})
            seen.add(key)
            entries.append(e)

    entries.sort(key=lambda e: (e["year"], e["office"] or "", e["person"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "vol1_buyuan_entries.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "vol1_buyuan_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    years = sorted({e["year"] for e in entries})
    missing = [y for y in range(YEAR_MIN, YEAR_MAX + 1) if y not in set(years)]
    per_year = Counter(e["year"] for e in entries)
    manifest = {
        "source": "张德信《明代职官年表》册1「部院大臣年表(京師)」（扫描 PDF）",
        "pdf_pages": 1281, "offset": 15,
        "book_pages": [401, 680], "pdf_range": [416, 695],
        "slices": [
            {"file": "vol1_buyuan_a.pdf", "pdf_pages": [416, 615], "count": 200, "chars": len(md_a)},
            {"file": "vol1_buyuan_b.pdf", "pdf_pages": [616, 695], "count": 80, "chars": len(md_b)},
        ],
        "tool": {"name": "MinerU", "params": {"ocr": True, "table": True, "language": "ch"}},
        "submitted_at": "2026-10-17T18:55:47+08:00",
        "batch_id": "79f53249-fdb5-4f7f-a405-7000658ffe39",
        "parser": "src/mingoff/ocr_buyuan.py",
        "strategy": "docs/部院OCR形态普查.md 第八节（v3：贪心名串分解+rowspan续行+三级锚定）",
        "gates": {
            "O2_年份连续": f"{'pass' if not missing else '缺年:' + str(missing)}（{len(years)}/277）",
            "O3_行重组": "名行/注行节律重组；异常进 review",
            "O4_名归一": "原文保留 raw_person；变体归一留待 CBDB 对齐阶段",
            "O5_人工抽检": "锚点抽验见普查报告第七节；evidence 8 页",
        },
        "year_header_jumps": jumps,
        "stats": {
            "entries": len(entries),
            "persons_unique": len({e["person"] for e in entries}),
            "years": len(years), "missing_years": missing,
            "no_office_entries": sum(1 for e in entries if e["office"] is None),
            "review_items": len(review), "name_dict": len(names),
            "anchor_stats": dict(stats),
            "per_year_min": min(per_year.values()) if per_year else 0,
            "per_year_max": max(per_year.values()) if per_year else 0,
        },
        "evidence": [
            "docs/evidence/book_p402_bujuan1368.png",
            "docs/evidence/book_p405_bujuan1371.png",
            "docs/evidence/book_p422_bujuan1388.png",
            "docs/evidence/book_p484_bujuan1449.png",
            "docs/evidence/book_p555_bujuan1520.png",
            "docs/evidence/book_p625_bujuan1590.png",
            "docs/evidence/book_p645_bujuan1610.png",
            "docs/evidence/book_p679_bujuan1644.png",
        ],
    }
    (OUT_DIR / "vol1_buyuan_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== 部院大臣年表解析结果（v3）===")
    print(f"entries={len(entries)}  独立人名={len({e['person'] for e in entries})}  "
          f"年覆盖={len(years)}/277  缺年={missing or '无'}")
    print(f"无office={sum(1 for e in entries if e['office'] is None)}  "
          f"待校={len(review)}  词典={len(names)}  年份跳变={jumps or '无'}")
    print(f"锚定={dict(stats)}")
    low = [(y, per_year[y]) for y in years if per_year[y] < 7]
    print(f"少于7条的年({len(low)}):", low[:30])
    print("\n样例:")
    for e in entries[:3] + entries[900:902] + entries[-3:]:
        print(" ", json.dumps(e, ensure_ascii=False)[:170])
    print(f"\n输出: {OUT_DIR}\\vol1_buyuan_{{entries,review,manifest}}.json")


if __name__ == "__main__":
    main()
