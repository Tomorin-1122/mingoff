"""D-11 第二轮：验证低置信行（行序兜底 <0.5）里有没有已知错挂（用 D42 已修年份作对照）。"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_d11_review.json").read_text(encoding="utf-8"))
# D42 修过的年份
FIXED = {1546, 1547, 1548, 1558}
lo_fixed = [r for r in d["rows"] if r["year"] in FIXED and r["conf"] < 0.5]
# 这些年份有标签吗？
lines = [f"D42 修正年在对页年列表里: {sorted(FIXED & set(d['meta']['unlabeled_years']))}",
         f"低置信行（D42 年份）: {len(lo_fixed)}"]
# 无标签年的分布：明初 vs 晚明
years = d["meta"]["unlabeled_years"]
buckets = collections.Counter(y // 50 * 50 for y in years)
lines.append(f"无标签年分布（50 年桶）: {json.dumps(dict(sorted(buckets.items())))}")
(ROOT / "docs/evidence/d11/_d11_round2.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
