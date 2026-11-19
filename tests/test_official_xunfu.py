# -*- coding: utf-8 -*-
"""巡抚年表任职段（official_xunfu）校验 + 解析锚点。"""
import json
from pathlib import Path

import pytest

from mingoff import official_xunfu as oxf

DATA = Path(oxf.DATA)
has_asset = (DATA / "vol3_xunfu_entries.json").is_file() and \
            (DATA / "official_xunfu.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="巡抚数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_xunfu.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 3000
    span = (min(t["start_year"] for t in tenures),
            max(t["end_year"] for t in tenures))
    assert span == (1430, 1644), span


def test_region_offices(tenures):
    offices = {t["office"] for t in tenures}
    for r in ("江西", "浙江", "湖廣", "河南山西", "北直隸山東", "南直隸蘇松",
              "宣府", "大同", "遼東", "陕西", "應天"):
        assert r in offices, r


def test_anchor_1430_six_xunfu(tenures):
    """宣德五年六巡抚（明史著名任命）：九月丙午同日赴任。"""
    def seg(who):
        return [t for t in tenures if t["person"] == who
                and t["start_year"] == 1430]
    # 同带首条带「九、丙午、八」注文，余人月空——衙署归属为断言主体
    assert any(t["office"] == "江西" for t in seg("趙新"))
    assert any(t["office"] == "浙江" for t in seg("趙倫"))
    assert any(t["office"] == "湖廣" for t in seg("吴政"))
    assert any(t["office"] == "河南山西" for t in seg("于謙"))
    assert any(t["office"] == "北直隸山東" for t in seg("曹弘"))
    assert any(t["office"] == "南直隸蘇松" for t in seg("周忱"))


def test_anchor_xuanshengyuye(tenures):
    # 葉盛 巡抚宣府（天顺三年 1459 在任）
    assert any(t["office"] == "宣府" and t["start_year"] <= 1459 <= t["end_year"]
               for t in tenures if t["person"] == "葉盛")


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t


def test_month_rules(tenures):
    for t in tenures:
        for k in ("start_month", "end_month"):
            assert t[k] is None or 1 <= t[k] <= 12, t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["start_year"] == 1644:
            assert (t["start_month"] or 1) <= 3, t


def test_page_traceable(tenures):
    for t in tenures:
        assert t["start_book_page"] and t["end_book_page"], t
        assert 2526 <= t["start_book_page"] <= t["end_book_page"] <= 2922, t


def test_no_overlap_same_office(tenures):
    seen = {}
    for t in tenures:
        key = (t["person_id"], t["office"])
        assert key not in seen or t["start_year"] > seen[key], t
        seen[key] = t["end_year"]


def test_audit_clean():
    r = oxf.audit()
    assert not r["blockers"], r["blockers"]
