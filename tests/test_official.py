# -*- coding: utf-8 -*-
"""正式数据管线测试（D21）：official.py 从年表源提取物重建内阁段。

验证点：
  1. 只含內閣段（殿閣/翰林院台阶官不得混入）
  2. 每段可溯源：note 为年表原文、verbs 有值
  3. NULL 纪律：月可为 None，但绝不出现 0（D4）
  4. 不臆造：同年边界多月冲突 → month 为 None（D20）
  5. 结构完整性：年份连续段、无倒挂（month_conflict 除外）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mingoff.official import build_cabinet_tenures, export_official, norm_verb


def test_only_neige_section():
    ts = build_cabinet_tenures()
    assert ts, "内阁段不应为空"
    assert all(t["office"] == "內閣" for t in ts)


def test_years_are_contiguous_segments():
    """段内 years 必须连续递增（年在位体切段的定义）。"""
    for t in build_cabinet_tenures():
        ys = t["years"]
        assert ys == sorted(ys)
        assert all(b == a + 1 for a, b in zip(ys, ys[1:])), t
        assert ys[0] == t["start_year"] and ys[-1] == t["end_year"]


def test_month_is_null_or_1_12_never_zero():
    for t in build_cabinet_tenures():
        for m in (t["start_month"], t["end_month"]):
            assert m is None or 1 <= m <= 12, (t["person"], m)


def test_no_time_inversion_unless_flagged():
    for t in build_cabinet_tenures():
        if t["month_conflict"]:
            continue  # 单年段并格，已显式标记
        if t["start_month"] and t["end_month"]:
            assert (t["start_year"], t["start_month"]) <= (t["end_year"], t["end_month"]), t


def test_confidence_bounds():
    for t in build_cabinet_tenures():
        assert 0 < t["confidence"] <= 0.8


def test_known_figures_present():
    """抽查名人（来源：年表册1）。⚠️ 实测发现：年表对「常年在任者」并非逐年
    列名（楊士奇 1403/1405–06 等年份缺行，張居正 1568–69/1572–75 空档），
    装配按源忠实切段、**不填补空档**（D4）。故此处只验证存在性与锚点年份。"""
    ts = {t["person"]: t for t in build_cabinet_tenures()}
    assert "楊士奇" in ts
    # 楊士奇有 1402（永乐入阁起点年）与 1444（正统末年）的段
    assert any(t["start_year"] <= 1402 for t in build_cabinet_tenures()
               if t["person"] == "楊士奇")
    # 張居正：1570 入阁前的段在，1582（万历十年卒）有段终点
    zjz_segs = [t for t in build_cabinet_tenures() if t["person"] == "張居正"]
    assert any(t["end_year"] == 1582 for t in zjz_segs), zjz_segs
    assert any(t["start_year"] <= 1570 for t in zjz_segs)


def test_segments_match_source_presence():
    """段的在任年集合必须与源条目逐年一致（不添加不删除）。"""
    import json
    from pathlib import Path
    from mingoff.official import DATA
    entries = json.loads((DATA / "neige_entries_aligned.json").read_text(encoding="utf-8"))
    src_years = {}
    for e in entries:
        if e.get("section") == "內閣":
            src_years.setdefault(e["person"], set()).add(e["year"])
    built = {}
    for t in build_cabinet_tenures():
        built.setdefault(t["person"], set()).update(t["years"])
    assert built == src_years, "装配必须与源逐年一致"


def test_export_meta_traceability():
    doc = export_official()
    m = doc["meta"]
    assert m["dataset"] == "mingoff-cabinet"
    assert "张德信" in m["source"] and "neige_" in m["source"]
    assert m["stats"]["tenures"] == len(doc["tenures"]) > 0
    assert m["stats"]["persons"] == len({t["person"] for t in doc["tenures"]})


def test_demo_merge_data_not_required():
    """D21：正式管线输入只有两份源提取物——merge 产物不在依赖里。"""
    import mingoff.official as off
    src = Path(off.__file__).read_text(encoding="utf-8")
    for banned in ("demo-data", "demo_data", "tenures_with_sinica", "merge_demo"):
        assert banned not in src, f"正式管线引用了 demo 数据: {banned}"


def test_norm_verb_patterns():
    assert norm_verb("", "禮尚兼東閣大學士入") == "enter"
    assert norm_verb("罷") == "leave"
    assert norm_verb("卒于任") == "leave"
    assert norm_verb("贈") == "other"


def test_tenure_type_is_honest():
    """内阁年表不区分实授/署理/加衔 → 一律实授，不臆造（D4 精神）。"""
    for t in build_cabinet_tenures():
        assert t["tenure_type"] == "实授"
        assert isinstance(t["leave"], str) and t["leave"]


def test_leave_reason_comes_from_verbs():
    for t in build_cabinet_tenures():
        if t["leave_verbs"]:
            assert t["leave"] != "未載"
            # 动词直译：任一原始动词必须体现在离任文本里（映射外的原样保留）
            assert any(v in t["leave"] for v in t["leave_verbs"]), t
        else:
            assert t["leave"] == "未載"


def test_notes_are_cleaned_of_ocr_title_lines():
    """源注文混入 '# 明代職官年表' 之类 OCR 标题行，导出前必须清掉。"""
    for t in build_cabinet_tenures():
        assert "#" not in t["note"], t["person"]
        assert t["note"] == t["note"].strip()


def test_shilu_hits_are_relevant_and_bounded():
    doc = export_official()
    assert doc["meta"]["version"] == 2
    assert "shilu" in doc
    persons = {t["person"] for t in doc["tenures"]}
    for person, blk in doc["shilu"].items():
        assert person in persons
        assert blk["count"] >= len(blk["hits"]) >= 1
        assert len(blk["hits"]) <= 8
        wins = [(t["start_year"] - 1, t["end_year"] + 1)
                for t in doc["tenures"] if t["person"] == person]
        for h in blk["hits"]:
            assert any(lo <= h["year"] <= hi for lo, hi in wins), (person, h["year"])
            assert h["source"] and h["content"]
            assert h["month"] is None or 1 <= h["month"] <= 12
