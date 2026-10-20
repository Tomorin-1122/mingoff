"""把"版本库追踪的文件"复制到临时目录，模拟公开仓的实际内容并跑测试。"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "AppData/Local/Temp/mingoff_stage"

if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)

out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
files = [f for f in out.stdout.decode("utf-8").split("\0") if f]
for f in files:
    src = ROOT / f
    dst = STAGE / f
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
print(f"tracked files copied: {len(files)} -> {STAGE}")
