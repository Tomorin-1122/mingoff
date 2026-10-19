"""金标准统计：GL_pos 应判"授官/是"，GL_neg 应判"议政/否"，GL_edge 只观测。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
d = json.load(open(ROOT / "src/mingoff/data/pilot_gold_out.json", encoding="utf-8"))
rows = d["rows"]
by = {}
for r in rows:
    by.setdefault(r["group"], []).append(r)


def rate(items, pred):
    return sum(1 for r in items if pred(r)) / len(items)


print(f"tokens={d['meta']['tokens']}  seconds={d['meta']['seconds']}\n")

pos = by["GL_pos"]
print("== GL_pos（句首授官动词+官职，应判 授官 / 是） n=%d ==" % len(pos))
print("  kind=授官:", f"{rate(pos, lambda r: r['kind']=='授官'):.1%}",
      " is_tenure=是:", f"{rate(pos, lambda r: r['is_tenure']=='是'):.1%}")
print("  kind 分布:", dict(Counter(r["kind"] for r in pos)))
hi = [r for r in pos if r["kind_conf"] >= 0.9]
lo = [r for r in pos if r["kind_conf"] < 0.7]
print(f"  分层：conf>=0.9 n={len(hi)} 准确 {rate(hi, lambda r: r['kind']=='授官'):.1%}"
      f"；conf<0.7 n={len(lo)} 准确 {rate(lo, lambda r: r['kind']=='授官'):.1%}")

neg = by["GL_neg"]
print("\n== GL_neg（无授官动词、含议政词，应判 议政 / 否） n=%d ==" % len(neg))
print("  kind=议政:", f"{rate(neg, lambda r: r['kind']=='议政'):.1%}",
      " is_tenure=否:", f"{rate(neg, lambda r: r['is_tenure']=='否'):.1%}")
print("  kind 分布:", dict(Counter(r["kind"] for r in neg)))

edge = by["GL_edge"]
print("\n== GL_edge（加/兼/贈/賜 类，仅观测） n=%d ==" % len(edge))
print("  kind 分布:", dict(Counter(r["kind"] for r in edge)))
print("  is_tenure=是:", f"{rate(edge, lambda r: r['is_tenure']=='是'):.1%}")

# 二分类：任职 vs 非任职（用 kind）
def is_appoint(r):
    return r["kind"] == "授官"


print("\n== 二分类汇总（授官=正类）==")
tp = sum(1 for r in pos if is_appoint(r))
fp = sum(1 for r in neg if is_appoint(r))
fn = sum(1 for r in pos if not is_appoint(r))
tn = sum(1 for r in neg if not is_appoint(r))
print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")
print(f"  precision={tp/(tp+fp):.1%}  recall={tp/(tp+fn):.1%}  accuracy={(tp+tn)/(tp+fp+fn+tn):.1%}")

# 典型误判示例
print("\n== GL_neg 里被误判为授官的 5 例 ==")
for r in [x for x in neg if x["kind"] == "授官"][:5]:
    print(f"  ({r['kind_conf']:.2f}) {r['text'][:70]}")
print("\n== GL_pos 里没判成授官的 5 例 ==")
for r in [x for x in pos if x["kind"] != "授官"][:5]:
    print(f"  ->{r['kind']} ({r['kind_conf']:.2f}) {r['text'][:70]}")
