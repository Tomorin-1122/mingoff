"""人工核验 6 条：内阁数据是主要对象，逐条看 tenure 细节（只读）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
c = json.loads((ROOT / "src/mingoff/data/official_cabinet.json").read_text(encoding="utf-8"))
out = []
for t in c["tenures"]:
    if t["person"] in ("李國楷", "李國𣚴", "錢溥", "錢士升", "劉一燝",
                       "翟鑾", "蔣冕", "劉珝", "劉翔"):
        out.append(json.dumps(t, ensure_ascii=False)[:500])
print("\n\n".join(out))
(ROOT / "docs/evidence/_renhe_cabinet.txt").write_text("\n\n".join(out), encoding="utf-8")
