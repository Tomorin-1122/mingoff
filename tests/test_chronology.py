# -*- coding: utf-8 -*-
"""纪年测试：干支、年号、虚岁、断限。

干支容易算错且错了不易发现（一年错全年错），所以逐个对《明史》年表标题校验。
"""
from __future__ import annotations

import pytest

from mingoff import chronology as C


# ---------------------------------------------------------------- 干支


@pytest.mark.parametrize(
    "year,expected",
    [
        (1628, "戊辰"),   # 崇祯元年 —— 《明史》卷112 标题「崇禎元年戊辰」
        (1629, "己巳"),   # 二年己巳
        (1630, "庚午"),   # 三年庚午
        (1631, "辛未"),
        (1632, "壬申"),
        (1633, "癸酉"),
        (1634, "甲戌"),
        (1635, "乙亥"),
        (1636, "丙子"),   # 九年丙子
        (1637, "丁丑"),
        (1638, "戊寅"),
        (1639, "己卯"),
        (1640, "庚辰"),
        (1641, "辛巳"),
        (1642, "壬午"),
        (1643, "癸未"),
        (1644, "甲申"),   # 十七年甲申 —— 崇祯自缢之年
    ],
)
def test_ganzhi_matches_mingshi_headings(year: int, expected: str):
    """干支必须与《明史》卷112 各年标题一致。

    这 17 个值不是随手写的 —— 它们是《明史》七卿年表每一年的标题里的干支，
    所以这条测试等于拿正史原文做了 17 次校验。
    """
    assert C.ganzhi(year) == expected


def test_ganzhi_cycles_every_60():
    assert C.ganzhi(1628) == C.ganzhi(1628 + 60)
    assert C.ganzhi(1644) == C.ganzhi(1644 - 60)


def test_ganzhi_known_anchors():
    """其他已知锚点，跨朝代校验算法正确性。"""
    assert C.ganzhi(1911) == "辛亥"   # 辛亥革命
    assert C.ganzhi(1894) == "甲午"   # 甲午战争
    assert C.ganzhi(1900) == "庚子"   # 庚子事变


# ---------------------------------------------------------------- 年号


@pytest.mark.parametrize(
    "year,expected",
    [
        (1628, "崇禎元年"),
        (1629, "崇禎二年"),
        (1636, "崇禎九年"),
        (1637, "崇禎十年"),
        (1641, "崇禎十四年"),
        (1644, "崇禎十七年"),
    ],
)
def test_era_label(year: int, expected: str):
    assert C.era_label(year) == expected


def test_era_label_out_of_range():
    assert C.era_label(1627) is None
    assert C.era_label(1645) is None


def test_full_label_combines_era_and_ganzhi():
    """老板要求的顶部格式：「崇祯二年己巳」。"""
    assert C.full_label(1629) == "崇禎二年己巳"
    assert C.full_label(1644) == "崇禎十七年甲申"


# ---------------------------------------------------------------- 周岁（老板拍板：不用虚岁）


def test_age_zhousui_at_chongzhen_years():
    """崇祯元年 17 岁（周岁，2 月生日已过口径）、十七年 33 岁。"""
    assert C.age_zhousui(1628, 2) == 17
    assert C.age_zhousui(1644, 2) == 33


def test_age_zhousui_january_is_conservative():
    """公历 1 月未过生日（2-06），按未满周岁计。"""
    assert C.age_zhousui(1628, 1) == 16


def test_age_zhousui_no_month_uses_full_year():
    """史料只到年时按生日已过计。"""
    assert C.age_zhousui(1628) == 17


def test_age_zhousui_increases_annually():
    for y in range(1612, 1650):
        assert C.age_zhousui(y + 1, 2) - C.age_zhousui(y, 2) == 1


# ---------------------------------------------------------------- 年表


def test_year_table_covers_full_span():
    t = C.year_table()
    assert len(t) == 17
    assert t[0]["year"] == 1628
    assert t[-1]["year"] == 1644


def test_year_table_rows_are_complete():
    for r in C.year_table():
        assert r["era"] and r["ganzhi"] and r["full"]
        assert r["age_su"] > 0
        assert r["emperor"] == "朱由檢"

def test_year_table_custom_range():
    t = C.year_table(1636, 1638)
    assert [r["year"] for r in t] == [1636, 1637, 1638]


# ---------------------------------------------------------------- 断限


def test_beijing_fall_is_chongzhen_17_3():
    """老板拍板的断限：崇祯十七年三月十九日（1644-04-25）北京城陷落，不做南明。"""
    f = C.BEIJING_FALL
    assert f["year"] == 1644
    assert f["month"] == 3
    assert f["day"] == 19
    assert f["gregorian"] == "1644-04-25"


def test_emperor_dates_are_consistent():
    e = C.EMPEROR
    assert e["era"] == "崇禎"
    assert e["born_gregorian"] == C.date(1611, 2, 6)
    assert e["enthroned_year"] == 1627   # 天启七年八月即位
    assert e["era_start"] == 1628        # 次年改元
