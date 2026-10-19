"""D42 收尾核对：四个修正年的最终状态 vs 原书（只读，输出 UTF-8）。"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))

BOOK = {
    1546: {"吏部": ["唐龍", "周用"], "戶部": ["王杲"], "禮部": ["費寀"],
           "兵部": ["路迎", "陳經"], "刑部": ["聞淵"], "工部": ["甘爲霖", "王以旂"],
           "總督京儲": [], "都察院": ["周用", "宋景"]},
    1547: {"吏部": ["周用", "聞淵"], "戶部": ["王杲", "夏邦謨"], "禮部": ["費寀"],
           "兵部": ["陳經", "王以旂"], "刑部": ["聞淵", "屠僑", "喻茂堅"],
           "工部": ["王以旂", "文明"], "總督京儲": ["王暐", "劉儲秀"],
           "都察院": ["宋景", "王以旂", "屠僑"]},
    1548: {"吏部": ["聞淵", "夏邦謨"], "戶部": ["夏邦謨"], "禮部": ["費寀", "孫承恩"],
           "兵部": ["王以旂", "劉儲秀", "趙廷瑞"], "刑部": ["喻茂堅"], "工部": ["文明"],
           "總督京儲": ["劉儲秀", "張潤", "李士翱"], "都察院": ["屠僑"]},
    1558: {"吏部": ["吳鵬"], "戶部": ["方鈍", "賈應春"], "禮部": ["吳山"],
           "兵部": ["許論", "楊博"], "刑部": ["賈應春", "鄭曉"],
           "工部": ["歐陽必進", "雷禮"], "總督倉場": ["高燿"], "都察院": ["周延"]},
}

lines, ok = [], 0
total = 0
for year, spec in BOOK.items():
    lines.append(f"## {year}")
    for off, book_names in sorted(spec.items()):
        got = sorted(r["person"] for r in e if r["year"] == year and r["office"] == off)
        same = sorted(got) == sorted(book_names)
        ok += same
        total += 1
        mark = "✅" if same else "⚠"
        lines.append(f"  {mark} {off}: 原书 {'/'.join(book_names) or '（空）'}；数据 {'/'.join(got) or '（空）'}")
lines.append(f"\n== 一致 {ok}/{total} ==")
(ROOT / "docs/evidence/d04/_d42_final.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
