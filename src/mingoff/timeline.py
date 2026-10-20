# -*- coding: utf-8 -*-
"""时间轴刻度：**每年 12 个月，等宽**。

## 项目负责人要求

> "还是每年都要有12个月的刻度，每年的长度要一样，这样美观一点，跑起来也比较直观"

所以时间轴不再是「按年等宽」，而是**按月等宽**：每年固定 12 格，
17 年 = 204 格，每年占总长的 1/17、每月占 1/204。

好处：
* 月份精度**能落在正确位置**（五月初任就画在 5/12 处），不再是"整年一条"；
* 各年长度一致，视觉上不会出现某年因为事件多而"看着更宽"的错觉；
* 拖到某年时，可以进一步定位到该年内的位置。

## 与"仅到年"的兼容

史料未载月份时，条从**年初**开始、到**年末**结束（占满该年 12 格），
并在详情里标注"仅到年"。**不假装知道月份。**
"""
from __future__ import annotations

ERA_START = 1628
ERA_END = 1644

MONTHS_PER_YEAR = 12


class Timeline:
    """把 (年, 月) 映射到 0~1 的比例位置。

    总格数 = 年数 × 12。所有位置都用"格"做整数运算再除以总格数，
    避免浮点误差累积导致末年偏差。
    """

    def __init__(self, year_min: int = ERA_START, year_max: int = ERA_END) -> None:
        self.year_min = year_min
        self.year_max = year_max
        self.years = year_max - year_min + 1
        self.total_slots = self.years * MONTHS_PER_YEAR

    def slot_of(self, year: int, month: int | None = None, *, end: bool = False) -> int:
        """(年, 月) → 格号（0-based）。

        月份为 None 时：
          * end=False → 该年第 1 格（年初）
          * end=True  → 该年第 12 格（年末）
        这样"仅到年"的记录自然占满整年。
        """
        idx = year - self.year_min
        if month is None:
            m = MONTHS_PER_YEAR - 1 if end else 0
        else:
            m = max(0, min(MONTHS_PER_YEAR - 1, month - 1))
        return idx * MONTHS_PER_YEAR + m

    def pct(self, slot: int) -> float:
        """格号 → 百分比。"""
        return slot / self.total_slots * 100.0

    def span_pct(self, start_year, start_month, end_year, end_month) -> tuple[float, float]:
        """一段任期的 (左%, 宽%)。

        区间取**闭区间**：从起始格到结束格**之后**的那条线。
        例如 1628 年 5 月到 1629 年 3 月 = 格 4 到格 15，
        宽 = (15+1-4) 格。
        """
        s = self.slot_of(start_year, start_month, end=False)
        e = self.slot_of(end_year, end_month, end=True)
        if e < s:
            e = s
        left = self.pct(s)
        width = (e - s + 1) / self.total_slots * 100.0
        return left, width

    def year_tick_pct(self, year: int) -> float:
        """某年年初（1 月）的位置 —— 用于年份刻度与游标。"""
        return self.pct(self.slot_of(year, 1))

    def month_tick_pct(self, year: int, month: int) -> float:
        return self.pct(self.slot_of(year, month))


#: 断限：崇祯十七年三月（北京城陷落之月）。项目负责人要求直接截断，不做标记。
CUTOFF_YEAR = 1644
CUTOFF_MONTH = 3


def is_after_cutoff(year: int | None, month: int | None) -> bool:
    """是否晚于断限（1644 年 3 月）。

    判定用"月"而非"日"：史料多数只到月，用日会引入不必要的不确定性。
    1644 年 3 月**本身保留**（城陷在该月十九日，当月仍有任免）。
    """
    if year is None:
        return False
    if year > CUTOFF_YEAR:
        return True
    if year < CUTOFF_YEAR:
        return False
    # year == 1644
    return month is not None and month > CUTOFF_MONTH


def clamp_end(year: int | None, month: int | None) -> tuple[int, int | None]:
    """把超过断限的"终年"截断到 1644 年 3 月。

    崇祯 1644 年 3 月死，此后不应再"在任"。数据里若某条 end 是 1644，
    截断后即为 1644-03。这是项目负责人明确要求的："截断一下就好了后面都不要了"。
    """
    if year is None:
        return CUTOFF_YEAR, CUTOFF_MONTH
    if (year, month or 0) > (CUTOFF_YEAR, CUTOFF_MONTH):
        return CUTOFF_YEAR, CUTOFF_MONTH
    return year, month


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    tl = Timeline()
    print(f"年数 {tl.years}，月格 {tl.total_slots}（每年 {MONTHS_PER_YEAR} 格）")
    print()
    print("=== 抽查位置 ===")
    for (y, m) in ((1628, 1), (1628, 5), (1644, 3), (1644, 12)):
        s = tl.slot_of(y, m)
        print(f"  {y}-{m:02d} → 格 {s:>3}, {tl.pct(s):7.3f}%")
    print()
    print("=== 每年等宽验证（应恒为 1/17 ≈ 5.882%）===")
    for y in (1628, 1630, 1644):
        w = tl.year_tick_pct(y + 1) - tl.year_tick_pct(y)
        print(f"  {y} 年宽 {w:.4f}%")
    assert abs(tl.year_tick_pct(1629) - tl.year_tick_pct(1628) - 100 / 17) < 1e-9
    print("  ✓ 每年等宽")
    print()
    print("=== 断限 ===")
    for (y, m) in ((1644, 2), (1644, 3), (1644, 4), (1645, 1)):
        print(f"  {y}-{m:02d} 晚于断限: {is_after_cutoff(y, m)}")
