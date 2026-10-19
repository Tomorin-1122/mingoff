"""D-11 报告数据：把对页年行归属的现状审计汇总（只读）。

产出 docs/evidence/d11/_d11_report_data.json：
  - 无标签年清单与行数
  - 各置信层行数
  - 与现有数据交叉验证结果
  - 有争议行（需回原书）清单
"""
import collections
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_d11_review.json").read_text(encoding="utf-8"))
rows = d["rows"]

by_year = collections.defaultdict(lambda: {"锚定": 0, "兜底": 0, "无": 0})
for r in rows:
    k = "锚定" if r["how"] == "人名锚" else ("兜底" if r["how"] == "行序兜底" else "无")
    by_year[r["year"]][k] += 1

summary = {
    "unlabeled_years": len(d["meta"]["unlabeled_years"]),
    "total_rows": len(rows),
    "confidence": {"high(>=0.9)": sum(1 for r in rows if r["conf"] >= 0.9),
                   "mid(0.5-0.9)": sum(1 for r in rows if 0.5 <= r["conf"] < 0.9),
                   "low(<0.5)": sum(1 for r in rows if r["conf"] < 0.5)},
    "crosscheck": json.loads((ROOT / "docs/evidence/d11/_d11_crosscheck.json").read_text(encoding="utf-8")),
    "rows_by_year": {str(y): v for y, v in sorted(by_year.items())},
}
(ROOT / "docs/evidence/d11/_d11_report_data.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "rows_by_year"}, ensure_ascii=False, indent=1))
