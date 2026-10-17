# -*- coding: utf-8 -*-
"""把数据库导出成 demo 用的内嵌 JSON。

demo 要能**双击打开、无网络也能跑**，所以数据必须内嵌进 HTML。
本模块负责把 `mingoff.sqlite` 转成前端友好的结构，并**保留不确定性字段**
（confidence / tenure_type / note），因为那正是本项目要展示的东西。

设计取舍：导出的 JSON 里 `start_year`/`end_year` 保持 `null` 而不是 0，
前端也按 null 渲染成空白 —— 缺载是信息，不是缺失数据。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

#: 年号纪年表（崇祯）。用于前端把公元年显示成「崇祯X年」。
#: 崇祯元年 = 1628。仅崇祯一朝，因为 demo 范围就是它。
CHONGZHEN_ERA_START = 1628
CHONGZHEN_ERA_END = 1644

#: 数字 → 汉字（用于"崇祯二年"这类显示）
_CN_DIGITS = "〇一二三四五六七八九"


def year_to_era(year: int) -> str | None:
    """公元年 → 年号纪年字符串。超出崇祯朝返回 None。"""
    if not (CHONGZHEN_ERA_START <= year <= CHONGZHEN_ERA_END):
        return None
    n = year - CHONGZHEN_ERA_START + 1
    if n == 1:
        return "崇祯元年"
    if n < 10:
        return f"崇祯{_CN_DIGITS[n]}年"
    if n < 20:
        return f"崇祯十{_CN_DIGITS[n - 10]}年" if n > 10 else "崇祯十年"
    tens, ones = divmod(n, 10)
    s = f"崇祯{_CN_DIGITS[tens]}十"
    if ones:
        s += _CN_DIGITS[ones]
    return s + "年"


def export(db_path: Path | str) -> dict:
    """从数据库导出 demo 数据。

    返回结构：
      {
        "meta": {...},
        "offices": [{"name","department","order"}],   # 用于前端固定行序
        "tenures": [{"office","person","start","end","type","leave","confidence","source","note"}]
      }
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        offices = [
            dict(r)
            for r in conn.execute(
                "SELECT office_id, office_chn, department, parent_office_id"
                " FROM office ORDER BY office_id"
            )
        ]
        rows = conn.execute(
            """
            SELECT t.tenure_id, t.start_year, t.end_year, t.start_month, t.end_month,
                   t.tenure_type, t.leave_reason, t.confidence, t.note,
                   o.office_chn AS office, o.department,
                   p.name_chn AS person, p.bio AS person_bio,
                   (SELECT GROUP_CONCAT(s.source_name, '、')
                      FROM tenure_source ts JOIN source s ON s.source_id = ts.source_id
                     WHERE ts.tenure_id = t.tenure_id) AS sources,
                   (SELECT s.url FROM tenure_source ts JOIN source s ON s.source_id = ts.source_id
                     WHERE ts.tenure_id = t.tenure_id AND s.url IS NOT NULL LIMIT 1) AS url
              FROM tenure t
              JOIN office o ON o.office_id = t.office_id
              JOIN person p ON p.person_id = t.person_id
             ORDER BY o.office_id, (t.start_year IS NULL), t.start_year, t.tenure_id
            """
        ).fetchall()
    finally:
        conn.close()

    tenures = []
    for r in rows:
        tenures.append(
            {
                "office": r["office"],
                "department": r["department"] or "",
                "person": r["person"],
                # 保持 None：前端渲染成空白，不编造
                "start": r["start_year"],
                "end": r["end_year"],
                "type": r["tenure_type"],
                "leave": r["leave_reason"],
                "confidence": r["confidence"],
                "source": r["sources"] or "",
                "url": r["url"] or "",
                "note": r["note"] or "",
            }
        )

    # 年份范围：从数据推出，不写死
    years = [t["start"] for t in tenures if t["start"]] + [
        t["end"] for t in tenures if t["end"]
    ]
    span = (min(years), max(years)) if years else (CHONGZHEN_ERA_START, CHONGZHEN_ERA_END)

    # 每个职位至少一条记录才出现在图里，避免空行
    used_offices = {t["office"] for t in tenures}
    office_list = []
    seen = set()
    for o in offices:
        name = o["office_chn"]
        if name in used_offices and name not in seen:
            seen.add(name)
            office_list.append(
                {"name": name, "department": o["department"] or "", "order": len(office_list)}
            )

    return {
        "meta": {
            "title": "明代职官数据库",
            "scope": f"崇祯朝 {span[0]}–{span[1]}",
            "year_min": span[0],
            "year_max": span[1],
            "count": len(tenures),
            "source_note": "据张德信《明代职官年表》口径；数据持续校订中",
            "caveat": "缺载处留空，不作填补；任期为约数，详见各条置信度",
        },
        "offices": office_list,
        "tenures": tenures,
    }


