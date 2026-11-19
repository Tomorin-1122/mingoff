# -*- coding: utf-8 -*-
"""总督年表任职段（official_zongdu）校验 + 解析锚点。"""
import json
from pathlib import Path

import pytest

from mingoff import official_zongdu as ozd

DATA = Path(ozd.DATA)
has_asset = (DATA / "vol3_zongdu_entries.json").is_file() and \
            (DATA / "official_zongdu.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="总督数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_zongdu.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 750
    span = (min(t["start_year"] for t in tenures),
            max(t["end_year"] for t in tenures))
    assert span == (1449, 1644), span


def test_region_offices(tenures):
    """区域带正名覆盖主要总督辖区（剥前缀后按印本）。"""
    offices = {t["office"] for t in tenures}
    for r in ("兩廣", "宣大", "薊遼", "漕運", "陕西三邊", "貴州", "京師", "河道"):
        assert r in offices, r


def test_anchors(tenures):
    def segs(who, off):
        return [t for t in tenures if t["person"] == who and t["office"] == off]

    # 侯璡：正统十四年十一月兵部左侍郎总督贵州军务
    assert any(t["start_year"] == 1449 and t["start_month"] == 11
               for t in segs("侯璡", "貴州"))
    # 于謙：正统十四年八月兵部尚书总督京师营务（至天顺元年）
    yu = segs("于謙", "京師")
    assert any(t["start_year"] == 1449 and t["start_month"] == 8
               and t["end_year"] == 1457 for t in yu)
    # 李蕙：弘治七年十一月总督漕运（两行纵排标签拼接锚点）
    assert any(t["start_year"] == 1494 and t["start_month"] == 11
               for t in segs("李蕙", "漕運"))
    # 蕭大亨 宣大；葉夢熊 陝西三邊（单字 2×2 网格拼接锚点）
    assert any(t["start_year"] == 1589 for t in segs("蕭大亨", "宣大"))
    # 归一后 陝西三邊/陕西三邊 两变体段合并，任期延至 1595
    assert any(t["start_year"] == 1592 and t["end_year"] == 1595
               for t in segs("葉夢熊", "陕西三邊"))
    # 孫鑛 薊遼 1594
    assert any(t["start_year"] == 1594 and t["start_month"] == 7
               for t in segs("孫鑛", "薊遼"))


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t


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
            assert t["end_month"] <= 3, t


def test_page_traceable(tenures):
    """书页 = PDF+2215（2320–2524）；跨页年 start≤end。"""
    for t in tenures:
        assert t["start_book_page"] and t["end_book_page"], t
        assert 2320 <= t["start_book_page"] <= t["end_book_page"] <= 2524, t


def test_no_overlap_same_office(tenures):
    seen = {}
    for t in tenures:
        key = (t["person_id"], t["office"])
        assert key not in seen or t["start_year"] > seen[key], t
        seen[key] = t["end_year"]


def test_audit_clean():
    r = ozd.audit()
    assert not r["blockers"], r["blockers"]
