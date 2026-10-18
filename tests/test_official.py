# -*- coding: utf-8 -*-
"""正式数据管线测试 v3（2026-10-17 数据重建）。

验证点：
  1. 重解析后的逐年名单（人-年）规模与连续性；
  2. 年度名单确实逐年（1436/1437/1515 等 OCR 旧缺块已修复）；
  3. D15 断限：1644 年三月后的南明任命全部剔除；
  4. 任职段：年份连续、月 ∈ [1,12] 或 None、无倒挂（month_conflict 除外）；
  5. CBDB ID 定点修复（楊士奇/楊溥/曹鼐/張孚敬/方逢年）；
  6. 导出 meta 溯源与 demo 隔离（D21）。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mingoff.official import (  # noqa: E402
    DATA,
    build_cabinet_tenures,
    build_shilu,
    export_official,
    load_entries,
)

SOUTHERN = {"高弘圖", "史可法", "馬士英", "王鐸", "姜曰廣", "方拱乾"}


def test_entries_scale_and_coverage():
    entries = load_entries()
    assert len(entries) > 1000, f"人-年 {len(entries)} 偏少（旧版仅 594）"
    years = {e["year"] for e in entries if 1402 <= e["year"] <= 1644}
    missing = [y for y in range(1402, 1645) if y not in years]
    assert not missing, f"缺年份 {missing}"


def test_entries_unique_person_year():
    """人名归一后同一人同年只能有一条（实测 1402 解縉、1441 曹鼐曾重复）。"""
    keys = [(e["year"], e["person"]) for e in load_entries()]
    assert len(keys) == len(set(keys)), "存在重复的 (year, person)"


def test_jiejin_1402_to_1407_continuous():
    """原书 1403 年有解縉（OCR 丢行，已按原书补）；解縉应为 1402–1407 单段。"""
    by_year = defaultdict(set)
    for e in load_entries():
        by_year[e["year"]].add(e["person"])
    assert "解縉" in by_year[1403]
    ts = [t for t in build_cabinet_tenures() if t["person"] == "解縉"]
    assert len(ts) == 1, ts
    assert (ts[0]["start_year"], ts[0]["start_month"]) == (1402, 8)
    assert (ts[0]["end_year"], ts[0]["end_month"]) == (1407, 2)
    assert ts[0]["years"] == [1402, 1403, 1404, 1405, 1406, 1407]


def test_known_year_rosters_present():
    """旧解析器丢无注文行的三处典型：1436 張瑛、1437 全年、1515 全年。"""
    by_year = defaultdict(set)
    for e in load_entries():
        by_year[e["year"]].add(e["person"])
    assert {"楊士奇", "楊榮", "楊溥", "張瑛"} <= by_year[1436]
    assert {"楊士奇", "楊榮", "楊溥"} <= by_year[1437]
    assert {"楊廷和", "梁儲", "靳貴", "楊一清"} <= by_year[1515]


def test_merged_year_header_repairs():
    """OCR 把下一年的年份头并进上一年的末行 → 末行人物被错归到下一年（2026-10-18 修）。

    实测：1440 曹鼐 / 1571 殷士儋 / 1583 許國 / 1616 吳道南；
    另有永乐十年（1412）胡廣的裸名行被挪到 1411 年末（按原书 p19 补录）。
    """
    by_year = defaultdict(set)
    for e in load_entries():
        by_year[e["year"]].add(e["person"])
    assert "曹鼐" in by_year[1440]
    assert "胡廣" in by_year[1412]
    assert "殷士儋" in by_year[1571]
    assert "許國" in by_year[1583]
    assert "吳道南" in by_year[1616]

    ts = {t["person"]: t for t in build_cabinet_tenures()}
    assert (ts["曹鼐"]["start_year"], ts["曹鼐"]["start_month"]) == (1440, 2)
    assert ts["胡廣"]["years"] == list(range(1402, 1419))
    assert (ts["殷士儋"]["start_year"], ts["殷士儋"]["end_year"]) == (1570, 1571)
    assert ts["許國"]["start_year"] == 1583


def test_wu_daonan_single_tenure_1613_1617():
    """吳道南：原书万历四十四年（1616）仍在阁，四十五年七月丁憂。

    旧数据因 1616 被吞进 1617 年份头，截到 1615，并留下 1617 孤立丁憂事件。
    """
    ts = [t for t in build_cabinet_tenures() if t["person"] == "吳道南"]
    assert len(ts) == 1, ts
    t = ts[0]
    assert (t["start_year"], t["start_month"]) == (1613, 9)
    assert (t["end_year"], t["end_month"]) == (1617, 7)
    assert t["leave"] == "丁憂"
    assert t["years"] == [1613, 1614, 1615, 1616, 1617]


def test_caoding_died_at_tumu():
    """曹鼐 1440 入阁、1449 土木之变死难（注文「死於難」→ 迄月 8）。"""
    ts = [t for t in build_cabinet_tenures() if t["person"] == "曹鼐"]
    assert len(ts) == 1, ts
    t = ts[0]
    assert (t["start_year"], t["start_month"]) == (1440, 2)
    assert (t["end_year"], t["end_month"]) == (1449, 8)
    assert t["leave"] == "死於難"


def test_only_neige_office():
    ts = build_cabinet_tenures()
    assert ts, "内阁段不应为空"
    assert all(t["office"] == "內閣" for t in ts)
    assert all(t["tenure_type"] == "实授" for t in ts)


def test_scale_and_continuity():
    ts = build_cabinet_tenures()
    # 旧版 360 段（事件碎片）→ 重解析后约 198 段连续任期
    assert 150 <= len(ts) <= 260, len(ts)
    assert sum(len(t["years"]) for t in ts) > 1000
    for t in ts:
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
            continue
        if t["start_month"] and t["end_month"]:
            assert (t["start_year"], t["start_month"]) <= (t["end_year"], t["end_month"]), t


def test_d15_cutoff_and_southern_ming_removed():
    ts = build_cabinet_tenures()
    for t in ts:
        assert (t["start_year"], t["start_month"] or 1) <= (1644, 3), t
        assert t["end_year"] <= 1644
        if t["end_year"] == 1644:
            assert t["end_month"] in (None, 1, 2, 3), t
    persons = {t["person"] for t in ts}
    assert not (SOUTHERN & persons), f"南明人物未剔除: {SOUTHERN & persons}"
    # 王應熊只保留 1633/1635/1642 的崇祯朝段，1644-08 段剔除
    wang = [t for t in ts if t["person"] == "王應熊"]
    assert wang and all(not (t["start_year"] == 1644) for t in wang), wang


def test_known_figures_continuous():
    ts = build_cabinet_tenures()
    by = defaultdict(list)
    for t in ts:
        by[t["person"]].append(t)
    assert len(by["楊士奇"]) == 1
    assert (by["楊士奇"][0]["start_year"], by["楊士奇"][0]["end_year"]) == (1402, 1444)
    assert (by["張居正"][0]["start_year"], by["張居正"][0]["end_year"]) == (1567, 1582)
    # 張瑛：1426–1429（改南京）与 1434–1436 两段
    zy = sorted((t["start_year"], t["end_year"]) for t in by["張瑛"])
    assert zy == [(1426, 1429), (1434, 1436)], zy
    # 嚴嵩、徐階 单段连续
    assert [(t["start_year"], t["end_year"]) for t in by["嚴嵩"]] == [(1542, 1562)]
    assert [(t["start_year"], t["end_year"]) for t in by["徐階"]] == [(1552, 1568)]


def test_cbdb_ids_fixed():
    ts = {t["person"]: t for t in build_cabinet_tenures()}
    assert ts["楊士奇"]["cbdb_id"] == 66729  # CBDB 作「楊寓」
    assert ts["楊士奇"]["cbdb_name"] == "楊寓"
    assert ts["楊溥"]["cbdb_id"] == 66746   # 旧挂 199050（无任职记录）
    assert ts["曹鼐"]["cbdb_id"] == 67222   # 旧挂 199155（错误同名）
    assert ts["張孚敬"]["cbdb_id"] == 68266  # CBDB 作「張璁」
    assert ts["方逢年"]["cbdb_id"] == 339044  # 旧挂 38925（方椿年）


def test_confidence_bounds():
    for t in build_cabinet_tenures():
        assert 0 < t["confidence"] <= 0.8


def test_export_meta_traceability():
    doc = export_official()
    m = doc["meta"]
    assert m["dataset"] == "mingoff-cabinet"
    assert m["version"] == 3
    assert m["canvas_from"] == 1368
    assert "张德信" in m["source"]
    assert m["stats"]["tenures"] == len(doc["tenures"]) > 0
    assert m["stats"]["persons"] == len({t["person"] for t in doc["tenures"]})
    assert m["stats"]["person_years"] > 1000


def test_demo_merge_data_not_required():
    """D21：正式管线输入只有重解析条目 + CBDB 映射，不引用 demo 合并产物。"""
    import mingoff.official as off
    src = Path(off.__file__).read_text(encoding="utf-8")
    for banned in ("demo-data", "demo_data", "tenures_with_sinica", "merge_demo"):
        assert banned not in src, f"正式管线引用了 demo 数据: {banned}"


def test_shilu_hits_are_relevant_and_bounded():
    doc = export_official()
    tenures = doc["tenures"]
    persons = {t["person"] for t in tenures}
    assert "shilu" in doc
    for person, blk in doc["shilu"].items():
        assert person in persons
        assert blk["count"] >= len(blk["hits"]) >= 1
        assert len(blk["hits"]) <= 8
        wins = [(t["start_year"] - 1, t["end_year"] + 1)
                for t in tenures if t["person"] == person]
        for h in blk["hits"]:
            assert any(lo <= h["year"] <= hi for lo, hi in wins), (person, h["year"])
            assert h["source"] and h["content"]
            assert h["month"] is None or 1 <= h["month"] <= 12
