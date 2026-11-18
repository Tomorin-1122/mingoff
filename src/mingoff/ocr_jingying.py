# -*- coding: utf-8 -*-
"""总督京营戎政大臣年表解析（2026-11-18，试点转正式）。

输入：_scratch/zongdu_survey/raw_pages/p{7..103}.jsonl（Paddle 行框，试点轮产物）
输出：src/mingoff/data/vol3_jingying_entries.json
      src/mingoff/data/vol3_jingying_review.json

版式事实（Paddle 行框实证）：
  1. 一年一页，97 页 = 嘉靖二十九年(1550)–1646；书页 = PDF 页 + 2215
     （锚点 pdf7→2222 / pdf8→2223 / pdf311→2526 页脚实测）；
  2. band = 名字行下方第一条位置标签（京卿同规律）。衙署带：
     總督京營戎政（标签總理/總督，纵排带 京營 下半截）／協理京營戎政／五軍營／
     三千營|神樞營（同槽异名，书本身混印——p7=1550 印三千營、p27=1570 起多印神樞營，
     非硬切换点，按印本如实分立）／神機營／京營參將（p45 型 schema 扩展带）；
  3. 标签纵排可拆行（神+機/五+軍/京+營），按 y 聚簇重组；标签页 vs 无标签页交替，
     无标签页继承最近带标签页的 schema（band 结构随时代缓变，p45 型移位不跨页突跳）；
  4. 注文紧跟名字行下方（同带逐行并入；无注词头碎片并入最近条目）；
     年份头与首名之间的卷首注（如「增神機营坐营官一员」）不入条目，记 review；
  5. 多人同带注文按邻近绑定，标 review；超星水印/页码/页眉过滤。

纪律（沿京卿试点）：人名可自动取；无标签页 office 按 schema 推 → review 标记；
段级 office_status 贯通（label-column / row-order / mixed）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from mingoff.ocr_jingqing import RE_YEAR_FULL, RE_YEAR_BARE

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "_scratch" / "zongdu_survey" / "raw_pages"
OUT = ROOT / "src" / "mingoff" / "data" / "vol3_jingying_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol3_jingying_review.json"
LO, HI = 7, 103
PAGE_OFFSET = 2215            # 书页 = PDF 页 + 2215

# 标签归一：页标签(含纵排重组) → band 正名
LABEL_NORM = {
    "總理": "總督京營戎政", "總督": "總督京營戎政", "京營": "總督京營戎政",
    "協理": "協理京營戎政", "协理": "協理京營戎政", "提督": "協理京營戎政",
    "五軍": "五軍營", "五軍營": "五軍營", "三千": "三千營", "三千營": "三千營",
    "神樞": "神樞營", "神樞營": "神樞營", "神機": "神機營", "神機營": "神機營",
    "京營參將": "京營參將", "世樞": "神樞營",
}
# 单字纵排碎片（标签列重组原料）
FRAG1 = set("神機五軍樞三千京營理協總将參")
RE_NAME = re.compile(r"^[\u4e00-\u9fff]{2,6}$")
RE_PAREN = re.compile(r"^[\u4e00-\u9fff][（(][\u4e00-\u9fff]{1,2}[)）][\u4e00-\u9fff]{0,2}$")
RE_PAGE_NO = re.compile(r"^\.?\d+\s*$")
RE_PUNCT = re.compile(r"[，。；、：（()）!！?？]")
RE_WM = re.compile(r"^[睿家旅超交]华[邮书]$|^超星|^图书|华邮|华书|^交书$")
SKIP = {"明代職官年表", "總督京营戎政大臣年表", "官", "職", "官職", "年代", "年", "代",
        "官代", "食", "旅手地", "睿华邮", "家华书", "旅华书"}
RE_NOTE_HEAD = re.compile(
    r"^(?:閏[正臘一二三四五六七八九十]{1,2}|正|[一二三四五六七八九十]{1,2})、"
    r"|^(?:閏[正臘一二三四五六七八九十]{1,2}|[一二三四五六七八九十]{1,2})月"
    r"|^(?:是年|同年|先是|尋|坐|卒|贈|加|兼|改|復|署|降|升|調|還|致仕|起|罷|任|充|寻)")


def load_pages() -> dict[int, list[tuple[str, int, int]]]:
    pages = {}
    for p in range(LO, HI + 1):
        f = RAW / f"p{p}.jsonl"
        if f.is_file():
            d = json.loads(f.read_text(encoding="utf-8").splitlines()[0])
            oc = d["result"]["ocrResults"][0]["prunedResult"]
            rows = []
            for t, b in zip(oc["rec_texts"], oc["rec_boxes"]):
                x, y = int(b[0]), int(b[1])
                if x > 1150 and 1700 < y < 1850:
                    stats_wm[0] += 1        # 右下角超星水印区（睿华邮/家华船等变体）
                    continue
                rows.append((t.strip(), x, y))
            pages[p] = rows
    return pages


stats_wm = [0]


def year_map(pages) -> dict[int, int]:
    ym = {}
    for p, rows in pages.items():
        for t, x, y in rows:
            m = RE_YEAR_FULL.search(t) or RE_YEAR_BARE.search(t)
            if m:
                ym[p] = int(m.group(2) if RE_YEAR_FULL.search(t) else m.group(1))
                break
    for p in range(LO, HI + 1):
        if p not in ym and p in pages:
            prev = next((ym[q] for q in range(p - 1, LO - 1, -1) if q in ym), None)
            nxt = next((ym[q] for q in range(p + 1, HI + 1) if q in ym), None)
            ym[p] = prev + 1 if prev else nxt
    return ym


def _label_of(t: str):
    if RE_PUNCT.search(t) or len(t) > 5:
        return None
    if t in LABEL_NORM:
        return LABEL_NORM[t]
    if len(t) == 1 and t in FRAG1:
        return t          # 碎片原样返回，聚簇后重组
    if t[:2] in LABEL_NORM:
        return LABEL_NORM[t[:2]]
    return None


# 七衙署带正名（显式集合，供规范判别）
CANON_BANDS = {"總督京營戎政", "協理京營戎政", "五軍營", "三千營", "神樞營",
               "神機營", "京營參將"}

def _cluster_labels(rows) -> list[tuple[str, int]]:
    """标签列 → [(band 正名, y)]。完整标签直收；单字碎片按 y 聚簇（gap≤110px）重组。"""
    frags = sorted([(y, _label_of(t)) for t, x, y in rows
                    if x < 380 and _label_of(t)], key=lambda v: v[0])
    out, cur, cur_y = [], [], None

    def settle():
        nonlocal cur, cur_y
        if cur:
            norm = LABEL_NORM.get("".join(cur))
            if norm:
                out.append((norm, cur_y))
            cur, cur_y = [], None

    for y, lab in frags:
        if lab in CANON_BANDS:
            settle()
            out.append((lab, y))
        else:                      # 单字碎片
            if cur and y - cur_y > 110:
                settle()
            if not cur:
                cur_y = y
            cur.append(lab)
    settle()
    # 同带多簇（總理+京營 纵排两簇）合并取最小 y
    merged: dict[str, list[int]] = {}
    for b, y in out:
        merged.setdefault(b, []).append(y)
    return sorted(((b, min(ys)) for b, ys in merged.items()), key=lambda v: v[1])


def parse():
    pages = load_pages()
    ymap = year_map(pages)
    # 1) 各页带标签 schema（含继承）
    schema: dict[int, list[tuple[str, int]]] = {}
    for p, rows in pages.items():
        lb = _cluster_labels(rows)
        if len(lb) >= 3:
            schema[p] = lb
    last = None
    own_labeled: set[int] = set()
    for p in range(LO, HI + 1):
        if p in schema:
            last = schema[p]
            own_labeled.add(p)
        elif last and p in pages:
            schema[p] = last  # 无标签页继承最近 schema（band 结构缓变）
    stats = Counter()
    review: list[dict] = []
    entries: list[dict] = []
    for p in range(LO, HI + 1):
        rows = pages.get(p)
        if not rows:
            continue
        yr = ymap.get(p)
        if yr is None:
            stats["no_year"] += 1
            continue
        book = p + PAGE_OFFSET
        labeled = p in own_labeled
        sl = schema.get(p, [])
        bands: dict[str, dict] = defaultdict(lambda: {"names": [], "strays": []})
        top_notes: list[str] = []
        content = sorted([(y, x, t) for t, x, y in rows
                          if t and t not in SKIP and not RE_WM.match(t)
                          and not RE_PAGE_NO.match(t)
                          and not (x < 380 and _label_of(t))
                          and not RE_YEAR_FULL.search(t) and not RE_YEAR_BARE.search(t)
                          and "年表" not in t], key=lambda v: (v[0], v[1]))
        first_name_y = next((y for y, x, t in content if _is_name(t)), None)
        for y, x, t in content:
            if first_name_y is not None and y < first_name_y - 40:
                top_notes.append(t)          # 卷首注（衙署增革说明）
                stats["top_note"] += 1
                continue
            b = _band_for(y, sl)
            bd = bands[b]
            if _is_name(t):
                bd["names"].append({"name": t, "note": "", "cont": []})
                stats["names"] += 1
            elif bd["names"]:
                lastn = bd["names"][-1]
                if RE_NOTE_HEAD.match(t):
                    lastn["note"] += t
                    stats["notes"] += 1
                else:
                    lastn["cont"].append(t)
                    stats["note_cont"] += 1
            else:
                bd["strays"].append(t)
                stats["stray"] += 1
        for b, bd in bands.items():
            n = len(bd["names"])
            for i, nm in enumerate(bd["names"]):
                e = {"year": yr, "office": b, "person": nm["name"],
                     "note": nm["note"],
                     "raw": " ".join([nm["note"]] + nm["cont"]).strip(),
                     "conf": 0.7 if labeled else 0.6,
                     "review": None, "book_page": book}
                if not labeled:
                    e["review"] = "无标签页，官职按最近 schema 推"
                if n >= 2:
                    e["review"] = ((e["review"] + "；") if e["review"] else "") + \
                        f"多人同带({n}人)，注文按邻近绑定"
                if nm["cont"]:
                    e["note"] += "".join(nm["cont"])
                if e["review"]:
                    review.append({"year": yr, "office": b, "person": nm["name"],
                                   "review": e["review"], "book_page": book})
                entries.append(e)
        for tn in top_notes:
            review.append({"year": yr, "office": "卷首注", "person": "",
                           "review": f"卷首注：{tn}", "book_page": book})
    stats["pages"] = len(pages)
    stats["years"] = len(set(e["year"] for e in entries))
    stats["watermark_skipped"] = stats_wm[0]
    return entries, review, stats


def _is_name(t: str) -> bool:
    return bool(RE_NAME.match(t) or RE_PAREN.match(t))


def _band_for(y: int, sl: list[tuple[str, int]]):
    if sl:
        for b, ly in sorted(sl, key=lambda v: v[1]):
            if y < ly:
                return b
        return sorted(sl, key=lambda v: v[1])[-1][0]
    return "未知"


def main():
    entries, review, stats = parse()
    meta = {
        "dataset": "总督京营戎政大臣年表",
        "source": "张德信《明代职官年表》第3册（PDF 7–103，书页 2222–2318）；PaddleOCR 行框",
        "year_range": [1550, 1646],
        "page_offset": PAGE_OFFSET,
        "stats": {**dict(stats), "entries": len(entries), "review": len(review)},
    }
    OUT.write_text(json.dumps({"meta": meta, "entries": entries},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps({"meta": meta, "items": review},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print("stats:", json.dumps(meta["stats"], ensure_ascii=False))
    for y in (1550, 1588, 1644):
        es = [(e["office"], e["person"], e["note"][:18])
              for e in entries if e["year"] == y]
        print(f"--- {y} ---")
        for o, p, n in es:
            print(f"  {o}: {p} {n}")


if __name__ == "__main__":
    main()
