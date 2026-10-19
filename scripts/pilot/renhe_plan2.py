"""人工核验 6 条：修改方案（D45）落地——修 vol1_entries 源 + official.py 补丁（只读预演）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_entries.json").read_text(encoding="utf-8"))

# 修法（D45）：
RENAMES = {"蔣晁": "蔣冕", "劉翔": "劉珝", "李國楷": "李國𣚴"}
REMOVES = [(1633, "錢溥"), (1635, "錢溥")]           # OCR 张冠李戴，原书 1633/1635 是錢士升
ADD = [(1543, "翟鑾", "")]                             # 原书 p281 翟鑾行（无注），OCR 丢行
NOTE_FIX = {(1633, "錢士升"): "九、庚戌、廿一，南禮右侍遷禮尚兼東閣大學士入。"}  # 原属錢溥注移给錢士升

n_rename = sum(1 for r in e if r["person"] in RENAMES)
n_remove = sum(1 for r in e if (r["year"], r["person"]) in REMOVES)
print(f"改 {n_rename} 条、删 {n_remove} 条、补 {len(ADD)} 条、注移 1 条")
for r in e:
    if (r["year"], r["person"]) in [(1633, "錢士升"), (1634, "錢士升")]:
        print("  錢士升 现状:", r["year"], r.get("note", "")[:30])
# 1633 錢士升 在 entries 里存在吗？
print("1633 錢士升 in entries:", any(r["year"] == 1633 and r["person"] == "錢士升" for r in e))
