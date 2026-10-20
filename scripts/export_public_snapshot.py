# -*- coding: utf-8 -*-
"""生成公开仓快照（Tier B：代码 + 精简结构化数据 + 文档，不含扫描/OCR/证据）。

用法：
    python scripts/export_public_snapshot.py [输出目录]
默认输出到仓库同级的 ``mingoff-public``（不覆盖已有目录；如存在请先移走）。

只复制白名单文件；随后做文本脱敏：
  * 「老板」→「项目负责人」
  * 真实姓名 → 「MingOff contributors」
  * C:/Users/<user> 之类本机绝对路径 → <repo>/<user>
排除：mrzj/、docs/evidence/、sinica_*、neige_*、web/demo.html、
      .workbuddy/、scripts/、_scratch/、site/out、node_modules。
"""
from __future__ import annotations

import json
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
DATA_FILES = {
    "official_cabinet.json", "official_buyuan.json",
    "person_profiles.json", "person_profiles_buyuan.json",
    "vol1_entries.json", "vol1_person_cbdb.json",
    "vol1_buyuan_entries.json", "vol1_buyuan_entries_v2.json",
    "vol1_buyuan_person_cbdb.json", "vol1_buyuan_person_cbdb_v2.json",
    "vol1_buyuan_person_cbdb_v3.json", "vol1_buyuan_manifest.json",
    "vol1_buyuan_pages.json", "vol1_buyuan_repair.json",
    "vol1_buyuan_review.json", "vol1_buyuan_review_v2.json",
    "vol1_buyuan_note_review.json", "vol1_buyuan_gap_review.json",
    "vol1_buyuan_d11_review.json", "chongzhen_offices.json",
    "quality_report.json", "cbdb_unresolved.json",
}
WEB_FILES = {"demo.template.html", "preview-desktop.png", "preview-mobile.png"}
SITE_ROOT = {
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "next.config.ts",
    "tsconfig.json", "next-env.d.ts", ".gitignore", "README.md",
}
# 内部文档（含本机路径/校园网/内部决策过程），不随公开仓发布
DOC_EXCLUDE = {
    "仓库发布方案.md", "PRD核查报告.md", "人工核验.md",
    "决策模型实测.md", "决策模型实测-任职史料判断.md",
    "决策模型实测-打开方式与省钱账.md", "决策模型打标试点报告.md",
}


def wanted(rel: Path) -> bool:
    s = rel.as_posix()
    if rel.parts[0] in (".git", ".workbuddy", "node_modules", "_scratch"):
        return False
    if s.startswith(".github/workflows/"):
        return True
    if s in ROOT_FILES:
        return True
    if s.startswith("src/mingoff/") and rel.parent.as_posix() == "src/mingoff":
        return rel.suffix == ".py"
    if rel.parent.as_posix() == "src/mingoff/data" and rel.name in DATA_FILES:
        return True
    if rel.parent.as_posix() == "tests" and rel.suffix == ".py":
        return True
    if rel.parent.as_posix() == "docs" and rel.suffix == ".md" and rel.name not in DOC_EXCLUDE:
        return True
    if s.startswith("docs/screenshots/"):
        return True
    if s.startswith("site/src/"):
        return True
    if s.startswith("site/") and rel.parent.as_posix() == "site" and rel.name in SITE_ROOT:
        return True
    if rel.parent.as_posix() == "web" and rel.name in WEB_FILES:
        return True
    return False


def read_text_any(path: Path) -> str | None:
    for enc in ("utf-8", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # 混合编码的历史文档：保留可读部分，坏字节替换，公开快照统一转 UTF-8
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
    skipped = []
    for src in ROOT.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(ROOT)
        if not wanted(rel):
            skipped.append(rel.as_posix())
            continue
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in {".md", ".py", ".ts", ".tsx", ".css", ".json", ".cff", ".toml", ".yml", ".yaml", ""}:
            text = read_text_any(src)
            if text is None:
                shutil.copy2(src, dst)
            else:
                dst.write_text(sanitize_text(text), encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        copied += 1
        total += dst.stat().st_size

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "local mingoff repository",
        "tier": "B（代码 + 精简结构化数据；不含扫描/OCR/证据/内部日志）",
        "files": copied,
        "bytes": total,
        "excluded_dirs": [
            "docs/evidence", "src/mingoff/data/mrzj", "src/mingoff/data/sinica_*",
            "src/mingoff/data/neige_*", "web/demo.html", ".workbuddy",
            "scripts", "_scratch", "site/out", "node_modules",
        ],
        "license": {
            "code": "Apache-2.0",
            "data": "CC BY-NC-SA 4.0",
        },
    }
    (OUT / "PUBLIC_SNAPSHOT.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"copied {copied} files, {total/1024/1024:.2f} MB -> {OUT}")
    print(f"excluded (not copied): {len(skipped)} files")


if __name__ == "__main__":
    main()
