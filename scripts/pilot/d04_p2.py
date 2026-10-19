"""D-04 工部/刑部 表头年核对（只读）。

对每个「表头明确年」，把原书该衙列出的人与数据比对，输出「数据多/数据缺」。
原书转写只取与本核对相关的衙署，人名逐字照录繁体。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "mingoff" / "data"
entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = entries if isinstance(entries, list) else entries["entries"]

BOOK = {
    # 书页 : (pdf 页, {衙署: [人名]})
    581: (596, {"兵部": ["路迎", "陳經"], "司属末行": ["陳經", "張珩", "王暐"],
               "都察院": ["周用", "宋景"]}),
    583: (598, {"兵部": ["王以旂", "劉儲秀", "趙廷瑞"], "刑部": ["喻茂堅"],
               "總督京儲": ["劉儲秀", "張潤", "李士翱"]}),
    585: (600, {"_无标签": ["夏邦謨", "潘潢/李士翱/孫應奎", "徐階", "丁汝夔/王邦瑞/翁萬達",
                          "劉訒/李士翱/顧應祥", "李士翱/胡松", "陳經/孫應奎/端廷赦", "屠僑"]}),
    586: (601, {"刑部": ["顧應祥", "萬鏜", "應大猷"], "總督倉場": ["端廷赦", "張經", "孫禱"]}),
    589: (604, {"_无标签": ["李默", "方鈍", "歐陽德/王用賓", "聶豹", "何鰲",
                          "歐陽必進/吳鵬", "楊行中/盧紳", "屠僑"]}),
    590: (605, {"刑部": ["何鰲"], "工部": ["吳鵬"], "總督京儲": ["盧紳"]}),
    591: (606, {"_无标签": ["李默/李本/吳鵬", "方鈍", "王用賓/吳山", "楊博/許論",
                          "何鰲/歐陽必進", "吳鵬/趙文華", "盧紳/高燿", "周延"]}),
    592: (607, {"刑部": ["歐陽必進", "賈應春"], "工部": ["歐陽必進", "趙文華"]}),
    593: (608, {"刑部": ["賈應春", "鄭曉"], "工部": ["歐陽必進", "雷禮"], "總督倉場": ["高燿"]}),
}
ORDER8 = ["吏部", "戶部", "禮部", "兵部", "刑部", "工部", "總督倉場", "都察院"]


def names(year, office):
    return sorted(r["person"].translate(str.maketrans("萬鎧范鐔", "萬鏜范鐸")) if False else r["person"]
                  for r in rows if r["year"] == year and r["office"] == office)


out = []
for page, (pdf, spec) in BOOK.items():
    year = page + 965  # 书页 581 → 1546，即 年份 = 书页 − 965（仅限本段）
    year = 1546 + (page - 581)
    out.append(f"## {year}（书页 p{page} / PDF {pdf}）")
    for off, book_names in spec.items():
        if off == "_无标签":
            out.append("  （无标签年，按行序）")
            for i, r_ in enumerate(book_names):
                o = ORDER8[i]
                got = names(year, "總督京儲") or names(year, "總督倉場") if i == 6 else names(year, o)
                extra = sorted(set(got) - set(r_.split("/")))
                out.append(f"    第{i + 1}行 {o}: 原书 {r_}；数据 {got}；数据多 {extra or '无'}")
            continue
        got = names(year, off)
        extra = sorted(set(got) - set(book_names))
        miss = sorted(set(book_names) - set(got))
        mark = "⚠" if (extra and off != "司属末行") else " "
        out.append(f"  {mark} {off}: 原书 {'/'.join(book_names)}；数据 {got or '（无）'}；"
                   f"数据多 {extra or '无'}；数据缺 {miss or '无'}")

(ROOT / "_d04_p2.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out).encode("ascii", "replace").decode())
