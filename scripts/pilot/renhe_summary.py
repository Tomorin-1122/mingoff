"""人工核验 6 条：全部在内阁数据（official_cabinet），定位完成。整理对应关系与修法（只读输出）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
c = json.loads((ROOT / "src/mingoff/data/official_cabinet.json").read_text(encoding="utf-8"))

lines = []
for t in c["tenures"]:
    p = t["person"]
    if p in ("李國楷", "李國𣚴", "錢溥", "劉一燝", "翟鑾", "蔣冕", "劉珝", "劉翔"):
        lines.append(
            f"{p} | {t['start_year']}.{t.get('start_month')}–{t['end_year']}.{t.get('end_month')} "
            f"| leave={t.get('leave')} | conf={t.get('confidence')} | note={t.get('note','')[:50]}")
print("\n".join(lines))
(ROOT / "docs/evidence/_renhe_summary.txt").write_text("\n".join(lines), encoding="utf-8")
