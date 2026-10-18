# -*- coding: utf-8 -*-
"""《明人傳記資料索引》单页 OCR → 条目（v2）。

输入: _scratch/mineru_mrzj/out/pNNNN.content_list.json（单页一文件）
输出: _scratch/mineru_mrzj/out/entries.json

v2 相对 v1 的修正：
1. 人名边界必须**前面是 `)`、`。`、`】` 或行首**，否则「字文玉,號鑑海」里的
   「文玉」会被当成新条目（v1 就是这么炸的）。
2. 按列重建后用「上一列末条 ← 本列首段」的规则拼接跨列断条，
   再跨页拼接跨页断条。
3. 标点归一：半角逗号夹汉字之间还原全角；页码块里的 `-20` 清洗成 `20`。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CJK = r"\u4e00-\u9fff"
BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj\out")

# 候选人名：2–4 汉字，后接 「，/字/號/初名/以字行/（年份/(年份」
CAND = re.compile(
    rf"([{CJK}]{{2,4}})(?=，|字|號|初名|以字行|（\(?\d{{3}}|\(\d{{3}})"
)
DATE_PAREN = re.compile(r"[（(]\d{3,4}\s*[—–\-]*\s*\d{0,4}[）)]$")
# 引文收尾：`)`、`/页码[上下]?`、`。`、`】`
CITE_TAIL = re.compile(r"(?:[)）]|/\d+[下上]?|\d+[下上]|[。】])$")
NAME_STOP = set("字號初以改別晚又自人氏妻母父弟男")
COMMA_FIX = re.compile(rf"(?<=[{CJK}0-9）)]),(?=[{CJK}（(0-9])")
BORN = re.compile(r"[（(](\d{3,4})\s*[—–\-]+\s*(\d{3,4})?[）)]")


def norm(s: str) -> str:
    return COMMA_FIX.sub("，", s)


def find_heads(text: str) -> list[tuple[int, str]]:
    """返回 [(名字起点, 名字)]，只保留前面是引文收尾的候选。"""
    heads = []
    for m in CAND.finditer(text):
        name = m.group(1)
        s = m.start()
        if name[0] in NAME_STOP:
            continue
        if s == 0:  # 列首
            heads.append((s, name))
            continue
        left = text[max(0, s - 24) : s]
        if not CITE_TAIL.search(left):
            continue
        if left.endswith((")", "）")) and DATE_PAREN.search(left):
            continue  # 生卒括号后的「字…」不是人名
        heads.append((s, name))
    # 去重叠（同一位置只留最长）
    out: list[tuple[int, str]] = []
    for h in heads:
        if out and h[0] < out[-1][0] + len(out[-1][1]):
            continue
        out.append(h)
    return out


def columns(table_body: str) -> list[str]:
    rows = re.findall(r"<tr>(.*?)</tr>", table_body, re.S)
    cols: list[list[str]] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        while len(cols) < len(cells):
            cols.append([])
        for i, c in enumerate(cells):
            c = re.sub(r"<[^>]+>", "", c).strip()
            if c:
                cols[i].append(c)
    return ["".join(parts) for parts in cols if parts]


def split_col(text: str) -> tuple[list[str], str]:
    """一列 → (完整条目列表, 列首未归属的碎片)。"""
    heads = find_heads(text)
    if not heads:
        return [], text
    lead = text[: heads[0][0]]
    out = []
    for i, (s, _name) in enumerate(heads):
        e = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        out.append(text[s:e].strip())
    return out, lead


def parse_page(path: Path) -> dict:
    blocks = json.loads(path.read_text(encoding="utf-8"))
    printed = ""
    group = ""
    tables: list[str] = []
    for b in blocks:
        t = b.get("type")
        if t == "page_number":
            printed = re.sub(r"[^0-9]", "", b.get("text") or "")
        elif t in ("text", "aside_text"):
            s = (b.get("text") or "").strip()
            if "劃" in s or s.startswith("【"):
                group = s
        elif t == "table" and b.get("table_body"):
            tables.append(b["table_body"])
    return {"file": path.stem, "printed": printed, "group": group, "tables": tables}


def build(pages: list[Path]) -> list[dict]:
    entries: list[dict] = []
    carry = ""  # 跨列/跨页未完成的尾巴
    for path in pages:
        pg = parse_page(path)
        col_texts: list[str] = []
        for tb in pg["tables"]:
            col_texts.extend(columns(tb))
        for ci, txt in enumerate(col_texts):
            txt = norm(txt)
            segs, lead = split_col(txt)
            if lead.strip():
                if entries:
                    entries[-1]["raw"] += lead.strip()
                else:
                    carry += lead.strip()
            for s in segs:
                entries.append(
                    {
                        "page": pg["printed"] or pg["file"],
                        "file": pg["file"],
                        "col": ci,
                        "raw": s,
                        "name": find_heads(s)[0][1] if find_heads(s) and find_heads(s)[0][0] == 0 else "",
                    }
                )
    if carry and entries:
        entries[0]["raw"] = carry + entries[0]["raw"]
    for e in entries:
        m = BORN.search(e["raw"])
        e["birth"] = int(m.group(1)) if m else None
        e["death"] = int(m.group(2)) if (m and m.group(2)) else None
    return entries


if __name__ == "__main__":
    files = sorted(BASE.glob("p*.content_list.json"))
    pages = [Path(f) for f in files]
    rows = build(pages)
    print(f"页 {len(pages)}  条目 {len(rows)}  平均 {len(rows)/max(1,len(pages)):.1f}/页")
    bad = [r for r in rows if not r["name"]]
    print(f"无名字段 {len(bad)}")
    from collections import Counter

    per = Counter(r["page"] for r in rows)
    print("每页条目:", dict(sorted(per.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)))
    print("生卒命中", sum(1 for r in rows if r["birth"]), "/", len(rows))
    print("\n前 12 条:")
    for r in rows[:12]:
        print(f"  p{r['page']} {r['name']:<4} {r['birth'] or ''}-{r['death'] or ''}  {r['raw'][:52]}")
    out = BASE / "entries.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", out)
