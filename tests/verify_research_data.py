# -*- coding: utf-8 -*-
"""校验研究数据的自洽性，尤其是与**独立 ground truth**（兵部尚书）的对照。

这一步的意义：研究数据与项目已有的 14 条兵部尚书是**两条独立路径**得到的
（前者查《明史》年表，后者来自 PRD 的 张德信年表 清单）。两条路若一致，
说明数据可信；若不一致，必须先查清再入库。
"""
import sys, json, collections
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

d = json.loads((ROOT / "src/mingoff/data/chongzhen_offices.json").read_text(encoding="utf-8"))
tenures = d["tenures"]

print("=" * 70)
print("### 1. 字段完整性")
required = {"office", "person", "start_year", "end_year", "tenure_type",
            "leave_reason", "source", "confidence"}
bad = []
for i, t in enumerate(tenures):
    missing = required - set(t)
    if missing:
        bad.append((i, t.get("person"), missing))
print(f"  缺字段的条目: {len(bad)}")
for i, p, m in bad[:5]:
    print(f"    #{i} {p}: 缺 {m}")

print()
print("### 2. tenure_type 是否都在受控词表内")
ALLOWED = {"实授", "署理", "加衔", "管", "检校"}
c = collections.Counter(t.get("tenure_type") for t in tenures)
for k, v in c.items():
    flag = "" if k in ALLOWED else "  ← 越界！"
    print(f"  {str(k):<6} {v}{flag}")

print()
print("### 3. 年份合理性")
bad_year = [t for t in tenures
            if (t.get("start_year") or 0) and not (1627 <= t["start_year"] <= 1645)]
print(f"  起始年越界: {len(bad_year)}")
for t in bad_year[:5]:
    print(f"    {t['person']} {t['start_year']}")
rev = [t for t in tenures
       if t.get("start_year") and t.get("end_year") and t["start_year"] > t["end_year"]]
print(f"  起止颠倒: {len(rev)}")
for t in rev[:5]:
    print(f"    {t['person']} {t['start_year']}–{t['end_year']}")

print()
print("### 4. 置信度分布（不该有 1.0）")
c2 = collections.Counter(t.get("confidence") for t in tenures)
for k, v in sorted(c2.items(), key=lambda x: -(x[0] or 0)):
    flag = "  ← 宣称绝对确定！" if k == 1.0 else ""
    print(f"  {k}: {v}{flag}")
assert 1.0 not in c2, "有置信度 1.0 的条目"

print()
print("### 5. 每条都要有出处")
no_src = [t for t in tenures if not t.get("source")]
print(f"  无出处: {len(no_src)}")

print()
print("### 6. 覆盖度审计（每年每职至少一条在任）")
Y0, Y1 = 1628, 1644
offices = [o["office"] for o in d["offices"]]
gaps = []
for off in offices:
    if off == "兵部尚書":
        continue  # 用我们的 ground truth 单独查
    lst = [t for t in tenures if t["office"] == off]
    for y in range(Y0, Y1 + 1):
        hit = any(
            (t.get("start_year") is None or t["start_year"] <= y)
            and (t.get("end_year") is None or t["end_year"] >= y)
            for t in lst
        )
        if not hit:
            gaps.append((off, y))
print(f"  缺口（某年该职无人记载）: {len(gaps)}")
for off, y in gaps[:15]:
    print(f"    {off} 缺 {y}")
if not gaps:
    print("  ✓ 无整年缺口")

print()
print("### 7. 1644 年南明混入检查（子代理自述的问题）")
y1644 = [t for t in tenures
         if (t.get("start_year") or 0) <= 1644 <= (t.get("end_year") or 0)]
low = [t for t in y1644 if (t.get("confidence") or 1) <= 0.5]
print(f"  1644 年在任条目: {len(y1644)}，其中低置信(≤0.5): {len(low)}")
for t in low[:10]:
    print(f"    {t['person']:<6} {t['office']:<10} conf={t.get('confidence')} "
          f"| {str(t.get('note') or '')[:40]}")

print()
print("=" * 70)
print("### 8. 与独立 ground truth（兵部尚书）对照")
gt = json.loads((ROOT / "web/demo-data.json").read_text(encoding="utf-8"))
gt_bing = {t["person"]: (t["start"], t["end"]) for t in gt["tenures"]
           if t["office"] == "兵部尚書"}
res_bing = {t["person"]: (t.get("start_year"), t.get("end_year"))
            for t in tenures if t["office"] == "兵部尚書"}
print(f"  ground truth（PRD/张德信年表）: {len(gt_bing)} 人")
print(f"  研究数据（明史年表）          : {len(res_bing)} 人")
both = set(gt_bing) & set(res_bing)
print(f"  交集: {len(both)} 人")
only_gt = set(gt_bing) - set(res_bing)
print(f"  仅 ground truth 有: {sorted(only_gt) if only_gt else '（无）'}")
