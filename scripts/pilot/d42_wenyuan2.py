"""1547 刑部行结构调整：聞淵 该年在刑部（原书刑部行第一人），此前修复删错了行。

原书 p582（PDF597）刑部行 = 聞淵 / 屠僑 / 喻茂堅（OCR 原文可证）。
D42 第一轮把 (1547,聞淵,刑部) 误删——BOOK_REMOVE 写错了，应当删的是
都察院行的聞淵（都察院行只有 宋景/王以旂/屠僑，無聞淵）……复核后其实都察院行也無聞淵。
真实情况：聞淵该年記在刑部行（「正、庚辰、廿七,改吏尚」），
所以 BOOK_REMOVE 里 (1547,聞淵,刑部) 是误删，必须撤销；
同时 (1547,聞淵,吏部) 的吏部条来自修复层「restored」——吏部行確有聞淵（「刑尚改」），
即聞淵 1547 同年跨两衙记载（刑部→吏部 改任），两行都真实。
本脚本检查两条是否都存在（只读）。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
rows = [r for r in e if r["year"] == 1547 and r["person"] == "聞淵"]
for r in rows:
    print(f"{r['office']}: {r['note'][:40]!r} status={r.get('note_status')}")
