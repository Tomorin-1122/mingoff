"""把《明人傳記資料索引》产出从 _scratch 归档进仓（D38 第 1 步）。

只做复制与校验，不改动任何源文件：
  _scratch/mineru_mrzj/*.json|*.csv  -> src/mingoff/data/mrzj/      （结构化资产）
  _scratch/mineru_mrzj/out/*.md      -> src/mingoff/data/mrzj/raw_ocr/（OCR 原始文本，可回溯）
  _scratch/mrzj_*.py                 -> scripts/mrzj/                （可复跑脚本）
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parent / "_scratch"
SRC = SCRATCH / "mineru_mrzj"
DST = ROOT / "src" / "mingoff" / "data" / "mrzj"
RAW_DST = DST / "raw_ocr"
SCRIPTS_DST = ROOT / "scripts" / "mrzj"

UNTRACKED_CSV = {"cbdb_final.csv"}  # 报告里没有引用，体积大，不入仓（重跑 mrzj_cbdb_disamb.py 可得）


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    for d in (DST, RAW_DST, SCRIPTS_DST):
        d.mkdir(parents=True, exist_ok=True)

    copied = []
    for p in sorted(SRC.iterdir()):
        if not p.is_file():
            continue
        if p.suffix not in (".json", ".csv"):
            continue
        if p.name in UNTRACKED_CSV:
            continue
        if p.name.startswith(("_", "one_p", "pilot", "up2x_", "col_p", "pilot3")):
            # 单页/放大/试点中间物，内容已被 corpus.json 覆盖，不入仓
            continue
        dst = DST / p.name
        if not dst.exists() or sha256(dst) != sha256(p):
            shutil.copy2(p, dst)
        copied.append(p.name)

    raw_n = 0
    for p in sorted((SRC / "out").glob("*.md")):
        dst = RAW_DST / p.name
        if not dst.exists() or dst.stat().st_size != p.stat().st_size:
            shutil.copy2(p, dst)
        raw_n += 1

    scripts = 0
    for p in sorted(SCRATCH.glob("mrzj_*.py")):
        shutil.copy2(p, SCRIPTS_DST / p.name)
        scripts += 1

    manifest = {
        "dataset": "mingoff-mrzj",
        "source_book": "《明人傳記資料索引》（昌彼得等編，中央研究院歷史語言研究所，1977 印刷本）",
        "note": "只取事实摘要与出处，不搬正文全文；正文由原书 PDF 现场可查。",
        "ocr": {"tool": "MinerU VLM", "pages": 963, "chars": 1207535,
                "raw_dir": "raw_ocr/（每页一段 Markdown，正文页 = PDF 页 − 25）"},
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
                  for p in DST.glob("*.json")},
        "raw_ocr_pages": raw_n,
        "scripts": sorted(p.name for p in SCRIPTS_DST.glob("*.py")),
    }
    (DST / "mrzj_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"structured {len(copied)} files -> {DST}")
    print(f"raw_ocr   {raw_n} pages  -> {RAW_DST}")
    print(f"scripts   {scripts} files -> {SCRIPTS_DST}")


if __name__ == "__main__":
    main()
