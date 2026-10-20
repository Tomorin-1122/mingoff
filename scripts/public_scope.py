# -*- coding: utf-8 -*-
"""精简仓（公开仓）分发规则：哪些文件**不进**公开快照。

维护方式（2026-10-20 老板拍板）：
  - **不再维护私有仓**；本地仓库直接提交公开仓 `Tomorin-1122/mingoff`；
  - 报告、证据、内部过程一律不入库（本文件 + .gitignore 双重保证）。

规则口径（与 docs/仓库发布方案.md 一致）：
  1. **版权风险资产**：原书扫描页、现代工具书 OCR、中研院批量检索结果 —— 不能公开；
  2. **内部过程资料**：报告、决策记录、工作日志、本机路径 —— 对读者无用且有隐私风险；
  3. **重建输入**：`vol1_*` 等中间物，精简仓只发**导出数据**，不发重建输入；
  4. 其余（代码 / 测试 / 站点 / 导出数据 / 许可与 README）全部保留。

自查：
  python scripts/check_public_scope.py          # 列出"被规则排除但仍在版本库里的文件"
"""
from __future__ import annotations

# 目录级排除（前缀匹配）
EXCLUDE_DIRS = (
    "docs/",            # 过程文档、报告、证据图：一律不入公开仓
    ".workbuddy/",      # 本机工作日志
    "web/",             # demo 成品与模板（站点已在 site/）
    "src/mingoff/data/mrzj/",   # 《明人传记资料索引》OCR 与人物库（现代工具书）
    "scripts/mrzj/",    # 私有 OCR 流水线脚本（含本机路径）
    "_scratch/",
)

# 文件级排除（精确路径）
EXCLUDE_FILES = (
    "src/mingoff/data/sinica_all.json",      # 中研院检索结果批量导出（13.2 MB）
    "src/mingoff/data/sinica_months.json",
    "src/mingoff/data/shilu_tags.json",      # 可重跑的派生产物
    "src/mingoff/data/shilu_tags.ckpt.jsonl",
    "_stage_mrzj.py",
)

# 重建输入（精简仓不发；审计遇到缺失会显式 SKIP）
REBUILD_INPUTS = (
    "vol1_buyuan_entries_v2.json",
    "vol1_buyuan_person_cbdb_v3.json",
    "vol1_buyuan_repair.json",
    "vol1_buyuan_manifest.json",
    "vol1_buyuan_pages.json",
    "vol1_buyuan_note_review.json",
    "vol1_buyuan_gap_review.json",
    "vol1_buyuan_review_v2.json",
)

# 允许例外（即使命中目录规则也保留）：公开仓必需
ALLOW = (
    "site/src/data/",
    "assets/",          # README 预览图（必须入仓，否则 GitHub README 图片裂开）
    # GitHub Pages 站点产物：docs/ 既是 Pages 发布目录，也是 Jekyll 页面来源。
    # 只放行构建产物，过程文档/报告/证据图仍不入仓。
    "docs/index.html",
    "docs/index.txt",
    "docs/404.html",
    "docs/.nojekyll",
    "docs/_next/",
)


def excluded(path: str) -> str | None:
    """返回排除原因；None 表示可入公开仓。"""
    p = path.replace("\\", "/")
    if any(p.startswith(a) for a in ALLOW):
        return None
    if p in EXCLUDE_FILES:
        return "文件级排除"
    if p in ("docs",) or any(p.startswith(d) for d in EXCLUDE_DIRS):
        return "目录级排除"
    name = p.rsplit("/", 1)[-1]
    if name in REBUILD_INPUTS:
        return "重建输入（精简仓不发）"
    if name.startswith("vol1_") and "/data/" in p:
        return "重建输入/中间数据（精简仓不发）"
    return None
