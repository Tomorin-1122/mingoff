# -*- coding: utf-8 -*-
"""崇祯朝年号纪年表：干支、皇帝、年龄。

## 数据来源与算法

* **干支**：由公元年推算（标准算法，`(year - 4) % 60` 定位六十甲子）。
  崇祯元年 = 1628 = 戊辰，实测与《明史》年表标题「崇禎元年戊辰」一致 ✓
* **皇帝**：崇祯朝即明思宗（朱由检），1627 年 8 月即位，1628 年改元崇祯。
* **年龄**：朱由检生于万历三十八年十二月，公历 **1611-02-06**。
  项目负责人拍板（2026-10-16）：**用周岁，不考虑虚岁**。
  周岁按"当年生日（2 月）是否已过"计算：
    - 2 月及以后 → 当年 − 1611
    - 1 月（公历未过生日）→ 当年 − 1611 − 1
  ⚠️ 生日 1611-02-06 是公历；农历正月与公历 1 月底–3 月初对应，边界月（正月）
  按"未过生日"取保守值，避免虚报精度。
"""
from __future__ import annotations

from datetime import date

#: 天干地支
_GAN = "甲乙丙丁戊己庚辛壬癸"
_ZHI = "子丑寅卯辰巳午未申酉戌亥"

#: 明思宗朱由检：年号崇祯
EMPEROR = {
    "name": "朱由檢",
    "temple": "明思宗",
    "era": "崇禎",
    "born_year": 1611,
    # 万历三十八年十二月 ≈ 公历 1611-02-06
    "born_gregorian": date(1611, 2, 6),
    # 即位：天启七年八月（1627-08）；改元：崇祯元年（1628）
    "enthroned_year": 1627,
    "era_start": 1628,
}

#: 北京城陷落：崇祯十七年三月十九日 = 1644-04-25
#: 项目负责人拍板：不做南明，截止至此。
BEIJING_FALL = {
    "year": 1644,
    "month": 3,
    "day": 19,
    "gregorian": "1644-04-25",
}

ERA_START = 1628
ERA_END = 1644


def ganzhi(year: int) -> str:
    """公元年 → 干支（如 1644 → 甲申）。

    标准算法：公元 4 年为甲子年，故 (year - 4) mod 60 定位六十甲子。
    实测校验：1628 → 戊辰（与《明史》「崇禎元年戊辰」一致）。
    """
    idx = (year - 4) % 60
    return _GAN[idx % 10] + _ZHI[idx % 12]


def era_year(year: int) -> int | None:
    """公元年 → 崇祯年序号（元年=1）。超出范围返回 None。"""
    if not (ERA_START <= year <= ERA_END):
        return None
    return year - ERA_START + 1


_CN_DIGITS = "〇一二三四五六七八九"


def era_label(year: int) -> str | None:
    """公元年 → 「崇禎二年」。"""
    n = era_year(year)
    if n is None:
        return None
    if n == 1:
        return "崇禎元年"
    if n < 10:
        return f"崇禎{_CN_DIGITS[n]}年"
    if n == 10:
        return "崇禎十年"
    if n < 20:
        return f"崇禎十{_CN_DIGITS[n - 10]}年"
    tens, ones = divmod(n, 10)
    return f"崇禎{_CN_DIGITS[tens]}十{_CN_DIGITS[ones] if ones else ''}年"


def full_label(year: int) -> str | None:
    """「崇禎二年己巳」—— 年号 + 干支，项目负责人要求的顶部显示格式。"""
    era = era_label(year)
    return f"{era}{ganzhi(year)}" if era else None


def age_zhousui(year: int, month: int | None = None) -> int:
    """周岁。项目负责人拍板：不考虑虚岁。

    生日为公历 1611-02-06：
      * month 是公历口径下的"是否已过生日"近似 —— 农历正月大致落在
        公历 1 月底–3 月初，边界按"未过生日"取保守值；
      * month 为 None（史料只到年）时按"当年生日已过"计（即 full year）。
    """
    born = EMPEROR["born_gregorian"]
    full = year - born.year
    if month is not None and month < 2:
        full -= 1
    return full


#: 兼容旧名：虚岁接口已废弃，保留别名以防外部引用断裂。
age_su = age_zhousui


def year_table(y0: int = ERA_START, y1: int = ERA_END) -> list[dict]:
    """产出逐年的纪年信息，供前端内嵌。年龄按周岁（2 月口径）。"""
    out = []
    for y in range(y0, y1 + 1):
        out.append({
            "year": y,
            "era": era_label(y),
            "ganzhi": ganzhi(y),
            "full": full_label(y),
            "age_su": age_zhousui(y, 2),
            "emperor": EMPEROR["name"],
        })
    return out


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print("公元  年号        干支   周岁")
    print("-" * 40)
    for r in year_table():
        print(f"{r['year']}  {r['era']:<10} {r['ganzhi']}  {r['age_su']:>3}")

    print()
    print("=== 校验（应与《明史》年表标题一致）===")
    for y in (1628, 1629, 1644):
        print(f"  {y} → {full_label(y)}")
    assert ganzhi(1628) == "戊辰", ganzhi(1628)
    assert ganzhi(1644) == "甲申", ganzhi(1644)
    assert ganzhi(1636) == "丙子", ganzhi(1636)
    print("  ✓ 干支正确（1628 戊辰 / 1644 甲申 / 1636 丙子）")
