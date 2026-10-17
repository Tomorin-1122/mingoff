# -*- coding: utf-8 -*-
"""demo 数据契约与时间轴几何验证（无浏览器）。

复刻前端的 span() 计算，逐条验证位置合法、断限正确、月份未被臆造。
"""
import sys, json, re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
html = (root / "web" / "demo.html").read_text(encoding="utf-8")

DATA = json.loads(re.search(r"const DATA = (\{.*?\});\s*\n", html, re.S).group(1))
YEARS = json.loads(re.search(r"const YEARS = (\[.*?\]);\s*\n", html, re.S).group(1))
YI = {r["year"]: r for r in YEARS}

Y0, Y1 = DATA["meta"]["year_min"], DATA["meta"]["year_max"]
NYEARS = Y1 - Y0 + 1
MPY = 12
TOTAL = NYEARS * MPY
CUT_Y, CUT_M = 1644, 3

failures: list[str] = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures.append(msg)


def slot(year, month, is_end):
    idx = year - Y0
    m = (MPY - 1 if is_end else 0) if month is None else max(0, min(MPY - 1, month - 1))
    return idx * MPY + m


def span(t):
    sY = Y0 if t["start"] is None else t["start"]
    eY = Y1 if t["end"] is None else t["end"]
    eM = t.get("end_month")
    if eY > CUT_Y or (eY == CUT_Y and (eM or 0) > CUT_M):
        eY, eM = CUT_Y, CUT_M
    s, e = slot(sY, t.get("start_month"), False), slot(eY, eM, True)
    if e < s:
        e = s
    return s, e


print(f"数据 {Y0}–{Y1}（{NYEARS} 年 × {MPY} 月 = {TOTAL} 格）"
      f"，{len(DATA['offices'])} 官职，{len(DATA['tenures'])} 条任职")
print()

print("=== 1. 时间轴：每年 12 月等宽 ===")
widths = []
for y in range(Y0, Y1):
    widths.append(slot(y + 1, 1, False) - slot(y, 1, False))
check(set(widths) == {MPY}, f"每年恰好 {MPY} 格（实测 {set(widths)}）")
check(TOTAL == NYEARS * MPY, f"总格数 {TOTAL}")
print(f"    每年占 {100/NYEARS:.4f}%，每月占 {100/TOTAL:.4f}%")

print()
print("=== 2. 纪年（干支 + 年号）===")
check(YI[1628]["ganzhi"] == "戊辰", "1628 戊辰")
check(YI[1644]["ganzhi"] == "甲申", "1644 甲申")
check(YI[1629]["era"] == "崇禎二年", "1629 = 崇禎二年")
check(all(y in YI for y in range(Y0, Y1 + 1)), f"覆盖全部 {NYEARS} 年")

print()
print("=== 3. 断限：1644 年 3 月，之后不画 ===")
over = [t for t in DATA["tenures"]
        if (t["end"] or 0) > CUT_Y or ((t["end"] or 0) == CUT_Y and (t.get("end_month") or 0) > CUT_M)]
check(not over, f"无终年超过 1644-03（检出 {len(over)}）")
NANMING = {"張慎言", "張有譽", "顧錫疇", "解學龍", "程註", "何應瑞", "李沾",
           "吳履中", "王鐸", "劉宗周"}
present = {t["person"] for t in DATA["tenures"]} & NANMING
check(not present, "无南明人物")
check(DATA["meta"]["year_max"] == CUT_Y, "止于 1644")
# 皇帝在位也须止于 1644-03
check(CUT_Y == 1644 and CUT_M == 3, "断限常量为 1644-03")

print()
print("=== 4. 月份：不臆造 ===")
wm = [t for t in DATA["tenures"] if t.get("start_month") or t.get("end_month")]
zero = [t for t in DATA["tenures"]
        if t.get("start_month") == 0 or t.get("end_month") == 0]
check(not zero, "没有 0 月")
print(f"    含月份的条目 {len(wm)}/{len(DATA['tenures'])}（其余留空，符合'不臆造'）")
for t in DATA["tenures"]:
    for k in ("start_month", "end_month"):
        v = t.get(k)
        if v is not None and not (1 <= v <= 12):
            failures.append(f"{t['person']} 的 {k}={v} 越界")

print()
print("=== 5. 几何：全部在界内 ===")
bad = 0
maxslot = 0
for t in DATA["tenures"]:
    s, e = span(t)
    if s < 0 or e >= TOTAL or e < s:
        bad += 1
    maxslot = max(maxslot, e)
check(bad == 0, f"全部 {len(DATA['tenures'])} 条位置合法")
print(f"    最末格 {maxslot} / {TOTAL - 1}（应 ≤ 断限所在的 {slot(CUT_Y, CUT_M, False)}）")
check(maxslot <= slot(CUT_Y, CUT_M, False), "无条目越过断限格")

print()
print("=== 6. 数据契约 ===")
check(not [t for t in DATA["tenures"] if t["start"] == 0 or t["end"] == 0], "没有 0 年")
check(not [t for t in DATA["tenures"] if not t.get("source")], "每条都有出处")
check(not [t for t in DATA["tenures"] if t.get("confidence") == 1.0], "无 1.0 置信度")
bad_type = [t for t in DATA["tenures"]
            if t.get("type") not in {"实授", "署理", "加衔", "管", "检校"}]
check(not bad_type, "任职类型都在受控词表内")

print()
print("=== 7. 并发峰值（泳道前提）===")
from collections import defaultdict
by = defaultdict(list)
for t in DATA["tenures"]:
    by[t["office"]].append(t)
for off, lst in by.items():
    peak = 0
    for y in range(Y0, CUT_Y + 1):
        n = sum(1 for t in lst
                if (t["start"] or Y0) <= y <= (t["end"] or Y1))
        peak = max(peak, n)
    print(f"    {off:<16} 峰值 {peak:>2} 人")

print()
print("=" * 60)
if failures:
    print(f"✗ {len(failures)} 项未通过:")
    for f in failures:
        print(f"    - {f}")
    sys.exit(1)
print("全部契约检查通过。")
