"""检查版本库里有没有"不该进公开仓"的文件。

用法：
  python scripts/check_public_scope.py            # 只报告
  python scripts/check_public_scope.py --strict   # 有违规时退出码 1（可挂 CI）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from public_scope import excluded  # noqa: E402


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8")
    return [l for l in out.stdout.splitlines() if l.strip()]


def main() -> int:
    bad = []
    for p in tracked():
        reason = excluded(p)
        if reason:
            bad.append((reason, p))
    print(f"版本库追踪文件 {len(tracked())} 个；命中公开仓排除规则 {len(bad)} 个")
    if bad:
        by_reason: dict[str, list[str]] = {}
        for reason, p in bad:
            by_reason.setdefault(reason, []).append(p)
        for reason, files in by_reason.items():
            print(f"\n[{reason}] {len(files)} 个")
            for f in files[:12]:
                print("   ", f)
            if len(files) > 12:
                print(f"    …另 {len(files) - 12} 个")
        print("\n→ 这些要么从版本库移除（git rm --cached）并入 .gitignore，"
              "要么确认可以公开后加入 scripts/public_scope.py 的 ALLOW。")
    else:
        print("✓ 版本库与公开仓规则一致")
    return 1 if (bad and "--strict" in sys.argv) else 0


if __name__ == "__main__":
    raise SystemExit(main())
