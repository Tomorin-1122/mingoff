"""D-04 全量核对（只读）：把已逐页转写的年份与原书比对，输出风险分级。

分级口径：
  P0 结构性 — 整行/整人放错衙署、或整行被丢（会导致「某人在任某衙」错/缺）
  P1 人名     — 单个人名异写（形近字）或错挂到另一衙
  P2 缺行     — 原书该衙有人、数据整行缺失
  P3 非表内   — 行的标签不在本表（如 1546 页「司属末行」= 司属年表的续页），暂不判
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

# 原书逐页转写：只有「表头年」可确定行→衙；无标签年单独标
BOOK = {
    1545: (595, "表头", {"吏部": ["熊浹", "唐龍"], "戶部": ["王杲"], "禮部": ["費寀"],
                        "兵部": ["戴金", "唐龍", "路迎"], "刑部": ["聞淵"], "工部": ["甘爲霖"],
                        "總督京儲": ["陳經"], "都察院": ["周用"]}),
    1546: (596, "表头", {"吏部": ["唐龍", "周用"], "戶部": ["王杲"], "禮部": ["費寀"],
                        "兵部": ["路迎", "陳經"], "刑部": ["聞淵"], "工部": ["甘爲霖", "王以旂"],
                        "司属末行(不判)": ["陳經", "張珩", "王暐"], "都察院": ["周用", "宋景"]}),
    1547: (597, "表头", {"吏部": ["周用", "聞淵"], "戶部": ["王杲", "夏邦謨"], "禮部": ["費寀"],
                        "兵部": ["陳經", "王以旂"], "刑部": ["聞淵", "屠僑", "喻茂堅"],
                        "工部": ["王以旂", "文明"], "總督京儲": ["王暐", "劉儲秀"],
                        "都察院": ["宋景", "王以旂", "屠僑"]}),
    1548: (598, "表头", {"吏部": ["聞淵", "夏邦謨"], "戶部": ["夏邦謨"], "禮部": ["費寀", "孫承恩"],
                        "兵部": ["王以旂", "劉儲秀", "趙廷瑞"], "刑部": ["喻茂堅"], "工部": ["文明"],
                        "總督京儲": ["劉儲秀", "張潤", "李士翱"], "都察院": ["屠僑"]}),
    1557: (607, "表头", {"吏部": ["吳鵬"], "戶部": ["方鈍"], "禮部": ["吳山"], "兵部": ["許論"],
                        "刑部": ["歐陽必進", "賈應春"], "工部": ["趙文華", "歐陽必進"],
                        "總督倉場": ["高燿"], "都察院": ["周延"]}),
    1558: (608, "表头", {"吏部": ["吳鵬"], "戶部": ["方鈍", "賈應春"], "禮部": ["吳山"],
                        "兵部": ["許論", "楊博"], "刑部": ["賈應春", "鄭曉"],
                        "工部": ["歐陽必進", "雷禮"], "總督倉場": ["高燿"], "都察院": ["周延"]}),
}
# 无标签年（对页续行）：按 8 行行序
BOOK_ORDERED = {
    1550: (600, ["夏邦謨", "潘潢/李士翱/孫應奎", "徐階", "丁汝夔/王邦瑞/翁萬達",
                 "劉訒/李士翱/顧應祥", "李士翱/胡松", "陳經/孫應奎/端廷赦", "屠僑"]),
    1552: (602, ["萬鏜", "孫應奎/韓士英/方鈍", "徐階/歐陽德", "趙錦/翁萬達",
                 "應大猷/何鰲", "歐陽必進", "孫禱/余胤緒", "屠僑"]),
    1554: (604, ["李默", "方鈍", "歐陽德/王用賓", "聶豹", "何鰲",
                 "歐陽必進/吳鵬", "楊行中/盧紳", "屠僑"]),
    1556: (606, ["李默/李本/吳鵬", "方鈍", "王用賓/吳山", "楊博/許論",
                 "何鰲/歐陽必進", "吳鵬/趙文華", "盧紳/高燿", "周延"]),
}
ORDER8 = ["吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督京儲", "都察院"]
ALIAS = {"萬鎧": "萬鏜", "范鐸": "范鐔"}  # 数据侧异写 → 原书正字


def norm(n):
    return ALIAS.get(n, n)


def data_names(year, office):
    return sorted(norm(r["person"]) for r in rows if r["year"] == year and r["office"] == office)


def data_names_any(year, offices):
    return sorted(norm(r["person"]) for r in rows if r["year"] == year and r["office"] in offices)


lines, risks = [], []
for year, (pdf, _kind, spec) in BOOK.items():
    lines.append(f"## {year}（p{year - 965} / PDF {pdf}）")
    for off, book_names in spec.items():
        if off.startswith("司属末行"):
            lines.append(f"  [不判] {off}: 原书 {'/'.join(book_names)}（司属年表续页，非本表行）")
            continue
        got = data_names(year, off)
        extra = sorted(set(got) - set(book_names))
        miss = sorted(set(book_names) - set(got))
        mark = "✅" if not extra and not miss else "⚠"
        lines.append(f"  {mark} {off}: 原书 {'/'.join(book_names)}；数据 {'/'.join(got)}"
                     f"；多 {extra or '无'}；缺 {miss or '无'}")
        if extra or miss:
            risks.append((year, off, extra, miss))

lines.append("")
lines.append("## 无标签年（对页续行）")
for year, (pdf, order) in BOOK_ORDERED.items():
    lines.append(f"### {year}（PDF {pdf}，8 行不过表头）")
    all_year = {r["person"] for r in rows if r["year"] == year}
    for i, book_row in enumerate(order):
        book_set = set(book_row.split("/"))
        cand = "總督京儲" if i == 6 else ORDER8[i]
        if i == 6:
            # 1550/1552 表头作「總督倉場」的可能，两个都看
            cands = ["總督京儲", "總督倉場"]
        else:
            cands = [ORDER8[i]]
        got = data_names_any(year, cands)
        # 对页年的判断只做「该年此衙有没有这个人」的粗检
        absent = [n for n in book_set if n not in all_year]
        lines.append(f"  第{i + 1}行 {ORDER8[i]}: 原书 {book_row}；数据({'/'.join(cands)}) {got or '（无）'}"
                     f"；{'本年全表都找不到 ' + str(absent) if absent else ''}")

text = "\n".join(lines)
(ROOT / "_d04_full.txt").write_text(text, encoding="utf-8")
print("written; risk rows:", len(risks))
