# -*- coding: utf-8 -*-
"""六科都給事中 book-patch 修复层（2026-11-07，原书实拍判读）。

地面真相（证据图 docs/evidence/keji/，渲染脚本 _scratch/keji_survey/render_hi.py）：

  1. **1618（正文 1493 / PDF 231）MinerU 丢表**：内容以 `## 人名` 片段溢出 md
     （parse_tables 不收 → 条目为空）。原书整页 6 带，带 1/2/4 有人。转录 3 条补入，
     与 md 溢出片段逐字互证 + 邻年闭环（1617 兵科=趙興邦(署)；1619 吏科=趙興邦 续任）：
       带1 吏科 趙興邦「十一、丁酉、十二，署兵給遷。」= 由署兵科遷入
       带2 戶科 吴亮嗣「十、癸未、廿八，推升不報。」
       带4 兵科 趙興邦「十一、丁酉、十二，遷吏都給。」= 遷出（赴吏科都給）
  2. **1637（崇禎十年丁丑）原书缺页**：·1511·(1636) 与 ·1512·(1638) 页脚连续，
     全书 246 个 content_list 表块无一含 1637 年份头、两份 OCR md 全文零「崇禎十年」。
     **非 OCR 丢失，不补条目**；任职段跨 1637 由 gap 逻辑显式记录（gap_years）。
  3. **1638（正文 1512 / PDF 250）4 条多人同格注文补配**：原解析「注文不猜配」，
     图上左右列对应明确（同一 cell 内人名列与注文列垂直对齐）：
       兵科 凌義渠「是年,遷福建參政。」 / 姚思孝「是年任;四、戊申、十五,奏。」
       工科 何楷「五、丁丑、十五,奏;七、戊寅、十七,降二級調用。」 / 范淑泰「十一、丙寅、八,奏。」

页码实测（build_page_map_keji 同源）：content_list 页脚捕获 253/254 页；
线性式 1268+(年−1393) 于 1393–1636 逐页精确，1638–1643 因原书缺 1637 页整体 −1，
1644=1518，弘光元年 1519–1520（D15 剔除）。

修复在组装时应用（仿 buyuan_repair.py：解析层保持忠实转录，修复层独立可审计）。
"""
from __future__ import annotations

import copy

# 1618 转录补录（raw 保留 md 溢出片段原貌——全角逗号；note 归一为语料半角风格）
BOOK_PAGE_1618 = "book-p1493"
BOOK_ADD_1618: list[dict] = [
    {"year": 1618, "office": "吏科", "person": "趙興邦",
     "note": "十一、丁酉、十二,署兵給遷。",
     "raw": "趙興邦 十一、丁酉、十二，署兵給遷。"},
    {"year": 1618, "office": "戶科", "person": "吴亮嗣",
     "note": "十、癸未、廿八,推升不報。",
     "raw": "吴亮嗣 十、癸未、廿八，推升不報。"},
    {"year": 1618, "office": "兵科", "person": "趙興邦",
     "note": "十一、丁酉、十二,遷吏都給。",
     "raw": "趙興邦 十一、丁酉、十二，遷吏都給。"},
]
REVIEW_TRANSCRIBE = "原书转录补录（p1493，MinerU 丢表），待老板抽检"

# 1638 多人同格注文补配：(person, office) → note
BOOK_PAGE_1638 = "book-p1512"
BOOK_PATCH_1638: dict[tuple[str, str], str] = {
    ("凌義渠", "兵科"): "是年,遷福建參政。",
    ("姚思孝", "兵科"): "是年任;四、戊申、十五,奏。",
    ("何楷", "工科"): "五、丁丑、十五,奏;七、戊寅、十七,降二級調用。",
    ("范淑泰", "工科"): "十一、丙寅、八,奏。",
}
REVIEW_PATCHED = "注文按原书 p1512 左右列补配（book-patch），待老板抽检"

# 原书缺页（结构性缺口，留档不补条目）
BOOK_GAP_YEARS = [1637]

# book-patch 年的实测页码（页脚原书可见：p231 页脚 ·1493·，2026-11-07 实拍）——
# 该页 MinerU 丢表 → content_list 无表块，页映射须显式补入
BOOK_PAGE_MAP = {1618: 1493}


def apply_keji_repair(entries: list[dict], report: dict | None = None) -> list[dict]:
    """应用 book-patch：1618 补 3 条 + 1638 补配 4 条注文。返回新列表（不 mutate 入参）。"""
    rep = report if report is not None else {}
    out = [copy.deepcopy(e) for e in entries]

    added: list[str] = []
    for spec in BOOK_ADD_1618:
        out.append({"year": spec["year"], "office": spec["office"],
                    "person": spec["person"], "note": spec["note"],
                    "raw": spec["raw"], "conf": 0.8,
                    "review": REVIEW_TRANSCRIBE,
                    "src": "book-patch", "book_page": BOOK_PAGE_1618})
        added.append(f'{spec["year"]} {spec["office"]} {spec["person"]}')

    patched: list[str] = []
    for e in out:
        key = (e.get("person"), e.get("office"))
        if e.get("year") == 1638 and key in BOOK_PATCH_1638:
            e["note"] = BOOK_PATCH_1638[key]
            e["review"] = REVIEW_PATCHED
            e["conf"] = 0.8
            e["src"] = "book-patch"
            e["book_page"] = BOOK_PAGE_1638
            patched.append(f'1638 {e["office"]} {e["person"]}')

    rep["book_patch"] = {"added": added, "patched": patched,
                         "book_gap_years": list(BOOK_GAP_YEARS)}
    return out
