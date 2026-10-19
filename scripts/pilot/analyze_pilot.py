"""试点分析：模型打标 vs 规则，统计一致性并生成人工核对清单。"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
d = json.load(open(ROOT / "src/mingoff/data/pilot_tag_out.json", encoding="utf-8"))
rows = d["rows"]

print("n =", len(rows), " tokens =", d["meta"]["tokens"], " seconds =", d["meta"]["seconds"])
print("\n== kind 分布 ==")
for k, v in Counter(r["kind"] for r in rows).most_common():
    print(f"  {k:<4} {v:>4}  {v/len(rows):.1%}")
print("\n== is_tenure 分布 ==")
print(" ", Counter(r["is_tenure"] for r in rows))
print("== leave 分布 ==")
print(" ", Counter(r["leave"] for r in rows))

print("\n== kind 平均置信度 ==")
by = {}
for r in rows:
    by.setdefault(r["kind"], []).append(r["kind_conf"])
for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(f"  {k:<4} n={len(v):>3}  mean_conf={sum(v)/len(v):.3f}  min={min(v):.2f}")

print("\n== clarity 分布（score 0-3）==")
cl = Counter(round(r["clarity"], 1) for r in rows)
for k in sorted(cl):
    print(f"  {k}: {cl[k]}")

# ---- 交叉：模型 kind vs 规则
print("\n== 交叉表：模型 kind（行）× 规则 R1（列）==")
cross = Counter((r["kind"], r["rules"]["R1_head_appoint"]) for r in rows)
print(f"  {'kind':<6}{'R1=0':>8}{'R1=1':>8}")
for kind in ("授官", "离任", "议政", "行政", "其他"):
    print(f"  {kind:<6}{cross.get((kind,0),0):>8}{cross.get((kind,1),0):>8}")

tp = cross.get(("授官", 1), 0)
fp = cross.get(("授官", 0), 0)
fn = sum(cross.get((k, 1), 0) for k in ("离任", "议政", "行政", "其他"))
print(f"\n  以「模型判授官」为正类：TP={tp} FP={fp} FN={fn}")
if tp + fp:
    print(f"  模型召回（相对规则R1）={tp/(tp+fn):.1%}  规则R1精确度（相对模型）={tp/(tp+fp):.1%}" if tp + fn else "")

# ---- 交叉：is_tenure vs R1/R2
print("\n== is_tenure=是 × (R1 or R2) ==")
c2 = Counter((r["is_tenure"], r["rules"]["R1_head_appoint"] or r["rules"]["R2_leave"]) for r in rows)
print("            规则否  规则是")
for v in ("是", "否"):
    print(f"  模型{v}   {c2.get((v,0),0):>6}  {c2.get((v,1),0):>6}")

# ---- 人工核对清单：按 kind 分层随机抽 60
random.seed(7)
groups = {}
for r in rows:
    groups.setdefault(r["kind"], []).append(r)
work = []
for kind, need in (("授官", 20), ("离任", 10), ("议政", 10), ("行政", 10), ("其他", 10)):
    pool = [(r, "模型") for r in groups.get(kind, [])]
    work += random.sample(pool, min(need, len(pool)))
# 规则命中但模型判非授官的（漏判候选）
fn_rows = [(r, "规则") for r in rows if r["rules"]["R1_head_appoint"] and r["kind"] != "授官"]
work += random.sample(fn_rows, min(10, len(fn_rows)))

with open(ROOT / "src/mingoff/data/pilot_manual_check.md", "w", encoding="utf-8") as f:
    f.write("# 试点人工核对清单（60 条）\n\n")
    f.write("> 生成：scripts/pilot/analyze_pilot.py。每行判定后填 ✅/❌ 与正确类别。\n\n")
    f.write("| # | 来源 | 模型/规则 | 人员 | 年 | 文本 | 模型判定 | 核对（✅/❌） | 备注 |\n")
    f.write("|---|---|---|---|---|---|---|---|---|\n")
    for i, (r, src) in enumerate(work, 1):
        text = r["text"].replace("|", "｜").replace("\n", " ")[:80]
        f.write(f"| {i} | {src} | {r['kind']}({r['kind_conf']:.2f}) | {r['person']} | {r['year']} "
                f"| {text} | {r['kind']} |  |  |\n")
print(f"\n人工清单已写入 src/mingoff/data/pilot_manual_check.md（{len(work)} 条）")
