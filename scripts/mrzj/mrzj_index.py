# -*- coding: utf-8 -*-
"""INDEX（PDF 1074–1189）→ 人名目录，并与正文 OCR 对校。

INDEX 体例：三栏，按 Wade-Giles 排序，每条 = 罗马字 + 汉字名 + 正文页。

产物:
  _scratch/mineru_mrzj/index_catalog.json    [{name, pages[], roman, index_page}]
  _scratch/mineru_mrzj/index_check.json      逐条对校结果
  _scratch/mineru_mrzj/index_check.md        人读摘要

对校口径（不依赖正文条目切分是否完美）:
  目录说「某人见 pX」→ 正文 pX 的 OCR 文本里是否出现该名；
  出现即 ok；不出现再看全书别页是否有条目开头，判 page_mismatch 或 name_missing。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
OUT = BASE / "out"
CJK = r"\u4e00-\u9fff"
OFFSET = 25

LINE_NAME_PAGE = re.compile(rf"^(.*?)\s*([{CJK}](?:\s*[{CJK}]){{1,3}})\s*(\d{{1,3}})\s*$")
# 行内扫描：汉字名 + 页码（一格常挤多条，不能用整行匹配）
NAME_PAGE = re.compile(
    rf"([{CJK}](?:\s?[{CJK}]){{1,3}})\s*(\d{{1,3}})(?![0-9])"
)
VARIANTS = str.maketrans({"黄": "黃", "吕": "呂", "杨": "楊", "吴": "吳", "苏": "蘇", "郑": "鄭", "颜": "顏"})

ROMAN_CHARS = re.compile(r"^[A-Za-z'’.\-\s]+$")
LATIN_ONLY = re.compile(r"^[A-Za-z][A-Za-z'’.\-\s]*$")


def table_columns(md: str) -> list[list[str]]:
    """把页面表格按列重建：同一 <td> 序号跨 <tr> 纵向拼接后的行串。"""
    cols: list[list[str]] = []
    for body in re.findall(r"<table>(.*?)</table>", md, re.S):
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            while len(cols) < len(cells):
                cols.append([])
            for i, c in enumerate(cells):
                c = re.sub(r"<[^>]+>", "", c)
                c = c.replace("&#x27;", "'").replace("&amp;", "&")
                for line in c.splitlines():
                    line = line.strip()
                    if line:
                        cols[i].append(line)
    return cols


def parse_index() -> list[dict]:
    entries: list[dict] = []
    for f in sorted(OUT.glob("p*.md")):
        pdfp = int(f.stem[1:5])
        if not (1074 <= pdfp <= 1189):
            continue
        md = f.read_text(encoding="utf-8")
        cols = table_columns(md)
        if not cols:
            # 少数页 MinerU 输出为纯文本（无 <table>），退化为整页一条流
            body = re.sub(r"<[^>]+>", "", md).replace("&#x27;", "'")
            cols = [[ln.strip() for ln in body.splitlines() if ln.strip()]]
        for ci, lines in enumerate(cols):
            s = " ".join(lines)
            prev = 0
            for m in NAME_PAGE.finditer(s):
                name = re.sub(r"\s+", "", m.group(1)).translate(VARIANTS)
                page = int(m.group(2))
                if not (1 <= page <= 963):
                    prev = m.end()
                    continue
                pre = s[prev : m.start()]
                roman = ""
                # 罗马字 = 本条之前、上一页码之后的拉丁串
                tail = re.split(r"\d{1,3}", pre)[-1] if pre else ""
                tail = tail.strip(" .-—")
                if tail and ROMAN_CHARS.match(tail):
                    roman = tail.strip()
                entries.append(
                    {
                        "name": name,
                        "page": page,
                        "roman": roman,
                        "index_page": pdfp - 1073,
                        "col": ci,
                    }
                )
                prev = m.end()
    return entries


def build_catalog(entries: list[dict]) -> list[dict]:
    by: dict[str, dict] = {}
    for e in entries:
        k = e["name"]
        d = by.setdefault(k, {"name": k, "pages": set(), "roman": e["roman"], "index_page": e["index_page"]})
        d["pages"].add(e["page"])
        if e["roman"] and not d["roman"]:
            d["roman"] = e["roman"]
    out = []
    for d in by.values():
        out.append({**d, "pages": sorted(d["pages"])})
    return sorted(out, key=lambda x: x["pages"][0])


def edit1(a: str, b: str) -> bool:
    """长度相同差一字，或长度差 1 且只多/少一字。"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :]


def near_on_page(name: str, text: str) -> list[str]:
    """在页内找与 name 同姓、一字之差的候选（含同长与差一长）。"""
    cands: list[str] = []
    for m in re.finditer(re.escape(name[0]), text):
        i = m.start()
        for L in (len(name) - 1, len(name), len(name) + 1):
            if L < 2:
                continue
            w = text[i : i + L]
            if len(w) == L and re.fullmatch(rf"[{CJK}]+", w) and edit1(name, w):
                cands.append(w)
    from collections import Counter

    return [w for w, _ in Counter(cands).most_common(3)]


