# -*- coding: utf-8 -*-
"""生成公开仓精简快照（代码 + 最终数据 + 站点；不含 docs/过程数据/扫描）。"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "mingoff-public"

ROOT_FILES = {
    "README.md", "LICENSE", "NOTICE", "DATA_LICENSE.md", "THIRD_PARTY.md",
    "CITATION.cff", ".gitattributes", ".gitignore", "pyproject.toml",
}
# 只保留最终导出物，不含 vol1_* / review / manifest / pages 等过程数据
DATA_FILES = {
    "official_cabinet.json", "official_buyuan.json",
    "person_profiles.json", "person_profiles_buyuan.json",
}
# 只保留不依赖过程数据资产的核心测试
TEST_FILES = {
    "conftest.py", "test_chronology.py", "test_shilu.py", "test_data.py",
    "test_timeline.py", "test_d46_lineage.py",
}
SITE_ROOT = {
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "next.config.ts",
    "tsconfig.json", "next-env.d.ts", ".gitignore",
}


def wanted(rel: Path) -> bool:
    s = rel.as_posix()
    if rel.parts[0] in (".git", ".workbuddy", "node_modules", "_scratch", "scripts", "web", "docs"):
        if s.startswith("docs/screenshots/"):
            return True
        return False
    if s.startswith(".github/workflows/"):
        return True
    if s in ROOT_FILES:
        return True
    if s.startswith("src/mingoff/"):
        if rel.parent.as_posix() == "src/mingoff":
            return rel.suffix == ".py"
        if rel.parent.as_posix() == "src/mingoff/data":
            return rel.name in DATA_FILES
        return False
    if rel.parent.as_posix() == "tests" and rel.name in TEST_FILES:
        return True
    if s.startswith("site/src/"):
        return True
    if rel.parent.as_posix() == "site" and rel.name in SITE_ROOT:
        return True
    return False


def read_text_any(path: Path) -> str | None:
    for enc in ("utf-8", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def sanitize_text(text: str) -> str:
    for old, new in (
        ("老板", "项目负责人"),
        ("\u9648\u6587\u8f69", "MingOff contributors"),
        ("C:/Users/31698", "<repo>"),
        ("C:\\Users\\31698", "<repo>"),
        ("C:/Users/", "<user>/"),
        ("C:\\Users\\", "<user>\\"),
        ("D:/Desktop", "<local>/Desktop"),
        ("D:\\Desktop", "<local>\\Desktop"),
    ):
        text = text.replace(old, new)
    return text


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"输出目录已存在：{OUT}（请先移走/删除）")
    OUT.mkdir(parents=True)
    copied = 0
    total = 0
    for src in ROOT.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(ROOT)
        if not wanted(rel):
            continue
        s = rel.as_posix()
        if s == "README.md":
            src_for, dst = ROOT / "README.public.md", OUT / "README.md"
        elif s.startswith("docs/screenshots/"):
            src_for, dst = src, OUT / "assets" / "screenshots" / rel.name
        else:
            src_for, dst = src, OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src_for.suffix in {".md", ".py", ".ts", ".tsx", ".css", ".json", ".cff", ".toml", ".yml", ".yaml"}:
            dst.write_text(sanitize_text(read_text_any(src_for)), encoding="utf-8")
        else:
            shutil.copy2(src_for, dst)
        copied += 1
        total += dst.stat().st_size

    print(f"copied {copied} files, {total/1024/1024:.2f} MB -> {OUT}")
    print(f"generated_at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
