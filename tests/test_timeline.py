# -*- coding: utf-8 -*-
"""时间轴测试：每年 12 个月等宽、断限截断、位置换算。

老板要求"每年都要有 12 个月的刻度，每年的长度要一样"——
这是可验证的数学性质，值得用测试钉住。
"""
from __future__ import annotations

import pytest

from mingoff import timeline as T


@pytest.fixture
def tl() -> T.Timeline:
    return T.Timeline()


# ---------------------------------------------------------------- 等宽


def test_each_year_has_twelve_slots(tl: T.Timeline):
    assert tl.total_slots == tl.years * 12 == 17 * 12 == 204


def test_every_year_has_identical_width(tl: T.Timeline):
    """老板核心要求：每年长度一样。"""
    widths = []
    for y in range(tl.year_min, tl.year_max):
        widths.append(tl.year_tick_pct(y + 1) - tl.year_tick_pct(y))
    assert len(set(round(w, 9) for w in widths)) == 1, f"年宽不一致: {widths}"
    assert abs(widths[0] - 100 / 17) < 1e-9


def test_months_within_a_year_are_equal(tl: T.Timeline):
    """同一年内 12 个月格必须等宽。"""
    for y in (1628, 1636, 1644):
        ws = []
        for m in range(1, 12):
            ws.append(tl.month_tick_pct(y, m + 1) - tl.month_tick_pct(y, m))
        assert len(set(round(w, 9) for w in ws)) == 1


def test_year_starts_at_january(tl: T.Timeline):
    for y in range(tl.year_min, tl.year_max + 1):
        assert tl.year_tick_pct(y) == tl.month_tick_pct(y, 1)


# ---------------------------------------------------------------- 位置


def test_first_slot_is_zero_pct(tl: T.Timeline):
    assert tl.pct(tl.slot_of(1628, 1)) == 0.0


def test_last_slot_is_under_100_pct(tl: T.Timeline):
    p = tl.pct(tl.slot_of(1644, 12))
    assert 99.0 < p < 100.0


def test_months_map_to_expected_slots(tl: T.Timeline):
    assert tl.slot_of(1628, 1) == 0
    assert tl.slot_of(1628, 5) == 4
    assert tl.slot_of(1629, 1) == 12
    assert tl.slot_of(1644, 3) == 16 * 12 + 2


def test_month_none_means_year_start_or_end(tl: T.Timeline):
    """月份未载时：起点算年初、终点算年末 —— 占满整年，但不假装知道月份。"""
    assert tl.slot_of(1630, None, end=False) == tl.slot_of(1630, 1)
    assert tl.slot_of(1630, None, end=True) == tl.slot_of(1630, 12)


def test_month_out_of_range_is_clamped(tl: T.Timeline):
    assert tl.slot_of(1630, 0) == tl.slot_of(1630, 1)
    assert tl.slot_of(1630, 99) == tl.slot_of(1630, 12)


# ---------------------------------------------------------------- 跨度


def test_span_same_year_full_width(tl: T.Timeline):
    left, width = tl.span_pct(1630, None, 1630, None)
    assert abs(left - tl.year_tick_pct(1630)) < 1e-9
    # 整年 = 12 格 / 204 格
    assert abs(width - 12 / 204 * 100) < 1e-9


def test_span_month_precision_is_narrower(tl: T.Timeline):
    """有月份时跨度应比整年窄 —— 这正是月份精度的价值。"""
    _, full = tl.span_pct(1630, None, 1630, None)
    left, part = tl.span_pct(1630, 5, 1630, 5)
    assert part < full
    assert abs(part - 1 / 204 * 100) < 1e-9
    assert left > tl.year_tick_pct(1630)


def test_span_never_inverted(tl: T.Timeline):
    """终点早于起点时不应产生负宽（防御性）。"""
    left, width = tl.span_pct(1635, 1, 1630, 12)
    assert width > 0


# ---------------------------------------------------------------- 断限


def test_cutoff_is_1644_march():
    """老板拍板：截止 1644 年 3 月。"""
    assert T.CUTOFF_YEAR == 1644
    assert T.CUTOFF_MONTH == 3


@pytest.mark.parametrize(
    "year,month,expected",
    [
        (1644, 1, False),
        (1644, 3, False),   # 三月本身保留（城陷在三月十九日，当月仍有任免）
        (1644, 4, True),
        (1644, 12, True),
        (1645, 1, True),
        (1643, 12, False),
        (None, None, False),
    ],
)
def test_is_after_cutoff(year, month, expected):
    assert T.is_after_cutoff(year, month) is expected


def test_is_after_cutoff_year_without_month_keeps_the_year():
    """1644 年但月份未载 → 不能判为越界（否则会误删整年数据）。"""
    assert T.is_after_cutoff(1644, None) is False


def test_clamp_end_pulls_later_years_back():
    """超出断限的终年一律拉到 1644-03。

    老板原话："截止时间是 1644 年 3 月……直接写 1644 年 3 月，
    截断一下就好了后面都不要了。"
    """
    assert T.clamp_end(1646, None) == (1644, 3)
    assert T.clamp_end(1644, 7) == (1644, 3)
    assert T.clamp_end(1644, 12) == (1644, 3)


def test_clamp_end_keeps_earlier_years_intact():
    assert T.clamp_end(1630, None) == (1630, None)
    assert T.clamp_end(1644, 2) == (1644, 2)
    assert T.clamp_end(1644, 3) == (1644, 3)


def test_clamp_none_becomes_cutoff():
    assert T.clamp_end(None, None) == (1644, 3)


def test_timeline_accepts_custom_range():
    tl = T.Timeline(1636, 1640)
    assert tl.years == 5
    assert tl.total_slots == 60