def main():
    entries = parse_index()
    # 已由正文验证的姓氏修正（罗马字定姓 + 该页确有正确名）
    fpath = BASE / "confirmed_roman_fixes.json"
    if fpath.exists():
        fmap = {(f["page"], f["old"]): f["new"] for f in json.loads(fpath.read_text(encoding="utf-8"))}
        for e in entries:
            k = (e["page"], e["name"])
            if k in fmap:
                e["name"] = fmap[k]
    # 已由正文条目开头验证的页码修正
    ppath = BASE / "page_fixes.json"
    if ppath.exists():
        pmap = {(f["old_page"], f["name"]): f["new_page"]
                for f in json.loads(ppath.read_text(encoding="utf-8"))}
        for e in entries:
            k = (e["page"], e["name"])
            if k in pmap:
                e["page"] = pmap[k]
    catalog = build_catalog(entries)
    (BASE / "index_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    csrc = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "corpus.json"
    hsrc = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / "body_heads.json"
    corpus = {
        p["printed_page"]: p["text"].translate(VARIANTS)
        for p in json.loads(csrc.read_text(encoding="utf-8"))
    }
    heads_by_page = {
        r["printed_page"]: set(r["heads"])
        for r in json.loads(hsrc.read_text(encoding="utf-8"))
    }
    all_pages = defaultdict(list)
    for pg, hs in heads_by_page.items():
        for h in hs:
            all_pages[h].append(pg)

    checks = []
    for c in catalog:
        name, pages = c["name"], c["pages"]
        ok_pages = [p for p in pages if name in corpus.get(p, "")]
        if ok_pages:
            checks.append({**c, "status": "ok", "body_pages": ok_pages[:5]})
            continue
        near = []
        for p in pages:
            near.extend(w for w in near_on_page(name, corpus.get(p, "")) if w != name)
        if near:
            from collections import Counter

            top = Counter(near).most_common(1)[0][0]
            checks.append({**c, "status": "ocr_variant", "body_pages": [], "variant": top})
            continue
        if all_pages.get(name):
            checks.append({**c, "status": "page_mismatch", "body_pages": all_pages[name][:5]})
        else:
            checks.append({**c, "status": "name_missing", "body_pages": []})

    (BASE / "index_check.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 收紧：变体必须同长、且是该页的条目开头、且该页内一对一
    cand = [
        (x["pages"][0], x["name"], x["variant"])
        for x in checks
        if x["status"] == "ocr_variant"
        and len(x["variant"]) == len(x["name"])
        and x["variant"] in heads_by_page.get(x["pages"][0], set())
    ]
    byv = defaultdict(list)
    for pg, n, v in cand:
        byv[(pg, v)].append(n)
    strict = {(pg, n): v for pg, n, v in cand if len(byv[(pg, v)]) == 1}
    for x in checks:
        pg = x["pages"][0]
        if (pg, x["name"]) in strict:
            x["status"] = "fixed"
            x["fixed_to"] = strict[(pg, x["name"])]
    (BASE / "index_check.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    c = Counter(x["status"] for x in checks)
    lines = [
        "# INDEX 人名目录对校",
        "",
        f"- 目录条目（去重后）：**{len(catalog)}** 人；解析原始条目 {len(entries)} 条",
        "",
        "| 状态 | 人数 | 含义 |",
        "|---|---|---|",
        f"| ok | {c['ok']} | 目录页正文里逐字有此名 |",
        f"| fixed | {c['fixed']} | 同页同长、一字差、且唯一 → 正文 OCR 可定向改 |",
        f"| ocr_variant | {c['ocr_variant']} | 同页有近名但证据不足（多对一/异长），待人工 |",
        f"| page_mismatch | {c['page_mismatch']} | 全书有条目，但不在目录所标页 |",
        f"| name_missing | {c['name_missing']} | 该页与全书皆无（疑漏行或严重错字） |",
        "",
        "## 可定向改的正文 OCR（目录名 → 正文现写法）",
    ]
    for x in [y for y in checks if y["status"] == "fixed"][:200]:
        lines.append(f"- p{x['pages'][0]}  {x['name']} → `{x['fixed_to']}`")
    lines.append("\n## page_mismatch")
    for x in [y for y in checks if y["status"] == "page_mismatch"][:30]:
        lines.append(f"- {x['name']}  目录 p{x['pages']} → 正文条目 p{x['body_pages']}")
    (BASE / "index_check.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"目录 {len(catalog)} 人 / 原始 {len(entries)} 条")
    for k in ("ok", "fixed", "ocr_variant", "page_mismatch", "name_missing"):
        print(f"  {k}: {c[k]}")
    print("->", BASE / "index_check.md")


if __name__ == "__main__":
    main()
