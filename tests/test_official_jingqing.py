# -*- coding: utf-8 -*-
"""京卿任职段（official_jingqing）校验：G2/G3/G6-京卿版 + 锚点。"""
import json
from pathlib import Path

import pytest

from mingoff import official_jingqing as oj

DATA = Path(oj.DATA)
has_asset = (DATA / "vol1_jingqing_entries.json").is_file() and \
            (DATA / "official_jingqing.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="京卿数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_jingqing.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 1300
    assert sum(len(t["years"]) for t in tenures) >= 3100
    span = (min(t["start_year"] for t in tenures), max(t["end_year"] for t in tenures))
    assert span == (1368, 1644)


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t
        assert t["start_year"] == ys[0] and t["end_year"] == ys[-1]


def test_office_set(tenures):
    offices = {t["office"] for t in tenures}
    assert offices == {"通政使", "大理卿", "太常卿", "光祿卿", "太僕卿",
                       "鴻臚卿", "尚寶卿", "順天府府尹"}


def test_month_rules(tenures):
    for t in tenures:
        for k in ("start_month", "end_month"):
            assert t[k] is None or 1 <= t[k] <= 12, t
        if t["start_year"] == t["end_year"] and t["start_month"] and t["end_month"]:
            assert t["start_month"] <= t["end_month"] or t["month_conflict"], t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["start_year"] == 1644:
            assert (t["start_month"] or 1) <= 3, t
        if t["end_year"] == 1644 and t["end_month"] is not None:
            assert t["end_month"] <= 3 or t["leave"] == "殉難", t


def test_page_traceable(tenures):
    """页级溯源：全部段有起止正文页码（year→Paddle 页眉索引实测）。"""
    missing = [t for t in tenures
               if t.get("start_book_page") is None or t.get("end_book_page") is None]
    assert not missing, f"无页码段 {len(missing)}"
    for t in tenures:
        assert 981 <= t["start_book_page"] <= 1266, t


def test_identity_span(tenures):
    """D-01：同一 person_id 跨度 ≤80 年；同名分代实体带 person_label。"""
    span = {}
    for t in tenures:
        lo, hi = span.get(t["person_id"], (9999, 0))
        span[t["person_id"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    too_long = {p for p, (lo, hi) in span.items() if hi - lo > 80}
    assert not too_long, too_long
    for t in tenures:
        if "#" in t["person_id"]:
            assert t.get("same_name_risk") and t["person_label"] != t["person"]


def test_no_overlap_same_office(tenures):
    seen = {}
    for t in tenures:
        key = (t["person_id"], t["office"])
        assert key not in seen or t["start_year"] > seen[key], t
        seen[key] = t["end_year"]


def test_gap_merge_marked(tenures):
    for t in tenures:
        if t.get("gap_years"):
            assert t.get("merged_segments", 1) >= 2
            assert t["confidence"] <= 0.6


def test_anchors(tenures):
    def segs(who, off):
        return [t for t in tenures if t["person"] == who and t["office"] == off]

    cai = segs("蔡瑄", "通政使")
    assert any(t["start_year"] <= 1382 and t["end_year"] == 1387
               and t["leave"] == "卒于任" for t in cai)
    gao = segs("高(沈)禄", "通政使")
    assert any(t["start_year"] == 1498 and t["end_year"] == 1506
               and t["end_month"] == 11 and t["leave"] == "卒于任" for t in gao)
    yang = segs("楊思忠", "通政使")
    assert any(t["start_year"] == 1569 and t["end_year"] == 1570
               and t["end_month"] == 7 and t["leave"] == "遷除" for t in yang)
    li = segs("栗永禄", "順天府府尹")
    assert any(t["start_year"] == 1570 and t["start_month"] == 5
               and t["tenure_type"] == "实授" for t in li)
    ling = segs("凌義渠", "大理卿")
    assert any(t["start_year"] == 1643 and t["end_year"] == 1644
               and t["leave"] == "殉難" for t in ling)
    # 栗永禄同年历两衙：光祿卿与順天府府尹各自独立段（衙署不合并）
    assert segs("栗永禄", "光祿卿") and segs("栗永禄", "順天府府尹")


def test_cbdb_aligned(doc):
    """CBDB 对齐 v1（match_official_cbdb.py）：段级对齐量 + 已核实锚点 id。"""
    s = doc["meta"]["stats"]
    assert s["cbdb_aligned"] >= 700, s["cbdb_aligned"]

    def ids(who):
        return {t["cbdb_id"] for t in doc["tenures"]
                if t["person"] == who and t.get("cbdb_id")}

    # 凌義渠 34757：生卒 1593–1644 与史实吻合（甲申殉节），CBDB 任职含兵科給事中/大理寺卿
    assert ids("凌義渠") == {34757}
    # 丁啟濬 126319：exact-unique 唯一同名候选
    assert ids("丁啟濬") == {126319}
    # 曾秉正 66533：manual（CBDB 通政使 1377–1382 任职记录 + 卒 1382）
    assert 66533 in ids("曾秉正")


def test_audit_clean():
    r = oj.audit()
    assert not r["blockers"], r["blockers"]
