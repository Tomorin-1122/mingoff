# -*- coding: utf-8 -*-
"""明实录检索结果解析测试。

样本取自**真实抓取**的中研院返回（见 _verify/extract_sinica_months.py 的输出），
不是构造的 —— 因为这里的坑（闰月、卷次干扰）只有真数据才暴露。
"""
from __future__ import annotations

import pytest

from mingoff import shilu as S


# ---------------------------------------------------------------- 月份解析


@pytest.mark.parametrize(
    "source,month,leap",
    [
        ("明實錄 神宗 卷五百十五 萬曆四十一年十二月", 12, False),
        ("明實錄 神宗 卷五百八十六 萬曆四十七年九月", 9, False),
        ("明實錄 光宗 卷六 泰昌元年八月", 8, False),
        ("明實錄 附錄 崇禎實錄 卷十 崇禎十年 五月", 5, False),
        ("明實錄 附錄 崇禎實錄 卷十一 崇禎十一年 六月", 6, False),
        ("明實錄 太祖 卷二百二 洪武二十三年五月至六月 五月", 5, False),
    ],
)
def test_parse_month(source, month, leap):
    assert S.parse_month(source) == (month, leap)


def test_parse_leap_month():
    """闰月必须识别 —— 实测陳新甲有「閏正月」两条，早期正则漏检。"""
    assert S.parse_month("明實錄 附錄 崇禎實錄 卷十三 崇禎十三年 閏正月") == (1, True)


def test_parse_month_absent():
    assert S.parse_month("明實錄 神宗 卷五百十五 萬曆四十一年") == (None, False)


def test_parse_month_prefers_first_occurrence():
    """出處里卷次在前、纪年在后；卷次不含「月」，所以第一个月份就是纪年月份。"""
    src = "明實錄 太祖 卷二百二 洪武二十三年五月至六月"
    assert S.parse_month(src)[0] == 5


@pytest.mark.parametrize(
    "num,expected",
    [("正", 1), ("一", 1), ("二", 2), ("九", 9), ("十", 10), ("十一", 11), ("十二", 12)],
)
def test_all_chinese_month_forms(num, expected):
    assert S.parse_month(f"明實錄 某 卷某 某年{num}月")[0] == expected


def test_shiyi_not_misparsed_as_ten():
    """「十一月」不能被切成「十月」—— 正则顺序敏感。"""
    assert S.parse_month("某 某年十一月")[0] == 11


# ---------------------------------------------------------------- 年号纪年文本


@pytest.mark.parametrize(
    "source,expected",
    [
        ("明實錄 附錄 崇禎實錄 卷十 崇禎十年 五月", "崇禎十年"),
        ("明實錄 神宗 卷五百十五 萬曆四十一年十二月", "萬曆四十一年"),
        ("明實錄 太祖 卷二百二 洪武二十三年五月至六月", "洪武二十三年"),
        ("明實錄 光宗 卷六 泰昌元年八月", "泰昌元年"),
    ],
)
def test_parse_era_year_text(source, expected):
    assert S.parse_era_year_text(source) == expected


def test_parse_era_year_text_absent():
    assert S.parse_era_year_text("某書 卷一 無紀年") == ""


# ---------------------------------------------------------------- 整行解析


REAL_HTML = """
<table class="text_tab"><tr><th>時間</th><th>年號</th><th>出處</th><th>內容</th>
<tr><tr><td>1613</td><td>萬曆</td><td>明實錄 神宗 卷五百十五 萬曆四十一年十二月</td><td>○禮部會同九卿科道會勘…<a href="info.php?id=X">楊嗣昌</a>…</td>
<tr><tr><td>1637</td><td>崇禎</td><td>明實錄 附錄 崇禎實錄 卷十 崇禎十年 五月</td><td>○兵部…</td>
<tr><tr><td>1640</td><td>崇禎</td><td>明實錄 附錄 崇禎實錄 卷十三 崇禎十三年 閏正月</td><td>○…</td>
</table>
"""


def test_parse_rows_from_real_html():
    rows = S.parse_rows(REAL_HTML)
    assert len(rows) == 3
    assert rows[0].year == 1613
    assert rows[0].era == "萬曆"
    assert rows[0].month == 12
    assert rows[0].precise
    # 内容里的 HTML 标签被清掉
    assert "<a" not in rows[0].content
    assert "楊嗣昌" in rows[0].content


def test_parse_rows_handles_leap():
    rows = S.parse_rows(REAL_HTML)
    leap = [r for r in rows if r.is_leap]
    assert len(leap) == 1
    assert leap[0].month == 1
    assert leap[0].month_label == "閏1月"


def test_month_label_is_chinese():
    rows = S.parse_rows(REAL_HTML)
    assert rows[0].month_label == "12月"
    assert rows[1].month_label == "5月"


def test_parse_rows_skips_empty():
    assert S.parse_rows("<table></table>") == []
    assert S.parse_rows("<td>1</td><td></td><td></td><td></td>") == []


def test_parse_rows_tolerates_non_numeric_year():
    html = "<td>不详</td><td>崇禎</td><td>某 崇禎十年 五月</td><td>内容</td>"
    rows = S.parse_rows(html)
    assert len(rows) == 1
    assert rows[0].year is None
    assert rows[0].month == 5


def test_month_coverage():
    rows = S.parse_rows(REAL_HTML)
    assert S.month_coverage(rows) == 1.0
    assert S.month_coverage([]) == 0.0


def test_month_coverage_partial():
    html = (
        "<td>1637</td><td>崇禎</td><td>某 崇禎十年 五月</td><td>a</td>"
        "<td>1640</td><td>崇禎</td><td>某 崇禎十三年</td><td>b</td>"
    )
    rows = S.parse_rows(html)
    assert S.month_coverage(rows) == 0.5
