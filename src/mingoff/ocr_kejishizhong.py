# -*- coding: utf-8 -*-
"""六科都給事中年表解析（2026-11-04，册2 正文 1267–1520 / PDF 5–258）。

输入：MinerU OCR 的 md（_scratch/mineru_nianbiao/out/vol2_kejishizhong_{a,b}.md）
输出：src/mingoff/data/vol2_kejishizhong_entries.json（提取物）
      src/mingoff/data/vol2_kejishizhong_review.json（待核清单）

版式事实（实拍 + md 普查，2026-11-04）：
  1. 与京卿同家族：一年一页、跨页成对，左页「官/職+年/代」角标 + 六科标签列
     （吏/戶/禮/兵/刑/工科），右页无标签 6 带按行位对应；带内多人并排成子列；
  2. **双年页是常态**（46 例 vs 京卿 1 例）：全部为「堆叠形」——年 A 带标签 6 行 +
     年 B 年份头行 + 年 B 无标签行，同在一个 <table> 内；年份头切表即可，
     年 B 行用 ref_seq（=年 A 的六科序）定位。无京卿 1396/1397 那种左右混排形
     （单行双年份头 0 例），不需要 Paddle x 裁决；
  3. 表覆盖 1393–1645：弘光元年(1645) 页在书内，按 D15 南明断限整页不入；
  4. 缺年归因（8 个）：1394/1396/1398/1400/1420/1422 = 原书整页空框、OCR 无表产出
     （1394 已实拍验证；1396/1398/1400/1420/1422 为同型空框，见报告）；
     1618/1637 = **OCR 丢表**（1618 内容溢出为 ## 行、1637 年份头被吞、内容并进
     1636 表尾）——解析器以「失头年份行」保守承接并标 review，补录走 book-patch；
  5. 带内换行：注文行并入上一带（同京卿）；有标签年后出现的**连续 ≥2 行人名行**
     按失头年份块处理（行序推科），单行人名行仍归上一带。

纪律沿京卿试点：人名可自动取；多人同格注文不猜配；无标签年标 review。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mingoff.ocr_jingqing import (is_note_row, parse_tables, row_year,  # noqa: F401
                                  row_years, split_persons, split_year_pages,
                                  text_of)


def split_year_pages_keji(tables_per_md):
    """D15 南明截断：六科表末段实测绘（2026-11-04）——第一个含「福王即位/監國」的表
    是崇禎十七年正页（其年份头注文带监国/即位记事）；其后的表 41=弘光元年无标签页
    （年份头被 OCR 错拷成崇禎十七年）、表 42=弘光元年(1645) 标签页，全属弘光期，
    整块剔除（其中人名任命月全在五月后，>三月断限）。返回 (pages, dropped_rows)。"""
    dropped = 0
    marker_seen = False
    trimmed = []
    for tables in tables_per_md:
        out_tables = []
        for rows in tables:
            if marker_seen:
                dropped += len(rows)
                continue
            has_marker = any("福王即位" in " ".join(r) or "福王監國" in " ".join(r)
                             for r in rows)
            out_tables.append(rows)
            if has_marker:
                marker_seen = True
        trimmed.append(out_tables)
    pages = split_year_pages(trimmed)
    return pages, dropped

ROOT = Path(__file__).resolve().parents[2]
MD = [ROOT / "_scratch" / "mineru_nianbiao" / "out" / f"vol2_kejishizhong_{p}.md"
      for p in ("a", "b")]
OUT = ROOT / "src" / "mingoff" / "data" / "vol2_kejishizhong_entries.json"
REVIEW = ROOT / "src" / "mingoff" / "data" / "vol2_kejishizhong_review.json"

OFFICES = ("吏科", "戶科", "禮科", "兵科", "刑科", "工科")
# 缺年归因（2026-11-04 测绘）：empty=原书整页空框；lost=OCR 丢表有内容待 book-patch
MISSING_ATTR = {
    1394: "empty", 1396: "empty", 1398: "empty", 1400: "empty",
    1420: "empty", 1422: "empty",
    1618: "lost", 1637: "lost",
}
FIRST_YEAR, LAST_YEAR = 1393, 1644  # 1645=弘光元年，D15 不入


def label_of(head: str) -> str | None:
    m = re.match(r"([\u4e00-\u9fff]{1,4}科)", head)
    if m and m.group(1) in OFFICES:
        return m.group(1)
    return None


def structure_page(page: dict, ref_seq: list[str]) -> tuple[list[dict], list[str], list[str]]:
    """一页 → (条目, 本页官职序列, warnings)。京卿版适配：六科框 + 失头年份块。

    预扫定位 6 科帧尾：帧后尾部若含 ≥2 个人名行 → 整块按「失头年份」承接
    （每行占一个 ref_seq 位，注文行并入上一带不占位）；否则尾部行走京卿式并入。
    """
    entries: list[dict] = []
    seq: list[str] = []
    warns: list[str] = []
    rows = page["rows"]

    # 预扫：有标签年的 6 科帧尾与人名行块
    frame_end = None
    label_count = 0
    for i, cells in enumerate(rows):
        if label_of(cells[0].strip() if cells else ""):
            label_count += 1
            if label_count == len(OFFICES):
                frame_end = i
                break
    suspect_from = None
    if frame_end is not None:
        trailing = rows[frame_end + 1:]
        n_name = sum(1 for cl in trailing
                     if cl and any(split_persons(c)[0] for c in cl if c))
        if n_name >= 2:
            suspect_from = frame_end + 1
            warns.append(f"帧后 {n_name} 个人名行按失头年份块承接")

    labelled = False
    cur_office: str | None = None
    last_band: list[tuple[int, dict]] = []   # (格号, 条目)
    block_cursor = [0]                        # 失头块内的 ref_seq 游标

    def emit(cells: list[str], ci_offset: int, year: int, office: str,
             force_review: str | None, conf_cap: float | None) -> None:
        nonlocal last_band
        last_band = []
        for ci, cell in enumerate(cells[ci_offset:]):
            if not cell:
                continue
            names, note = split_persons(cell)
            if not names:
                band = [e for j, e in last_band if j == ci] or \
                       ([e for _, e in last_band] if len(last_band) == 1 else [])
                if band:
                    for e in band:
                        e["note"] = (e["note"] + "；" + cell) if e["note"] else cell
                        e["conf"] = min(e["conf"], 0.5)
                    continue
                warns.append(f"{year} {office} 格无法切出人名: {cell[:30]}")
                continue
            review, conf, this_note = force_review, 0.8, note
            if len(names) > 1:
                review = (review + "；" if review else "") + \
                    f"多人同格({len(names)}人)，注文列对应丢失"
                conf, this_note = min(conf, 0.5), ""
            if conf_cap is not None:
                conf = min(conf, conf_cap)
            if not note and not review:
                conf = 0.7
            for k, name in enumerate(names):
                e = {
                    "year": year,
                    "office": office,
                    "person": name,
                    "note": this_note if (len(names) == 1 or k == 0) else "",
                    "raw": cell if k == 0 else "",
                    "conf": round(conf, 2),
                    "review": review,
                }
                entries.append(e)
                last_band.append((ci, e))

    for ri, cells in enumerate(rows):
        head = cells[0].strip() if cells else ""
        office = label_of(head)
        year = page["years"][0]

        if office:
            labelled = True
            cur_office = office
            seq.append(office)
            emit(cells, 1, year, office, None, None)
            continue

        # ── 非标签行 ──
        has_name = any(split_persons(c)[0] for c in cells if c)

        if suspect_from is not None and ri >= suspect_from:
            # 失头年份块：每行占一个 ref_seq 位（空行=空带），注文行并入上一带
            if not cells or not any(cells):
                block_cursor[0] += 1
                last_band = []
                continue
            if not has_name:
                band = [e for _, e in last_band] if len(last_band) == 1 else []
                if band:
                    for e in band:
                        e["note"] = (e["note"] + "；" + " ".join(c for c in cells if c)) \
                            if e["note"] else " ".join(c for c in cells if c)
                        e["conf"] = min(e["conf"], 0.5)
                    continue
            i = block_cursor[0]
            block_cursor[0] += 1
            blk_office = ref_seq[i] if i < len(ref_seq) else None
            if blk_office is None:
                warns.append(f"{year} 失头块行{i + 1} 超出参考序列({len(ref_seq)}行)")
                last_band = []
                continue
            emit(cells, 0, year, blk_office,
                 "失头年份行，年份暂归当前年（疑为下一年），官职按行序推", 0.4)
            continue

        if cells and is_note_row(cells) and last_band and not has_name:
            # 换行注文行 → 上一带（不占行号）
            for ci, cell in enumerate(cells):
                if not cell:
                    continue
                band = [e for j, e in last_band if j == ci] or \
                       ([e for _, e in last_band] if len(last_band) == 1 else [])
                if band:
                    for e in band:
                        e["note"] = (e["note"] + "；" + cell) if e["note"] else cell
                        e["review"] = ((e["review"] + "；") if e["review"] else "") + \
                            "换行注文残片并入"
                        e["conf"] = min(e["conf"], 0.5)
            continue

        if not labelled:
            # 无标签年：按 ref_seq 行位定科
            i = len(seq)
            if not cells or not any(cells):
                if i < len(ref_seq):
                    seq.append("")
                    continue
                continue  # 帧外空行（MinerU 空带 artifact）：静默跳过
            seq.append("")
            cur_office = ref_seq[i] if i < len(ref_seq) else None
            if cur_office is None:
                warns.append(f"{year} 行{i + 1} 超出参考官职序列({len(ref_seq)}行)")
                continue
            emit(cells, 0, year, cur_office, None, 0.6)
            continue

        # 有标签年的帧内散行人名行（少见）：归当前带并标疑
        if has_name and cur_office:
            emit(cells, 0, year, cur_office,
                 "有标签年内的无标签人名行，暂归当前带，需回原书核对", 0.4)
        elif cur_office is None:
            warns.append(f"{year} 无归属行: {' '.join(cells)[:30]}")
    return entries, seq, warns


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=FIRST_YEAR)
    ap.add_argument("--to-year", type=int, default=LAST_YEAR)
    args = ap.parse_args()

    pages, hg_dropped = split_year_pages_keji(
        [parse_tables(p.read_text(encoding="utf-8")) for p in MD])
    years = [y for p in pages for y in p["years"]]

    entries: list[dict] = []
    all_warns: list[str] = []
    ref_seq: list[str] = []
    for page in pages:
        if not (args.from_year <= page["years"][0] <= args.to_year):
            continue
        es, seq, warns = structure_page(page, ref_seq)
        entries.extend(es)
        all_warns += [f"{page['years'][0]} {w}" for w in warns]
        if seq and seq[0]:
            ref_seq = [o for o in seq if o]

    review = [e for e in entries if e["review"]]
    got_years = sorted({e["year"] for e in entries})
    missing = [y for y in range(args.from_year, args.to_year + 1) if y not in years]
    missing_attr = {y: MISSING_ATTR.get(y, "unattributed") for y in missing}
    empty_years = [y for y, a in missing_attr.items() if a == "empty"]
    lost_years = [y for y, a in missing_attr.items() if a == "lost"]
    dupes = [y for y in set(years) if years.count(y) > 1]

    payload = {
        "meta": {
            "dataset": "六科都給事中年表",
            "source": "张德信《明代职官年表》册2 正文 1267–1520（PDF 5–258，offset −1262 实测）；MinerU OCR",
            "year_range": [min(got_years), max(got_years)] if got_years else None,
            "pilot_range": [args.from_year, args.to_year],
            "stats": {
                "entries": len(entries),
                "years_with_entries": len(got_years),
                "missing_years": missing,
                "missing_attr": missing_attr,
                "empty_frame_years": empty_years,
                "lost_table_years": lost_years,
                "dup_years": dupes,
                "persons": len({e["person"] for e in entries}),
                "with_note": sum(1 for e in entries if e["note"]),
                "review": len(review),
                "warn": len(all_warns),
                "conf_avg": round(sum(e["conf"] for e in entries) / len(entries), 3) if entries else None,
                "hongguang_rows_dropped": hg_dropped,
            },
            "note": "缺年 8 个已归因：6 空框（原书实拍验证）+ 2 丢表（1618/1637 待 book-patch）；"
                    "弘光元年(1645) 按 D15 不入；多人同格注文不猜配；无标签年按行序推并标 review。",
        },
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    st = payload["meta"]["stats"]
    print(f"年页 {len([p for p in pages if args.from_year <= p['years'][0] <= args.to_year])}；"
          f"缺年 {missing or '无'}（空框 {len(empty_years)} / 丢表 {lost_years}）；重复年 {dupes or '无'}")
    print(f"条目 {st['entries']}；人数 {st['persons']}；有注 {st['with_note']}；待核 {st['review']}；警告 {st['warn']}")
    for w in all_warns[:12]:
        print("  ⚠", w)
    # 锚点抽印
    anchors = {"1393": ["冀凱"], "1397": ["仲旼", "劉繼宗"], "1413": ["梁質", "倪俊"],
               "1414": ["梁質", "李晟"], "1518": ["黃鐘", "邵錫", "邢寰"], "1644": []}
    for y, names in anchors.items():
        if args.from_year <= int(y) <= args.to_year and names:
            es = [e for e in entries if e["year"] == int(y)]
            tag = " ".join(f"{e['office']}:{e['person']}" for e in es)
            ok = all(any(n in e["person"] for e in es) for n in names)
            print(f"  锚点 {y} {'✓' if ok else '✗'} | {tag[:130]}")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
