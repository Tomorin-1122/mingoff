# -*- coding: utf-8 -*-
"""部院侍郎年表 OCR 解析（零模型成本，纯文本处理）。

输入：MinerU OCR md（_scratch/mineru_nianbiao/out/vol1_shilang_jingshi_a/b.md）
输出：src/mingoff/data/vol1_shilang_entries.json（提取物）
      src/mingoff/data/vol1_shilang_review.json（可疑行，供人工核）

策略（2026-10-22）：
  1. 两遍法：先用"注文以月令+顿号开头"切出所有人名，短名（2-4 字）入词典；
  2. 再用词典对长串（多人连写）做最长匹配切分；
  3. 切不干净、注文段数对不上人名的，一律标 review，不猜配。
版式：一行一衙；格内多人时 OCR 常把名字连写、注文连写 —— 这正是 review 的来源。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SRC = [ROOT / "_scratch/mineru_nianbiao/out/vol1_shilang_jingshi_a.md",
       ROOT / "_scratch/mineru_nianbiao/out/vol1_shilang_jingshi_b.md"]
OUT = ROOT / "src" / "mingoff" / "data" / "vol1_shilang_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol1_shilang_review.json"

OFFICES = ("吏部", "戶部", "禮部", "兵部", "刑部", "工部", "都察院", "御史臺中丞",
           "御史臺", "御史府", "易州山廠提督", "總倉場", "總督京儲", "總督倉場")
YEAR_RE = re.compile(r"(洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎)"
                     r"([元一二三四五六七八九十]+)年\s*[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s*[(（](\d{4})")
MONTH = re.compile(r"(?:正|閏|臘|[一二三四五六七八九十]{1,2})、")
TAG = re.compile(r"[（(]([左右文])[）)]")
CJK_HEAD = re.compile(r"^[\u4e00-\u9fff]{2,8}")


def plain(cell: str) -> str:
    t = re.sub(r"<[^>]+>", "", cell)
    return re.sub(r"\s+", " ", t.replace("\u3000", " ")).strip()


def cut(text: str) -> tuple[str, str]:
    """切出人名部分与注文部分（人名部分可能含多人连写）。"""
    m = MONTH.search(text)
    if m:
        return text[:m.start()].strip(), text[m.start():].strip()
    for kw in ("是年", "本年", "後無考", "無考"):
        i = text.find(kw)
        if i > 0:
            return text[:i].strip(), text[i:].strip()
    return text.strip(), ""


def split_names(head: str, pool: set[str]) -> tuple[list[str], str]:
    """把可能连写的人名串切成若干人名；返回 (names, tags_tail)。"""
    tags = []
    names: list[str] = []
    s = head
    while s:
        m = TAG.match(s)
        if m:
            tags.append(m.group(1))
            s = s[m.end():]
            continue
        hit = None
        for L in (4, 3, 2):
            cand = s[:L]
            if cand in pool:
                hit = cand
                break
        if not hit:
            m = re.match(r"^[\u4e00-\u9fff]{2,4}", s)
            if not m:
                break
            hit = m.group(0)
            # 没有词典命中：只能当单人，剩余串继续（多半是粘着的下一个人名）
            names.append(hit)
            s = s[m.end():]
            continue
        names.append(hit)
        s = s[len(hit):]
    return names, "".join(tags)


def main() -> int:
    text = "".join(p.read_text(encoding="utf-8") for p in SRC if p.exists())
    tables = re.findall(r"<table>.*?</table>", text, re.S)

    # ── 第一遍：收集可靠短名（2–4 字且紧跟注文）──
    pool: Counter = Counter()
    for tb in tables:
        for tr in re.findall(r"<tr>(.*?)</tr>", tb, re.S):
            tds = [plain(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            for td in tds[1:]:
                if not td:
                    continue
                head, note = cut(td)
                head = TAG.sub("", head)
                if note and 2 <= len(head) <= 4 and CJK_HEAD.match(head):
                    pool[head] += 1
    pool = {k for k, v in pool.items() if v >= 1}

    entries, review = [], []
    cur_year = cur_era = None
    # 衙署行序：跨页沿用上一张有标签页的顺序（侍郎表行序多年稳定）
    seq: list[str] = list(OFFICES[:6]) + ["都察院"]

    for tb in tables:
        rows = re.findall(r"<tr>(.*?)</tr>", tb, re.S)
        page_seq: list[str] = []
        row_idx = 0
        for tr in rows:
            tds = [plain(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not tds:
                continue
            ym = YEAR_RE.search(" ".join(tds))
            if ym:
                cur_year, cur_era = int(ym.group(3)), ym.group(1) + ym.group(2) + "年"
                continue
            if cur_year is None:
                continue

            has_office = any(t in OFFICES for t in tds)
            if has_office:
                # 有标签页：首格（或其中一格）是衙署名
                oi = next(i for i, t in enumerate(tds) if t in OFFICES)
                office = tds[oi]
                body = tds[oi + 1:]
                page_seq.append(office)
            else:
                # 对页年：整行都是数据，按上一页衙署序列逐行对应
                office = seq[row_idx] if row_idx < len(seq) else None
                row_idx += 1
                body = tds
                if office is None:
                    review.append({"year": cur_year, "kind": "row-order",
                                   "raw": " | ".join(tds)[:120],
                                   "why": "对页年行序超出已知衙署序列"})
                    continue

            for td in body:
                if not td:
                    continue
                head, note = cut(td)
                names, tags = split_names(head, pool)
                if not names:
                    continue
                if len(names) > 1:
                    # 多人连写：人名可切，但注文无法分到各人 → 整体标 review
                    review.append({"year": cur_year, "office": office, "kind": "multi-name",
                                   "names": names, "note": note,
                                   "why": f"格内 {len(names)} 人连写，注文未分派"})
                    for n in names:
                        entries.append({"year": cur_year, "era": cur_era, "office": office,
                                        "person": n, "tag": tags or None, "note": "",
                                        "src": "ocr", "review": "多人同格，注文待核"})
                else:
                    entries.append({"year": cur_year, "era": cur_era, "office": office,
                                    "person": names[0], "tag": tags or None, "note": note,
                                    "src": "ocr", "review": None})

        if page_seq:
            seq = page_seq

    for i, e in enumerate(entries):
        e.pop("_rowid", None)
    years = sorted({e["year"] for e in entries})
    payload = {
        "meta": {
            "dataset": "部院侍郎年表（京師）· OCR 解析",
            "source": "MinerU OCR（册1 正文 681–980）",
            "year_range": [min(years), max(years)] if years else None,
            "stats": {
                "entries": len(entries), "years": len(years),
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "review_rows": len(review),
                "name_pool": len(pool),
            },
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload["meta"]["stats"], ensure_ascii=False, indent=1))
    print(f"年份 {min(years)}–{max(years)}")
    print(f"→ {OUT}")
    print(f"→ {REVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
