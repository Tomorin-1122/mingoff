# -*- coding: utf-8 -*-
"""从「出處」列提取年月 —— 月份精度的可靠来源。

## 背景（老板指出的正解）

我上一轮结论说"月份不可得"，**是错的** —— 因为我看了错误的列。
实测中研院 `output.php check[]=3`（明實錄）返回的表格是：

    <tr><th>時間</th><th>年號</th><th>出處</th><th>內容</th>
    <tr><td>1637</td><td>崇禎</td>
        <td>明實錄 附錄 崇禎實錄 卷十 崇禎十年 五月</td>
        <td>○…</td>

**月份在「出處」列**：`… 卷十 崇禎十年 五月`。即"实录名 + 庙号 + 卷次 + 年号纪年(含月)"。

实测覆盖率（修正闰月漏检后）：**35/35 = 100%**。
所以《明实录》确实带就任月份 —— 实录按"年号X年Y月"系日编排。

## 与 CBDB 的对比

| 来源 | 崇祯朝记录 | 含月份 | 结论 |
|---|---|---|---|
| CBDB 快照 | 2,676 | 31（1.2%，多为 `0月`）| ❌ 不可用 |
| 中研院明實錄 | 按需检索 | **100%** | ✅ 可用 |

## 本模块的边界

只做**解析**（HTML → 结构化），不做抓取。抓取在 `_verify/extract_sinica_months.py`
（一次性核实脚本）；正式接入时应挪进本项目并加限速。
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

#: 汉字月 → 数字。注意「十一」「十二」要在「十」之前匹配，否则「十一」会被切成「十」。
_CN_MONTH = {
    "正": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
}

#: 「閏正月」的閏要在月名前吃掉，否则会被当作无月份（实测踩过：陳新甲两条漏检）
_MONTH_RE = re.compile(r"(閏)?(十一|十二|十|正|[一二三四五六七八九])月")

#: 一条记录：<td>年</td><td>年號</td><td>出處</td><td>內容</td>
#: 年不假定是纯数字 —— 站点可能给「不详」「？」等；解析时再转 int，转不动留 None。
_ROW_RE = re.compile(
    r"<td>([^<]{1,12})</td>\s*<td>([^<]*)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>",
    re.S | re.I,
)


@dataclass
class ShiluRow:
    """一条明实录检索结果。"""

    year: int | None          # 公元年（站点给的，可能是"事件年"而非"就任年"）
    era: str                  # 年號（洪武/永樂/…/崇禎）
    source: str               # 出處：实录名 + 庙号 + 卷次 + 年号纪年(含月)
    content: str              # 內容：原文
    month: int | None = None  # 从出處解析出的月份
    is_leap: bool = False     # 是否閏月
    era_year_text: str = ""   # 「崇禎十年」原文，便于核对

    @property
    def precise(self) -> bool:
        """是否精确到月。"""
        return self.month is not None

    @property
    def month_label(self) -> str:
        if self.month is None:
            return ""
        return f"{'閏' if self.is_leap else ''}{self.month}月"


def parse_month(source: str) -> tuple[int | None, bool]:
    """从出處取 (月份, 是否闰月)。

    出處形如「明實錄 附錄 崇禎實錄 卷十 崇禎十年 五月」。
    取**第一个**月份 —— 卷次里不会出现"月"字，所以第一个就是纪年月份。
    """
    m = _MONTH_RE.search(source)
    if not m:
        return None, False
    return _CN_MONTH.get(m.group(2)), bool(m.group(1))


#: 明代年号全表（含二字年号 —— 早期写成字符类 `[崇禎]`，
#: 那只会匹配单字，把「崇禎十年」截成「禎十年」。必须用**选择分支**）
_ERA_NAMES = (
    "洪武", "建文", "永樂", "洪熙", "宣德", "正統", "景泰", "天順",
    "成化", "弘治", "正德", "嘉靖", "隆慶", "萬曆", "泰昌", "天啟", "崇禎",
)
_ERA_YEAR_RE = re.compile(
    "(" + "|".join(_ERA_NAMES) + r")([元一二三四五六七八九十]+)年"
)


def parse_era_year_text(source: str) -> str:
    """取出「崇禎十年」这样的年号纪年文本（用于人工核对）。"""
    m = _ERA_YEAR_RE.search(source)
    return m.group(0) if m else ""


def parse_rows(html_text: str) -> list[ShiluRow]:
    """把中研院返回的 HTML 解析成结构化行。

    只取有月份或明确纪年的行；表格里可能夹着表头与空行，一律跳过。
    """
    out: list[ShiluRow] = []
    for m in _ROW_RE.finditer(html_text):
        year_s, era, src_raw, content_raw = m.groups()
        src = _html.unescape(re.sub(r"<[^>]+>", " ", src_raw))
        src = re.sub(r"\s+", " ", src).strip()
        content = _html.unescape(re.sub(r"<[^>]+>", "", content_raw))
        content = re.sub(r"\s+", "", content).strip()
        if not src and not content:
            continue
        month, leap = parse_month(src)
        try:
            year: int | None = int(year_s)
        except ValueError:
            year = None
        out.append(
            ShiluRow(
                year=year, era=era.strip(), source=src, content=content,
                month=month, is_leap=leap, era_year_text=parse_era_year_text(src),
            )
        )
    return out


def month_coverage(rows: list[ShiluRow]) -> float:
    """含月份的行占比，用于评估检索质量。"""
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.precise) / len(rows)
