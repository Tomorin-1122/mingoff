"""D-04 其他衙署的姓名差异探针（泛用：只列出「数据有、原书该衙未列」的人，需人工看图判断是否漏行）。

本脚本只核对**表头明确**的年份；无标签年为对页续行，行归属需靠行序+锚点，另在报告里说明。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"

entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

# 已核过、不在本轮范围的年份
DONE = {1549, 1550, 1551, 1552, 1553, 1554, 1555, 1556, 1557, 1396, 1397, 1398, 1399, 1400, 1401, 1402}

# 从原书逐页转写的「表头年」人名（只转写与本核对相关的衙署）
BOOK = {
    1558: {"pdf": 608, "page": 593, "表头": {"刑部": ["歐陽必進"], "總督倉場": ["高燿"]}},
    1548: {"pdf": 598, "page": 583, "表头": {"兵部": ["趙廷瑞"], "刑部": ["喻茂堅"]}},
}


def names(year, office):
    return sorted(r["person"] for r in rows if r["year"] == year and r["office"] == office)


def main():
    for year, spec in BOOK.items():
        out = [f"== {year} p{spec['page']} PDF{spec['pdf']} =="]
        for off, book_names in spec["表头"].items():
            got = names(year, off)
            out.append(f"  原书「{off}」= {'/'.join(book_names)}")
            out.append(f"  数据「{off}」= {'/'.join(got) or '（无）'}")
            out.append(f"  数据多：{sorted(set(got) - set(book_names))}  数据缺：{sorted(set(book_names) - set(got))}")
        print("\n".join(out))


if __name__ == "__main__":
    main()
