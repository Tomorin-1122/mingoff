# -*- coding: utf-8 -*-
"""总督年表解析（2026-11-19）。

输入：_scratch/zongdu_survey/raw_pages/p{105..309}.jsonl（Paddle 行框，11-18 全卷轮）
输出：src/mingoff/data/vol3_zongdu_entries.json / vol3_zongdu_review.json

版式事实（pdf105/150/250 实证）：
  1. 一年一页为主（少数跨页年，如 1622）；书页 = PDF + 2215（锚点 2320/2365 页脚）；
  2. band = 名字行下方第一条区域标签（京卿/京营同规律）；区域标签可为多行纵排
     （總督+漕運 两行 = 總督漕運）或单字 2×2 网格（陝+西/三+邊 → 陝西三邊）：
     单字按行聚簇（y gap≤25，行内按 x 排序），行簇再拼（gap≤90）；
  3. 区域标签正名 = 剥「總督/總理/提督/經略/兼制/兼撫」前缀 + 總漕→漕運、總河→河道，
     其余按印本（兩廣/宣大/薊遼/漕運/三邊/陕西/河道/貴州/川貴/湖廣…）；
     同位异印（漕運/總督漕運）归并后分段连续；
  4. 名字行 x>300（双槽 x≈390/1020），注文紧跟名字行下方（同带逐行并入）；
  5. 角标区（y<360）与右下水印区（x>1150, y1700–1850）过滤；年份头与首名之间的
     卷首注（衙署增革说明）不入条目，记 review。
纪律：无本页标签页继承最近 schema（如实标 review）；人名可自动取；段可溯源。
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
from mingoff.ocr_jingying import RE_NAME, RE_PAREN, RE_NOTE_HEAD, RE_PUNCT, RE_PAGE_NO

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "_scratch" / "zongdu_survey" / "raw_pages"
OUT = ROOT / "src" / "mingoff" / "data" / "vol3_zongdu_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol3_zongdu_review.json"
LO, HI = 105, 309
PAGE_OFFSET = 2215

SKIP_TEXT = {"明代職官年表", "總督年表", "官", "職", "年", "代", "年代", "官代",
             "書", "书", "食", "大木", "成化", "成义", "成代"}
RE_WM = re.compile(r"华[邮书州帜船]|^W驰$|^客驰$|^书$|^家$|^#业$|驰$|^超星")
PREFIX_STRIP = ("總督", "總理", "提督", "經略", "兼制", "兼撫")
LABEL_ALIAS = {"總漕": "漕運", "總河": "河道"}
JUNK_LABELS = {"大木", "務", "書"}   # 拼接后仍为垃圾的标签名，整带丢弃

wm_skipped = [0]


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
                    wm_skipped[0] += 1
                    continue
                rows.append((t.strip(), x, y))
            pages[p] = rows
    return pages


def year_map(pages: dict) -> dict[int, int]:
    ym = {}
    for p, rows in pages.items():
        for t, x, y in rows:
            m = RE_YEAR_FULL.search(t)
            if m:
                ym[p] = int(m.group(2))
                break
            m = RE_YEAR_BARE.search(t)
            if m:
                ym[p] = int(m.group(1))
                break
    for p in range(LO, HI + 1):
        if p not in ym and p in pages:
            prev = next((ym[q] for q in range(p - 1, LO - 1, -1) if q in ym), None)
            nxt = next((ym[q] for q in range(p + 1, HI + 1) if q in ym), None)
            ym[p] = prev + 1 if prev else nxt
    return ym


def _norm_label(text: str):
    for pre in PREFIX_STRIP:
        if text.startswith(pre) and len(text) > len(pre):
            text = text[len(pre):]
            break
    return LABEL_ALIAS.get(text, text)


def _line_cluster(frags: list[tuple[int, int, str]]) -> list[str]:
    """单字碎片 → 行（y gap≤25，行内按 x 排序）；行簇拼接（gap≤90）。"""
    frags.sort(key=lambda v: (v[1], v[0]))     # (x, y, ch) → y 为主
    lines, cur = [], []
    for x, y, ch in frags:
        if cur and y - cur[-1][1] > 25:
            lines.append(cur)
            cur = []
        cur.append((x, y, ch))
    if cur:
        lines.append(cur)
    # 行 → 文本
    texts = []
    for ln in lines:
        ln.sort(key=lambda v: v[0])
        texts.append(("".join(c for _, _, c in ln), ln[0][1]))
    # 行簇拼接（gap≤90），返回 [(拼接文本, 首行 y)]
    out, buf = [], [texts[0]] if texts else []
    for t, y in texts[1:]:
        if y - buf[-1][1] > 90:
            out.append(("".join(b[0] for b in buf), buf[0][1]))
            buf = []
        buf.append((t, y))
    if buf:
        out.append(("".join(b[0] for b in buf), buf[0][1]))
    return out


def collect_labels(rows) -> list[tuple[str, int, bool]]:
    """本页区域标签 → [(office 正名, 首行 y, 网格拼接来源)]。"""
    cands = sorted([(y, x, t) for t, x, y in rows
                    if x < 300 and 360 < y < 2100 and 1 <= len(t) <= 6
                    and not RE_PUNCT.search(t) and t not in SKIP_TEXT
                    and (RE_NAME.match(t) or len(t) == 1)],
                   key=lambda v: v[0])
    items = []
    for y, x, t in cands:
        if len(t) == 1:
            items.append(("frag", y, x, t))
        else:
            items.append(("word", y, x, t))
    out: list[tuple[str, int, bool]] = []
    i = 0
    while i < len(items):
        if items[i][0] == "word":
            lab = _norm_label(items[i][3])
            if lab:
                out.append((lab, items[i][1], False))
            i += 1
        else:
            j = i
            while j < len(items) and items[j][0] == "frag":
                j += 1
            fragblock = [(x, y, t) for _, y, x, t in items[i:j]]
            for text, y0 in _line_cluster([(x, y, c) for x, y, c in fragblock]):
                lab = _norm_label(text)
                if lab:
                    out.append((lab, y0, True))
            i = j
    # 同名相邻标签合并（同位重复取最小 y）
    merged: dict[str, list[int]] = {}
    origin: dict[str, bool] = {}
    for lab, y, fg in out:
        merged.setdefault(lab, []).append(y)
        origin[lab] = origin.get(lab, False) or fg
    cands2 = sorted(((lab, min(ys)) for lab, ys in merged.items()), key=lambda v: v[1])
    # 相邻异名标签纵向拼接（两行复合标签：總督+漕運 → 總督漕運；gap≤90）
    joined: list[tuple[str, int, bool]] = []
    for lab, y in cands2:
        if joined and y - joined[-1][1] <= 90:
            plab, _, pfg = joined[-1]
            joined[-1] = (plab + lab, y, pfg)
        else:
            joined.append((lab, y, origin.get(lab, False)))
    return [(_norm_label(lab), y, fg) for lab, y, fg in joined
            if _norm_label(lab) not in JUNK_LABELS]


def _is_name(t: str) -> bool:
    return bool(RE_NAME.match(t) or RE_PAREN.match(t))


def _band_for(y: int, labels):
    for lab, ly, _fg in labels:
        if y < ly:
            return lab
    return labels[-1][0] if labels else "未知"


def parse():
    pages = load_pages()
    ymap = year_map(pages)
    schema: dict[int, list] = {}
    own_labeled: set[int] = set()
    last = None
    for p in range(LO, HI + 1):
        rows = pages.get(p)
        if not rows:
            continue
        lb = collect_labels(rows)
        if len(lb) >= 2:
            schema[p] = lb
            own_labeled.add(p)
            last = lb
        elif last:
            schema[p] = last
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
        bands = defaultdict(lambda: {"names": []})
        top_notes: list[str] = []
        content = sorted([(y, x, t) for t, x, y in rows
                          if t and t not in SKIP_TEXT and not RE_WM.search(t)
                          and not RE_PAGE_NO.match(t) and x > 300 and 360 < y < 2100
                          and not RE_YEAR_FULL.search(t) and not RE_YEAR_BARE.search(t)
                          and "年表" not in t], key=lambda v: (v[0], v[1]))
        first_name_y = next((y for y, x, t in content if _is_name(t)), None)
        for y, x, t in content:
            if first_name_y is not None and y < first_name_y - 40:
                top_notes.append(t)
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
                stats["stray"] += 1
        for b, bd in bands.items():
            n = len(bd["names"])
            fg = next((f for lab, _y, f in sl if lab == b), False)
            for nm in bd["names"]:
                note = nm["note"] + "".join(nm["cont"])
                e = {"year": yr, "office": b, "person": nm["name"],
                     "note": note, "raw": note, "conf": 0.7 if labeled else 0.6,
                     "review": None, "book_page": book}
                if not labeled:
                    e["review"] = "无本页标签，官职按最近 schema 推"
                if fg:
                    e["review"] = ((e["review"] + "；") if e["review"] else "") + \
                        "区域标签为单字网格拼接，官职名待核"
                if n >= 2:
                    e["review"] = ((e["review"] + "；") if e["review"] else "") + \
                        f"多人同带({n}人)，注文按邻近绑定"
                if e["review"]:
                    review.append({"year": yr, "office": b, "person": nm["name"],
                                   "review": e["review"], "book_page": book})
                entries.append(e)
        for tn in top_notes:
            review.append({"year": yr, "office": "卷首注", "person": "",
                           "review": f"卷首注：{tn}", "book_page": book})
    stats["pages"] = len(pages)
    stats["watermark_skipped"] = wm_skipped[0]
    return entries, review, stats, ymap


def main():
    entries, review, stats, ymap = parse()
    meta = {
        "dataset": "总督年表",
        "source": "张德信《明代职官年表》第3册 PDF 105–309（书页 2320–2524）；PaddleOCR 行框",
        "year_range": [min(ymap.values()), max(ymap.values())],
        "page_offset": PAGE_OFFSET,
        "band_rule": "名字行属其下方第一条区域标签；标签可多行纵排（總督+漕運）"
                     "或单字网格（陝西三邊）；官职正名剥總督/總理等前缀",
        "stats": {**dict(stats), "entries": len(entries), "review": len(review)},
    }
    OUT.write_text(json.dumps({"meta": meta, "entries": entries},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps({"meta": meta, "items": review},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print("stats:", json.dumps(meta["stats"], ensure_ascii=False))
    for y in (1449, 1494, 1594, 1644):
        es = [(e["office"], e["person"], e["note"][:16])
              for e in entries if e["year"] == y]
        print(f"--- {y} ({len(es)}条) ---")
        for o, p, n in es[:12]:
            print(f"  {o}: {p} {n}")


if __name__ == "__main__":
    main()
