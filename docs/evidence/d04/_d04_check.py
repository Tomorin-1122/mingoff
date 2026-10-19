"""D-04 表头核对：从原书 PDF 逐页核对衙署归属，只出证据与差异，不改任何数据。

用法：
  python _d04_check.py            # 打印核对结论
产出（只读，不写数据）：
  _d04_check.txt                  # 人可读核对表
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"

entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]
pages = json.loads((DATA / "vol1_buyuan_pages.json").read_text(encoding="utf-8"))


def names(year: int, office: str) -> list[str]:
    return sorted(r["person"] for r in rows if r["year"] == year and r["office"] == office)


# ---------------------------------------------------------------- 原书页转写
# 只转写与本核对相关的人/衙；人名逐字照录（繁体），注文省略，用 … 表示。
# 依据：docs/evidence/d04/pdf{599..607}.png，书页 = PDF − 15。
BOOK = {
    1549: {"pdf": 599, "page": 584, "表头": {"吏部": ["聞淵", "夏邦謨"],
                                           "戶部": ["夏邦謨", "潘潢"],
                                           "禮部": ["孫承恩", "徐階"],
                                           "兵部": ["趙廷瑞", "范鐔", "翁萬達", "丁汝夔"],
                                           "刑部": ["喻茂堅", "劉訒"],
                                           "工部": ["文明", "李士翱"],
                                           "總督京儲": ["李士翱"],
                                           "都察院": ["屠僑"]}},
    1550: {"pdf": 600, "page": 585, "无标签列": True,
           "行序": [["夏邦謨"], ["潘潢", "李士翱", "孫應奎"], ["徐階"],
                    ["丁汝夔", "王邦瑞", "翁萬達"], ["劉訒", "李士翱", "顧應祥"],
                    ["李士翱", "胡松"], ["陳經", "孫應奎", "端廷赦"], ["屠僑"]]},
    1551: {"pdf": 601, "page": 586, "表头": {"吏部": ["夏邦謨", "李默", "萬鏜"],
                                           "戶部": ["孫應奎"],
                                           "禮部": ["徐階"],
                                           "兵部": ["王邦瑞", "趙錦", "史道"],
                                           "刑部": ["顧應祥", "萬鏜", "應大猷"],
                                           "工部": ["胡松", "歐陽必進"],
                                           "總督倉場": ["端廷赦", "張經", "孫禱"],
                                           "都察院": ["屠僑"]}},
    1552: {"pdf": 602, "page": 587, "无标签列": True,
           "行序": [["萬鏜"], ["孫應奎", "韓士英", "方鈍"], ["徐階", "歐陽德"],
                    ["趙錦", "翁萬達"], ["應大猷", "何鰲"], ["歐陽必進"],
                    ["孫禱", "余胤緒"], ["屠僑"]]},
    1553: {"pdf": 603, "page": 588, "表头": {"吏部": ["萬鏜", "李默"],
                                           "戶部": ["方鈍"], "禮部": ["歐陽德"],
                                           "兵部": ["聶豹"], "刑部": ["何鰲"],
                                           "工部": ["歐陽必進"],
                                           "總督京儲": ["孫禱", "楊行中"],
                                           "都察院": ["屠僑"]}},
    1554: {"pdf": 604, "page": 589, "无标签列": True,
           "行序": [["李默"], ["方鈍"], ["歐陽德", "王用賓"], ["聶豹"], ["何鰲"],
                    ["歐陽必進", "吳鵬"], ["楊行中", "盧紳"], ["屠僑"]]},
    1555: {"pdf": 605, "page": 590, "表头": {"吏部": ["李默"], "戶部": ["方鈍"],
                                           "禮部": ["王用賓"], "兵部": ["聶豹", "楊博"],
                                           "刑部": ["何鰲"], "工部": ["吳鵬"],
                                           "總督京儲": ["盧紳"],
                                           "都察院": ["屠僑", "周延"]}},
    1556: {"pdf": 606, "page": 591, "无标签列": True,
           "行序": [["李默", "李本", "吳鵬"], ["方鈍"], ["王用賓", "吳山"],
                    ["楊博", "許論"], ["何鰲", "歐陽必進"], ["吳鵬", "趙文華"],
                    ["盧紳", "高燿"], ["周延"]]},
    1557: {"pdf": 607, "page": 592, "表头": {"吏部": ["吳鵬"], "戶部": ["方鈍"],
                                           "禮部": ["吳山"], "兵部": ["許論"],
                                           "刑部": ["歐陽必進", "賈應春"],
                                           "工部": ["趙文華", "歐陽必進"],
                                           "總會場": ["高燿"], "都察院": ["周延"]}},
}

# 洪武三十一年 / 建文三页
BOOK_EARLY = {
    1397: {"pdf": 446, "page": 431, "表头": {"工部": ["孫顯", "嚴震直"],
                                          "都察院": ["鄧文鏗", "楊靖", "嚴震直"]}},
    1398: {"pdf": 447, "page": 432, "表头": {"刑部": ["夏恕", "暴昭"],
                                          "御史臺(御史大夫)": ["暴昭"]}},
    1399: {"pdf": 448, "page": 433, "表头": {"刑部": ["暴昭", "侯泰"],
                                          "御史府(御史大夫)": ["景清", "練子寧"]}},
    1400: {"pdf": 449, "page": 434, "表头": {"刑部": ["暴昭", "侯泰"],
                                          "御史府(御史大夫)": ["景清", "練子寧"]}},
}


def main() -> None:
    out: list[str] = []
    out.append("# D-04 表头核对（只读）\n")
    out.append("## A. 1550–1557 衙署归属\n")
    # 无标签年的行序→衙序映射（按固定行序推断，并给出依据）
    OFFICE_ORDER = ["吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督京儲", "總督倉場", "都察院"]
    for year, spec in BOOK.items():
        if "表头" in spec:
            for off, book_names in spec["表头"].items():
                off_key = "總督倉場" if off == "總會場" else off
                got = names(year, off_key)
                missing = [n for n in book_names if n not in got]
                extra = [n for n in got if n not in book_names]
                diff = []
                if missing:
                    diff.append(f"数据缺 {missing}")
                if extra:
                    diff.append(f"数据多 {extra}（原书未列）")
                status = "一致" if not diff else "；".join(diff)
                out.append(f"{year} p{spec['page']} 表头「{off}」→ 数据 {off_key}：{status}")
        else:
            out.append(f"{year} p{spec['page']} 无标签列（对页），原书行序：")
            for i, row_names in enumerate(spec["行序"]):
                out.append(f"    第{i + 1}行 {'/'.join(row_names)}")
    out.append("\n## B. 御史系列（1397–1400）\n")
    for year, spec in BOOK_EARLY.items():
        for off, book_names in spec["表头"].items():
            off_key = "御史臺" if off.startswith("御史臺") else ("御史府" if off.startswith("御史府") else off)
            got = names(year, off_key)
            missing = [n for n in book_names if n not in got]
            out.append(f"{year} p{spec['page']} 原书「{off}」= {'/'.join(book_names)}；"
                       f"数据 {off_key} = {'/'.join(got) or '（无）'}；"
                       f"{'一致' if not missing else '数据缺 ' + str(missing)}")
    text = "\n".join(out)
    (ROOT / "_d04_check.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
