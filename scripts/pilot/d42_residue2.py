"""D42 残留：1558 總倉場（D41 字面后是「總倉場」，核对脚本按「總督倉場」查所以空）。

数据 1558 挂「總倉場」高燿——D41 后这就是正确写法；核对脚本用词旧了。确认后更新本脚本口径。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
e = json.loads((ROOT / "src/mingoff/data/vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
for r in e:
    if r["year"] == 1558 and "倉場" in r["office"]:
        print(f"1558 {r['office']} {r['person']} src={r.get('src')} page={r.get('book_page')}")
