"""D45（人工核验 6 条）落地：修 vol1_entries.json 源数据（幂等，可复跑）。

老板手核（docs/人工核验.md）：
  1. 天启七年 李國楷 → 应为 李國𣚴（原书 p372 文淵閣行；OCR 楷/𣚴 形近）
  2. 錢溥（1633/1635）→ 原书无，应为 錢士升（1633 行即錢士升入阁；錢溥是天顺朝人，CBDB 张冠李戴）
  3. 劉一燝 万历四十八年(1620)入阁 —— 数据已正确（1620 起），仅确认
  4. 翟鑾 嘉靖二十二年(1543)在任 —— 原书 p281 有翟鑾行（无注），OCR 丢行 → 补
  5. 蔣冕 嘉靖三年正月至五月都在任 —— OCR 1521-1523 把「蔣冕」误成「蔣 晁」→ 归一
  6. 成化十一年(1475) 劉翔 → 实为 劉珝 → 归一

修完重跑 `python -m mingoff.official` 重建 official_cabinet.json。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
ENT = ROOT / "src/mingoff/data/vol1_entries.json"

RENAMES = {"蔣晁": "蔣冕", "劉翔": "劉珝", "李國楷": "李國𣚴"}
REMOVES = [(1633, "錢溥"), (1635, "錢溥")]
ADD = [(1543, "翟鑾", "")]

e = json.loads(ENT.read_text(encoding="utf-8"))
n0 = len(e)

# 1 改名（含 1633「錢溥」实为 OCR 把「錢士升」切成「錢溥」「升」——raw 为 '錢士'+'升 九、庚戌…'）
for r in e:
    if r["person"] in RENAMES:
        r["person"] = RENAMES[r["person"]]
# 1b 1633「錢溥」条实为錢士升（原书 book374 文淵閣行：錢士升 九、庚戌、廿一,南禮右侍遷禮尚兼東閣大學士入）
for r in e:
    if r["year"] == 1633 and r["person"] == "錢溥":
        r["person"] = "錢士升"
        r["note"] = "九、庚戌、廿一，南禮右侍遷禮尚兼東閣大學士入。"
        r["raw_person"] = "錢溥"
# 1c 1635「錢溥 note=升」条：原书 1635 行只有錢士升（空行续任），该条是 1633 错切碎片 → 删

# 2 删錢溥误条（1635 残片）
e = [r for r in e if (r["year"], r["person"]) not in REMOVES]

# 4 补 1543 翟鑾
if not any(r["year"] == 1543 and r["person"] == "翟鑾" for r in e):
    e.append({"year": 1543, "person": "翟鑾", "note": "", "raw_person": "翟鑾",
              "src": "book-p281"})

# 5 补 1635 錢士升（原书 book376(1635) 有錢士升空行=续任；OCR 1635 段有「錢士升」名行被丢）
if not any(r["year"] == 1635 and r["person"] == "錢士升" for r in e):
    e.append({"year": 1635, "person": "錢士升", "note": "", "raw_person": "錢士升",
              "src": "book-p376"})

e.sort(key=lambda r: (r["year"], r["person"]))
ENT.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"entries: {n0} -> {len(e)}（改 6 / 删 2 / 补 1）")
