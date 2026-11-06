# -*- coding: utf-8 -*-
"""生成部院人工校对台（本地工具）。

产物（默认 _proofread/，已 gitignore，不进公开仓）：
  index.html     单文件校对台（数据内嵌）
  pages/p<书页>.jpg  原书扫描页（按需渲染，已存在则跳过）

用法：
  python scripts/build_proofread.py                 # 生成 html + 渲染缺失页图
  python scripts/build_proofread.py --no-pages      # 只重建 html
  python scripts/build_proofread.py --years 1368,1369 --no-pages
  python scripts/build_proofread.py --force-pages   # 重渲全部页图

页图渲染依赖 PyMuPDF（隔离环境）：
  %LOCALAPPDATA%\\..\\ .workbuddy\\binaries\\python\\envs\\proofread\\Scripts\\python.exe
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
OUT = ROOT / "_proofread"
TPL = ROOT / "scripts" / "proofread_template.html"

DEFAULT_PDF = Path(
    r"D:\北山研史\明代职官\明代职官年表_第1册_(张德信著)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"
)

# 年号（起始年, 结束年, 名称）；1457 归天顺（正月复辟改元）
ERAS = [
    (1368, 1398, "洪武"), (1399, 1402, "建文"), (1403, 1424, "永樂"),
    (1425, 1425, "洪熙"), (1426, 1435, "宣德"), (1436, 1449, "正統"),
    (1450, 1457, "景泰"), (1457, 1464, "天順"), (1465, 1487, "成化"),
    (1488, 1505, "弘治"), (1506, 1521, "正德"), (1522, 1566, "嘉靖"),
    (1567, 1572, "隆慶"), (1573, 1620, "萬曆"), (1621, 1627, "天啟"),
    (1628, 1644, "崇禎"),
]

CN_NUM = "〇一二三四五六七八九"


def era_label(year: int) -> str:
    """返回「萬曆二十七年」式年号年。"""
    # 1457 特殊：天順元年
    for start, end, name in ERAS:
        if name == "萬曆" and 1620 == year:
            continue  # 1620 归泰昌前的万历四十八年（见下）
        if start <= year <= end:
            n = year - start + 1
            if name == "景泰" and year == 1457:
                return "景泰八年／天順元年"
            return f"{name}{cn_num(n)}年"
    if year == 1620:
        return "萬曆四十八年／泰昌元年"
    return str(year)


def cn_num(n: int) -> str:
    if n <= 10:
        return "元" if n == 1 else CN_NUM[n] if n < 10 else "十"
    if n < 20:
        return "十" + CN_NUM[n - 10]
    t, u = divmod(n, 10)
    return CN_NUM[t] + "十" + (CN_NUM[u] if u else "")


OFFICE_ORDER = [
    "吏部", "戶部", "禮部", "兵部", "刑部", "工部",
    "都察院", "御史臺", "御史府",
    "總督京儲", "總督倉場", "總倉場",
]

# office_status → 展示用 CSS 类
STATUS_CLS = {
    "page-verified": "page", "name-anchor": "anchor", "row-order": "row",
    "mixed": "mix", "null": "null",
}

# 条目 flag → 中文短标签（校对台直接显示，避免露内部代号）
FLAG_CN = {
    "office重复": "衙署重複",
    "note?": "注文待核",
    "③顺序兜底": "行序兜底",
    "dup": "重複條目",
}


def flag_label(flag: str | None) -> str | None:
    if not flag:
        return None
    out: list[str] = []
    for part in flag.split(";"):
        part = part.strip()
        if not part:
            continue
        cn = FLAG_CN.get(part, part)
        if cn not in out:
            out.append(cn)
    return "／".join(out) if out else None



def load(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def build_tenure_index(official: dict) -> dict:
    """(year, person_id, office) → tenure 摘要（取覆盖该年的第一条）。"""
    idx: dict[tuple[int, str, str], dict] = {}
    for t in official["tenures"]:
        pid = t.get("person_id") or t.get("person")
        office = t.get("office") or ""
        summ = {
            "status": t.get("office_status"),
            "conf": t.get("confidence"),
            "type": t.get("tenure_type"),
            "leave": t.get("leave"),
            "start": (t.get("start_year"), t.get("start_month")),
            "end": (t.get("end_year"), t.get("end_month")),
        }
        for y in t.get("years") or []:
            idx.setdefault((y, pid, office), summ)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pages", action="store_true", help="只重建 html")
    ap.add_argument("--force-pages", action="store_true", help="重渲全部页图")
    ap.add_argument("--years", default="", help="只处理这些年份（逗号分隔，调试用）")
    ap.add_argument("--pdf", default=str(DEFAULT_PDF))
    ap.add_argument("--width", type=int, default=1200, help="页图目标宽度（像素）")
    ap.add_argument("--quality", type=int, default=82, help="JPEG 质量")
    args = ap.parse_args()

    entries = load("vol1_buyuan_entries_v2.json")
    pages = load("vol1_buyuan_pages.json")
    official = load("official_buyuan.json")
    d11 = load("vol1_buyuan_d11_review.json")

    tindex = build_tenure_index(official)
    unlabeled = set(d11["meta"].get("unlabeled_years") or [])

    # D11 按年归并
    d11_by_year: dict[int, list] = {}
    for r in d11["rows"]:
        d11_by_year.setdefault(r["year"], []).append(r)

    # 页映射：兼容 {year: {pdf_page, book_page}} 与 [{"year":..}] 两种形态
    page_map: dict[int, dict] = {}
    if isinstance(pages, dict):
        for k, v in pages.items():
            try:
                page_map[int(k)] = v
            except (TypeError, ValueError):
                continue
    elif isinstance(pages, list):
        for v in pages:
            if "year" in v:
                page_map[int(v["year"])] = v

    # 条目按 (年, 衙) 分组，并生成稳定 id
    by_year_office: dict[int, dict[str, list]] = {}
    for e in entries:
        y, office, person = int(e["year"]), e.get("office") or "", e.get("person") or ""
        by_year_office.setdefault(y, {}).setdefault(office, []).append(e)

    only_years = {int(x) for x in args.years.split(",") if x.strip().isdigit()}

    years_out = []
    for y in sorted(by_year_office):
        if only_years and y not in only_years:
            continue
        pm = page_map.get(y) or {}
        book = int(pm.get("book_page") or pm.get("book") or 0)
        pdf = int(pm.get("pdf_page") or pm.get("pdf") or (book + 15 if book else 0))
        if not book:
            print(f"[warn] {y} 无页码，跳过", file=sys.stderr)
            continue

        offices = []
        counters: dict[tuple[str, str], int] = {}
        total = 0
        row_order_n = 0
        flag_n = 0
        for office in sorted(
            by_year_office[y],
            key=lambda o: OFFICE_ORDER.index(o) if o in OFFICE_ORDER else 99,
        ):
            rows = []
            for e in by_year_office[y][office]:
                person = e.get("person") or ""
                pid = e.get("person_id") or person
                key = (office, person)
                n = counters.get(key, 0)
                counters[key] = n + 1
                tid = f"{y}|{office}|{person}|{n}"
                t = tindex.get((y, pid, office)) or {}
                status = t.get("status")
                if status in ("row-order", "null"):
                    row_order_n += 1
                flag = e.get("flag")
                if flag:
                    flag_n += 1
                rows.append({
                    "id": tid,
                    "p": person,
                    "note": e.get("note") or "",
                    "st": {"v": status, "cls": STATUS_CLS.get(status, "null")} if status else None,
                    "conf": t.get("conf"),
                    "flag": flag_label(flag),
                })
                total += 1
            offices.append({"n": office, "rows": rows})

        # 风险分与标签
        risk = 0
        tags = []
        if y in unlabeled:
            risk += 3
            tags.append("本頁無衙署名（須對照鄰頁）")
        low = [r for r in d11_by_year.get(y, []) if (r.get("conf") or 0) < 0.9]
        if low:
            risk += min(len(low), 4)
            tags.append(f"{len(low)} 行行序推斷待核")
        if row_order_n >= 3:
            risk += 2
            tags.append(f"{row_order_n} 條歸屬未定")
        elif row_order_n:
            risk += 1
            tags.append(f"{row_order_n} 條歸屬待核")
        if flag_n >= 5:
            risk += 1
            tags.append(f"{flag_n} 條重複/異常標記")

        years_out.append({
            "y": y,
            "era": era_label(y),
            "book": book,
            "pdf": pdf,
            "risk": risk,
            "tags": tags,
            "total": total,
            "offices": offices,
            "d11": [
                {
                    "row": r.get("row", 0),
                    "names": r.get("names") or [],
                    "cells": r.get("cells_head") or [],
                    "suggest": r.get("suggest_office") or "",
                    "conf": r.get("conf") or 0,
                }
                for r in d11_by_year.get(y, [])
                if (r.get("conf") or 0) < 0.9
            ],
        })

    # file:// PDF 链接（中文路径需百分号编码）
    from urllib.parse import quote
    pdf_uri = "file:///" + quote(str(Path(args.pdf).as_posix()).lstrip("/"), safe="/:()")
    book_year = {str(y["book"]): {"y": y["y"], "era": y["era"]} for y in years_out}
    payload = {"pdfBase": pdf_uri, "years": years_out, "bookYear": book_year}

    tpl = TPL.read_text(encoding="utf-8")
    if "/*__DATA__*/null" not in tpl:
        print("模板缺少 __DATA__ 占位符", file=sys.stderr)
        return 2
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")

    print(f"html: {OUT / 'index.html'}  ({len(html)/1024/1024:.2f} MB)")
    print(f"年份: {len(years_out)}  条目: {sum(y['total'] for y in years_out)}")
    print(f"PDF: {pdf_uri}")

    if args.no_pages:
        return 0

    # ── 渲页图 ──
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("\n[skip] 未安装 PyMuPDF，跳过页图渲染。"
              "\n  安装：python -m venv <env> && <env>/Scripts/pip install pymupdf", file=sys.stderr)
        return 0

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"\n[skip] PDF 不存在：{pdf_path}", file=sys.stderr)
        return 0

    OUT.joinpath("pages").mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    made = skipped = 0
    for y in years_out:
        book, pdf = y["book"], y["pdf"]
        dst = OUT / "pages" / f"p{book}.jpg"
        if dst.exists() and not args.force_pages:
            skipped += 1
            continue
        pix = doc.load_page(pdf - 1)
        zoom = args.width / pix.rect.width
        pixmap = pix.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pixmap.save(str(dst), jpg_quality=args.quality)
        made += 1
        if made % 20 == 0:
            print(f"  渲染 {made} 页…", flush=True)
    doc.close()
    total_mb = sum(f.stat().st_size for f in (OUT / "pages").glob("*.jpg")) / 1024 / 1024
    print(f"页图：新渲 {made}，跳过 {skipped}，目录合计 {total_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