def _load_shilu() -> dict:
    """读《明实录》命中数据（缺文件时返回空 dict，demo 照常出图）。"""
    p = Path(__file__).resolve().parents[2] / "src" / "mingoff" / "data" / "sinica_months.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def build_html(root: Path, data: dict) -> Path:
    """把数据注入 HTML 模板，产出**可双击打开、断网可用**的单文件 demo。

    为什么内嵌数据而不是 fetch JSON：
    ① 本地 file:// 打开时 fetch 会被 CORS 拦掉；
    ② 评审 demo 时不该要求先起服务器。
    正式版会改成 API 拉取，这一步是 demo 专用。
    """
    from .chronology import year_table

    template = root / "web" / "demo.template.html"
    out = root / "web" / "demo.html"
    if not template.is_file():
        raise FileNotFoundError(f"模板不存在: {template}")

    html = template.read_text(encoding="utf-8")
    y0, y1 = data["meta"]["year_min"], data["meta"]["year_max"]

    payloads = {
        "__DEMO_DATA__": json.dumps(data, ensure_ascii=False),
        # 纪年表（干支/年号/周岁）由 Python 生成，前端不重写算法
        "__YEAR_TABLE__": json.dumps(
            year_table(y0, y1), ensure_ascii=False
        ),
        # 《明实录》命中（原文 + 月份），供抽屉直接贴原文
        "__SHILU_MONTHS__": json.dumps(
            _load_shilu(), ensure_ascii=False
        ),
    }
    for marker, payload in payloads.items():
        if marker not in html:
            raise ValueError(f"模板里找不到占位符 {marker}")
        # </script> 需转义，避免提前闭合 script 标签
        html = html.replace(marker, payload.replace("</", "<\\/"))

    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    """一步产出可双击打开的 demo。

    数据来源分两步：
      1. `export()` 从数据库导出（含兵部尚书的 ground truth）；
      2. `merge_demo_data` 把《明史》年表研究数据并进来。

    这里直接读**合并后**的数据集；若合并文件不存在，退化为只用数据库数据
    （这样即使没跑研究数据，demo 也能出图，只是官职少）。
    """
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[2]

    merged = root / "web" / "demo-data-merged.json"
    if not merged.is_file():
        print(f"[提示] 未找到合并数据 {merged.name}，尝试只用数据库数据。")
        print("       要含全部官职，先跑：python -m mingoff.merge_demo_data")
        db = root / "data" / "mingoff.sqlite"
        if not db.is_file():
            print(f"[错误] 数据库不存在: {db}（先跑 mingoff init && mingoff seed）")
            return 2
        data = export(db)
    else:
        data = json.loads(merged.read_text(encoding="utf-8"))

    json_out = root / "web" / "demo-data.json"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    html_out = build_html(root, data)
    size_kb = html_out.stat().st_size / 1024
    print(f"[完成] {data['meta']['count']} 条任职，{len(data['offices'])} 个官职，"
          f"年份 {data['meta']['year_min']}–{data['meta']['year_max']}")
    for o in data["offices"]:
        n = sum(1 for t in data["tenures"] if t["office"] == o["name"])
        print(f"    {o['name']:<16} {n} 条")
    print(f"       demo: {html_out}  ({size_kb:.0f} KB，双击即可打开)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
