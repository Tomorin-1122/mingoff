# -*- coding: utf-8 -*-
"""中書省大臣年表解析（试点，2026-10-21）。

输入：MinerU OCR 的 md（_scratch/mineru_nianbiao/out/vol1_zhongshu.md）
输出：src/mingoff/data/vol1_zhongshu_entries.json（提取物，不入公开仓）

版式事实（实测 13 年，PDF 16–29）：
  1. 奇数年（左页）带官职标签：丞相(左/右)、平章政事、丞(左/右)、參知政事；
  2. 偶数年（对页）无标签，只有数据行，行数会变（某官职人多时另起一行）；
  3. 一格内多人并排时，OCR 把名字连在前、注文连在后，**列对应关系已丢失**；
     这类格的注文一律不猜配，标 review。
  4. 1372+1373、1376+1377 各被 OCR 合成一个 table，按年份标题切回两页。

纪律：人名可自动取；注文只在"单人格"且能干净切分时才采用，其余标 review 留原文。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MD = ROOT / "_scratch" / "mineru_nianbiao" / "out" / "vol1_zhongshu.md"
OUT = ROOT / "src" / "mingoff" / "data" / "vol1_zhongshu_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol1_zhongshu_review.json"

OFFICES = ("丞相", "平章政事", "丞", "參知政事")
YEAR_RE = re.compile(r"(洪武[元一二三四五六七八九十]+年)\s*[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s*[(（](\d{4})")
NAME_RE = re.compile(r"([\u4e00-\u9fff]{2,4})(?=[\s\u3000(（]|$)")
MONTH_START = re.compile(r"^(正|閏|臘|[一二三四五六七八九十]{1,2})、")
CJK = re.compile(r"^[\u4e00-\u9fff]{2,4}")


def text_of(cell: str) -> str:
    """去掉 HTML 标签、合并空白（原文里的换行视为分隔）。"""
    t = re.sub(r"<[^>]+>", "", cell)
    t = t.replace("\u3000", " ")
    return re.sub(r"\s+", " ", t).strip()


def split_persons(text: str) -> tuple[list[str], str]:
    """从头切出人名序列，返回 (names, 余下注文)。

    两种形态：
      a) 名字有空格/括号分隔：常遇春 胡廷瑞 廖永忠 李伯昇(丁未年…
      b) 名后直接跟注文：趙庸正、乙亥、四;  → 靠"注文以月令+顿号开头"下刀
    """
    names: list[str] = []
    pos = 0
    while pos < len(text):
        m = NAME_RE.match(text, pos)
        if not m:
            break
        names.append(m.group(1))
        pos = m.end()
        while pos < len(text) and text[pos] in " \u3000":
            pos += 1
    if names:
        return names, text[pos:].strip()

    # b) 无分隔：在第一个"月令+、"之前切
    for i in range(2, min(5, len(text)) + 1):
        head, tail = text[:i], text[i:].lstrip()
        if MONTH_START.match(tail) and CJK.match(head):
            return [head], tail
    # 兜底：取开头 2–3 字（存疑，由调用方标 review）
    m = CJK.match(text)
    return ([m.group(0)] if m else []), text[m.end():].strip() if m else text


def parse_rows(rows: list[list[str]]) -> list[dict]:
    """把一个 table 切成若干"年页"，每页给出 (year, era, 行列表)。"""
    pages: list[dict] = []
    cur: dict | None = None
    for cells in rows:
        joined = " ".join(cells)
        ym = YEAR_RE.search(joined)
        if ym:
            # 年份行本身也可能带数据（如 1369 的年份单独一行）
            cur = {"year": int(ym.group(2)), "era": ym.group(1), "rows": []}
            pages.append(cur)
            continue
        if cur is None:
            continue
        cur["rows"].append([text_of(c) for c in cells])
    return pages


def structure_page(page: dict, fallback_seq: list[tuple[str, str | None]]) -> list[dict]:
    """把一页的行解析成条目。

    fallback_seq：无标签年用的 (office, side) 序列（来自上一个有标签年）。
    """
    out: list[dict] = []
    labelled = any(r and r[0] in OFFICES for r in page["rows"])
    seq_i = 0
    pending_office: str | None = None
    pending_side: str | None = None

    for cells in page["rows"]:
        if not cells:
            continue
        head = cells[0].strip()
        rest = [c for c in cells[1:]]

        if head in OFFICES:
            pending_office = head
            pending_side = None
            # 左/右写在第二格时，本行即该 side 的数据
            if rest and rest[0] in ("左", "右"):
                pending_side = rest[0]
                body = " ".join(rest[1:]).strip()
            else:
                body = " ".join(rest).strip()
        elif head in ("左", "右") and pending_office:
            pending_side = head
            body = " ".join(rest).strip()
        elif not labelled:
            # 对页年：无标签，按序取上一页的官职序列
            if seq_i < len(fallback_seq):
                pending_office, pending_side = fallback_seq[seq_i]
            seq_i += 1
            body = " ".join(c for c in cells if c).strip()
        else:
            # 有标签年的续行（同一官职换行续写）
            body = " ".join(c for c in cells if c).strip()

        if not body:
            continue
        names, note = split_persons(body)
        if not names:
            continue
        multi = len(names) > 1
        for k, name in enumerate(names):
            review = None
            conf = 0.8
            if multi:
                # 多人并排：注文列对应关系已丢失，不猜配
                review = f"多人同格({len(names)}人)，注文列对应丢失"
                conf = 0.5
                this_note = ""
            else:
                this_note = note
                if not note:
                    conf = 0.7
            if not labelled:
                review = (review + "；" if review else "") + "对页年无官职标签，按行序推"
                conf = min(conf, 0.6)
            out.append({
                "year": page["year"],
                "office": pending_office,
                "side": pending_side,
                "person": name,
                "note": this_note,
                "raw": body if not multi else (body if k == 0 else ""),
                "conf": conf,
                "review": review,
            })
    return out


def main() -> int:
    md = MD.read_text(encoding="utf-8")
    tables = re.findall(r"<table>.*?</table>", md, re.S)
    entries: list[dict] = []
    seq: list[tuple[str, str | None]] = []

    for tb in tables:
        rows = [[text_of(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                for r in re.findall(r"<tr>(.*?)</tr>", tb, re.S)]
        for page in parse_rows(rows):
            got = structure_page(page, seq)
            if not got:
                continue
            entries.extend(got)
            # 有标签年更新"官职序列"（供下一对页年用）
            lab = [(e["office"], e["side"]) for e in got if e["office"]]
            if lab and any(r and r[0] in OFFICES for r in page["rows"]):
                seen: list[tuple[str, str | None]] = []
                for item in lab:
                    if item not in seen:
                        seen.append(item)
                seq = seen

    years = sorted({e["year"] for e in entries})
    review = [e for e in entries if e["review"]]
    payload = {
        "meta": {
            "dataset": "中書省大臣年表（试点）",
            "source": "张德信《明代職官年表》册1 正文 1–14（PDF 16–29）；MinerU OCR",
            "year_range": [min(years), max(years)] if years else None,
            "stats": {
                "entries": len(entries),
                "years": len(years),
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "review": len(review),
                "conf_avg": round(sum(e["conf"] for e in entries) / len(entries), 3) if entries else None,
            },
            "note": "多人同格注文列对应已丢失，不猜配；对页年行序可靠度较低。均需回原书页核。",
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"条目 {len(entries)}；年份 {len(years)}（{min(years)}–{max(years)}）")
    print(f"有人名无注文 {sum(1 for e in entries if not e['note'])}；待核 {len(review)}")
    print(f"→ {OUT}")
    print(f"→ {REVIEW}")
    # 逐年概览
    for y in years:
        es = [e for e in entries if e["year"] == y]
        tags = " ".join(f"{e['office']}{('·'+e['side']) if e['side'] else ''}:{e['person']}" for e in es)
        print(f"  {y} ({len(es)}) {tags[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
