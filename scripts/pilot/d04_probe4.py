"""D-04 剩余人名差异核对：列出「数据有、原书该衙未列」的人，逐条附原书页。

只读：不改任何数据。输出写入 _d04_names.txt（UTF-8），PowerShell 回显中文不可靠。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

# 原书转写（表头明确年）：年份 -> {衙署: [人名]}
BOOK = {
    1548: {"兵部": ["趙廷瑞"], "刑部": ["喻茂堅"]},
    1558: {"刑部": ["賈應春"], "工部": ["歐陽必進", "雷禮"], "總督倉場": ["高燿"]},
}
# 无标签年：按 8 行行序（吏/戶/禮/兵/刑/工/總督倉場 或 京儲/都察院）
BOOK_ORDERED = {
    1550: ["夏邦謨", "潘潢/李士翱/孫應奎", "徐階", "丁汝夔/王邦瑞/翁萬達",
           "劉訒/李士翱/顧應祥", "李士翱/胡松", "陳經/孫應奎/端廷赦", "屠僑"],
    1552: ["萬鏜", "孫應奎/韓士英/方鈍", "徐階/歐陽德", "趙錦/翁萬達",
           "應大猷/何鰲", "歐陽必進", "孫禱/余胤緒", "屠僑"],
    1554: ["李默", "方鈍", "歐陽德/王用賓", "聶豹", "何鰲",
           "歐陽必進/吳鵬", "楊行中/盧紳", "屠僑"],
    1556: ["李默/李本/吳鵬", "方鈍", "王用賓/吳山", "楊博/許論",
           "何鰲/歐陽必進", "吳鵬/趙文華", "盧紳/高燿", "周延"],
}
ORDER8 = ["吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督倉場", "都察院"]


def names(year, office):
    return sorted(r["person"] for r in rows if r["year"] == year and r["office"] == office)


out = ["# D-04 人名差异（数据 vs 原书，只读）", ""]
out.append("## 一、表头明确年")
for year, spec in BOOK.items():
    out.append(f"### {year}")
    for off, book_names in spec.items():
        got = names(year, off)
        extra = sorted(set(got) - set(book_names))
        out.append(f"- {off}：原书 {'/'.join(book_names)}；数据 {'/'.join(got) or '（无）'}；"
                   f"**数据多** {extra or '无'}；数据缺 {sorted(set(book_names) - set(got)) or '无'}")

out.append("")
out.append("## 二、无标签年（按行序）")
for year, order in BOOK_ORDERED.items():
    out.append(f"### {year}（对页续行，行政 8 行）")
    for i, book_row in enumerate(order):
        year_off = ORDER8[i]
        if year_off == "總督倉場":
            for cand in ("總督倉場", "總督京儲"):
                got = names(year, cand)
                if got:
                    extra = sorted(set(got) - set(book_row.split("/")))
                    out.append(f"  第{i + 1}行 原书 {book_row}；数据 {cand} {got}；数据多 {extra or '无'}")
        else:
            got = names(year, year_off)
            extra = sorted(set(got) - set(book_row.split("/")))
            out.append(f"  第{i + 1}行 {year_off} 原书 {book_row}；数据 {got or '（无）'}；数据多 {extra or '无'}")

(ROOT / "_d04_names.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
