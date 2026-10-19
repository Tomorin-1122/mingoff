"""D-11：对页续行对齐——把对页无标签年的行与相邻带标签页合并重排，产出修正建议（只读）。

方法：
  1. 从 OCR markdown 按年份头切表，每表抽「行」（<tr>），识别带标签行（首格=标签词）；
  2. 对无标签年：用「该年所有人名 → 已知 (人,衙) 历史」先给人名锚定；
  3. 剩余行按与邻页标签序列的对齐关系给出「建议 office」+ 置信标记；
  4. 与 vol1_buyuan_entries_v2 现状比对，输出差异清单供人工核（不改数据）。

产出：
  src/mingoff/data/vol1_buyuan_d11_review.json  —— 逐行建议
  docs/evidence/d11/_d11_summary.txt            —— 人读摘要
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
SCR = ROOT.parent / "_scratch" / "mineru_buyuan"
DATA = ROOT / "src" / "mingoff" / "data"

LABELS = {"吏部", "戶部", "户部", "禮部", "礼部", "兵部", "刑部", "工部",
          "御史臺", "御史台", "御史府", "都察院",
          "總督京儲", "總倉場", "總督倉場", "督倉場", "總會場"}
# 原书标签 → 数据 office（D41 字面口径）
LABEL2OFFICE = {
    "吏部": "吏部", "戶部": "戶部", "户部": "戶部", "禮部": "禮部", "礼部": "禮部",
    "兵部": "兵部", "刑部": "刑部", "工部": "工部",
    "御史臺": "御史臺", "御史台": "御史臺", "御史府": "御史府", "都察院": "都察院",
    "總督京儲": "總督京儲", "總倉場": "總倉場", "總督倉場": "總督倉場",
    "督倉場": "總督倉場", "總會場": "總倉場",
}
NAME_RE = re.compile(r"^[\u4e00-\u9fff]{2,4}(（[^）]{1,6}）)?$")


def load_tables():
    text = ((SCR / "vol1_buyuan_a.md").read_text(encoding="utf-8")
            + (SCR / "vol1_buyuan_b.md").read_text(encoding="utf-8"))
    # 按年份标记切
    out = {}  # year -> list of rows; row = {"labeled": office or None, "names": [...]}
    for m in re.finditer(r"[（(](\d{4})[）)]", text):
        year = int(m.group(1))
        seg = text[m.end(): text.find(f"({year + 1})", m.end()) if text.find(f"({year + 1})", m.end()) > 0 else m.end() + 9000]
        rows = []
        for tr in re.finditer(r"<tr>(.*?)</tr>", seg, re.S):
            cells = [re.sub(r"<[^>]+>", "", c).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), re.S)]
            cells = [c for c in cells if c]
            if not cells:
                continue
            first = cells[0]
            labeled = None
            if first in LABELS:
                labeled = LABEL2OFFICE[first]
                cells = cells[1:]
            names = [c for c in cells if NAME_RE.match(c)]
            rows.append({"labeled": labeled, "names": names, "cells": cells})
        if rows and year not in out:
            out[year] = rows
    return out


def main():
    tables = load_tables()
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
    # 人名 → 年份集合 → 衙署历史（来自已有数据的带标签年 + 已确认的行）
    p_offices = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in entries:
        p_offices[r["person"]][r["office"]].append(r["year"])

    review = []
    unlabeled_years = []
    for year, rows in sorted(tables.items()):
        labeled_rows = [r for r in rows if r["labeled"]]
        if labeled_rows:
            continue  # 带标签年解析层已可靠（D40 逐页验证的 11 年也都属这类）
        unlabeled_years.append(year)
        # 邻页标签序列
        neighbor = None
        for d in (1, -1):
            t = tables.get(year + d)
            if t and [r for r in t if r["labeled"]]:
                neighbor = ([r["labeled"] for r in t if r["labeled"]], d)
                break
        seq = neighbor[0] if neighbor else []
        for i, row in enumerate(rows):
            # 人名锚定
            anchored = collections.Counter()
            for n in row["names"]:
                for off, ys in p_offices.get(n, {}).items():
                    if any(abs(y - year) <= 4 for y in ys):
                        anchored[off] += 1
            sugg, conf, how = None, 0.0, ""
            if anchored:
                off, n = anchored.most_common(1)[0]
                sugg, conf, how = off, n / sum(anchored.values()), "人名锚"
            elif seq and i < len(seq):
                sugg, conf, how = seq[i], 0.3, "行序兜底"
            review.append({
                "year": year, "row": i, "names": row["names"],
                "cells_head": [c[:24] for c in row["cells"][:3]],
                "suggest_office": sugg, "conf": round(conf, 2), "how": how,
                "neighbor": f"{neighbor[1]:+d}" if neighbor else None,
            })

    out = {"meta": {"unlabeled_years": unlabeled_years, "rows": len(review),
                    "note": "D11 第一轮：只出建议，不改数据；conf<0.5 的行序兜底必须回原书页核"},
           "rows": review}
    (DATA / "vol1_buyuan_d11_review.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# D-11 对页续行对齐（第一轮，只读）", "",
             f"对页无标签年：{len(unlabeled_years)} 个：{unlabeled_years}", "",
             "| 年 | 行 | 人名 | 建议 office | 置信 | 依据 |", "|---|---|---|---|---|---|"]
    for r in review:
        lines.append(f"| {r['year']} | {r['row']} | {'/'.join(r['names']) or '（无名）'} "
                     f"| {r['suggest_office'] or '？'} | {r['conf']} | {r['how']} |")
    (ROOT / "docs/evidence/d11/_d11_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"unlabeled years: {len(unlabeled_years)}; rows: {len(review)}")


if __name__ == "__main__":
    main()
