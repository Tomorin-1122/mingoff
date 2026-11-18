# -*- coding: utf-8 -*-
"""总督京营戎政大臣任职段（official_jingying）校验 + 试点锚点。"""
import json
from pathlib import Path

import pytest

from mingoff import official_jingying as ojy

DATA = Path(ojy.DATA)
has_asset = (DATA / "vol3_jingying_entries.json").is_file() and \
            (DATA / "official_jingying.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="京营数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_jingying.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 300
    span = (min(t["start_year"] for t in tenures),
            max(t["end_year"] for t in tenures))
    assert span == (1550, 1644), span


def test_office_set(tenures):
    assert {t["office"] for t in tenures} == {
        "總督京營戎政", "協理京營戎政", "五軍營", "三千營", "神樞營", "神機營",
        "京營參將"}


def test_band_slot_exclusive(tenures):
    """三千營/神樞營 同槽异名（书本身混印：1570 起即见神樞營标签，非 1588 硬切换）——
    按印本如实分立；同一年同槽只允许出现一个标签名（人数不限）。"""
    for y in range(1550, 1645):
        names = {t["office"] for t in tenures
                 if t["office"] in ("三千營", "神樞營")
                 and t["start_year"] <= y <= t["end_year"]}
        assert len(names) <= 1, (y, names)


def test_anchors(tenures):
    def segs(who, off):
        return [t for t in tenures if t["person"] == who and t["office"] == off]

    # 仇鸞：嘉靖廿九年九月首任總督京營戎政，三十一年卒（庚戌之变后置）
    qiu = segs("仇鸞", "總督京營戎政")
    assert any(t["start_year"] == 1550 and t["start_month"] == 9
               and t["end_year"] == 1552 and t["leave"] == "死" for t in qiu)
    # 王邦瑞：协理京营戎政首任（兵部侍郎赞理）
    assert any(t["person"] == "王邦瑞" and t["office"] == "協理京營戎政"
               and t["start_year"] == 1550 for t in tenures)
    # 李邦珍型倒不用；甲申段：李國楨 1643 起总督、趙之龍 1644 三月降
    li = segs("李國楨", "總督京營戎政")
    assert any(t["start_year"] == 1643 and t["end_year"] == 1644
               and t["end_clamped"] for t in li)
    zhao = segs("趙之龍", "總督京營戎政")
    assert any(t["start_year"] == 1644 and t["leave"] == "降職"
               and t["start_month"] == 3 for t in zhao)
    # 傅希摯 1587 起协理；京營參將带（p45 型 schema 新增）有段
    assert any(t["person"] == "傅希摯" and t["office"] == "協理京營戎政"
               and t["start_year"] == 1587 for t in tenures)
    assert any(t["person"] == "郭三翰" and t["office"] == "京營參將"
               and t["start_year"] == 1588 for t in tenures)


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
    """页级溯源：书页 = PDF+2215，1550→2222 … 1644→2316。"""
    for t in tenures:
        assert t["start_book_page"] == t["start_year"] + 672, t
        assert 2222 <= t["start_book_page"] <= 2318, t


def test_no_overlap_same_office(tenures):
    seen = {}
    for t in tenures:
        key = (t["person_id"], t["office"])
        assert key not in seen or t["start_year"] > seen[key], t
        seen[key] = t["end_year"]


def test_audit_clean():
    r = ojy.audit()
    assert not r["blockers"], r["blockers"]
