# -*- coding: utf-8 -*-
"""京卿/六科 粘连人名格子级修复（2026-11-07，正字别名轮第一波）。

背景：多人同格（≥3 人并排）的格子，OCR 无分隔粘连（如「嚴世蕃陸煒徐養正四、乙酉、…」），
split_persons 兜底只切 2–4 字头 → 产出「嚴世蕃陸」这类假人名（CBDB no-candidate）。

修复方式（证据两级）：
  1. CBDB 人名词典（BIOG_MAIN 正名+别名 48.8 万+9.5 万）对格子人名区贪心最长匹配，
     全部成分命中才采纳（`_scratch/keji_survey/propose_glue_split.py` 提议、人工逐条核对）；
  2. 拆出的成分与原书注文事件交叉印证（如 沈人種|何源 的「閏九、戊午、廿一,遷大理卿」
     与 順天府府尹 格「何源閏九、戊午、廿一,太常卿遷」同日互证）。

应用（组装前）：按 (year, office) 定位格子 → 删除垃圾碎片条目（人名精确指认）→
按 persons 重建（首条带注文/原文，余人注文空），一律 conf 0.5 + review 留痕。
注文列对应关系本就不可知（多人同格纪律），故注文体留在首条、不猜配。
"""
from __future__ import annotations

import copy

# 格子拆分规格：year/office 定位；remove=垃圾碎片人名（逐格实查）；glue=人名区粘连原文；
# persons=正确拆分（词典命中+原书互证）
CELL_SPLITS: dict[str, list[dict]] = {
    "jingqing": [
        {"year": 1425, "office": "通政使", "remove": ["古樸李", "嘉顧佐"],
         "glue": "古樸李嘉顧佐", "persons": ["古樸", "李嘉", "顧佐"]},
        {"year": 1557, "office": "通政使", "remove": ["汪宗", "元盧勳"],
         "glue": "汪宗元盧勳", "persons": ["汪宗元", "盧勳"]},
        {"year": 1557, "office": "大理卿", "remove": ["張舜臣胡"],
         "glue": "張舜臣胡叔廉錢邦彥", "persons": ["張舜臣", "胡叔廉", "錢邦彥"]},
        {"year": 1557, "office": "光祿卿", "remove": ["郝良臣胡"],
         "glue": "郝良臣胡叔廉何遷", "persons": ["郝良臣", "胡叔廉", "何遷", "盧宗哲"]},
        {"year": 1557, "office": "尚寶卿", "remove": ["嚴世蕃陸"],
         "glue": "嚴世蕃陸煒徐養正", "persons": ["嚴世蕃", "陸煒", "徐養正"]},
        {"year": 1573, "office": "太僕卿", "remove": ["羅良李幼"],
         "glue": "羅良李幼滋吴道直王世貞", "persons": ["羅良", "李幼滋", "吴道直", "王世貞"]},
        {"year": 1585, "office": "太常卿", "remove": ["沈人", "種何源"],
         "glue": "沈人種何源", "persons": ["沈人種", "何源"]},
        {"year": 1622, "office": "太常卿", "remove": ["白瑜趙南"],
         "glue": "白瑜趙南星朱光祚", "persons": ["白瑜", "趙南星", "朱光祚"]},
        {"year": 1622, "office": "光祿卿", "remove": ["白所知許"],
         "glue": "白所知許維新洪翼聖胡克儉", "persons": ["白所知", "許維新", "洪翼聖", "胡克儉"]},
    ],
    "kejishizhong": [
        {"year": 1499, "office": "工科", "remove": ["林廷", "玉韓智"],
         "glue": "林廷玉韓智", "persons": ["林廷玉", "韓智"]},
        {"year": 1543, "office": "禮科", "remove": ["李泰管見"],
         "glue": "李泰管見劉大直周采", "persons": ["李泰", "管見", "劉大直", "周采"]},
        {"year": 1543, "office": "兵科", "remove": ["王繼宗錢"],
         "glue": "王繼宗錢亮戴夢桂", "persons": ["王繼宗", "錢亮", "戴夢桂"]},
    ],
}

# 假人名移除（格子内容实为官名串行/标签渗漏，非人名）
REMOVES: dict[str, list[tuple[int, str, str]]] = {
    "jingqing": [(1612, "太常卿", "光祿卿")],   # 格子原文「光祿卿.」= 官名渗漏
    "kejishizhong": [],
}


def apply_glue_repair(entries: list[dict], table: str,
                      report: dict | None = None) -> list[dict]:
    """应用格子拆分/移除。返回新列表（不 mutate 入参）。"""
    rep = report if report is not None else {}
    out = [copy.deepcopy(e) for e in entries]
    splits, removes = 0, 0

    for spec in CELL_SPLITS.get(table, []):
        idxs = [i for i, e in enumerate(out)
                if e["year"] == spec["year"] and e["office"] == spec["office"]
                and e["person"] in spec["remove"]]
        if not idxs:
            continue
        first = out[idxs[0]]
        raw = first.get("raw", "")
        note = raw[len(spec["glue"]):].strip(" ，。") if raw.startswith(spec["glue"]) \
            else first.get("note", "")
        persons = spec["persons"]
        rebuilt = []
        for k, p in enumerate(persons):
            rebuilt.append({
                "year": spec["year"], "office": spec["office"], "person": p,
                "note": note if k == 0 else "",
                "raw": raw if k == 0 else "",
                "conf": 0.5,
                "review": f"多人同格({len(persons)}人)，注文列对应丢失；"
                          f"按CBDB词典+原书格子拆分",
                "src": "glue-split",
            })
        at = idxs[0]
        for i in sorted(idxs, reverse=True):
            del out[i]
        out[at:at] = rebuilt
        splits += 1

    for (year, office, person) in REMOVES.get(table, []):
        before = len(out)
        out = [e for e in out
               if not (e["year"] == year and e["office"] == office
                       and e["person"] == person)]
        removes += before - len(out)

    rep["glue_repair"] = {"table": table, "cells_split": splits, "removed": removes}
    return out
