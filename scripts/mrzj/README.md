# 《明人傳記資料索引》处理脚本

本目录是 D38 归档的脚本副本。脚本原本运行在仓库外的 `../_scratch/`，
路径多为**相对 `_scratch` 的硬编码**；归档后保留原样，便于复核，
重跑时请在 `_scratch` 同级位置按顺序复制回去，或按需改路径。

## 顺序（每一步都读上一步的产物，可单独重跑）

| # | 脚本 | 输入 → 输出 |
|---|---|---|
| 1 | `mrzj_slice.py` / `mrzj_probe.py` / `mrzj_size_probe.py` | 原书 PDF → 964 个单页 PDF（`pages/`） |
| 2 | `mrzj_batch.py` | 单页 PDF → MinerU 批量 OCR（50 页/批 + 429 退避） |
| 3 | `mrzj_ocr_eval.py` | 三模型（flash / VLM / pipeline）10 页比对，定 VLM |
| 4 | `mrzj_parse.py`、`mrzj_corpus.py` | `out/*.md` → `corpus.json` / `mrzj_fulltext.txt` |
| 5 | `mrzj_match.py` | 正文 → 282 名 CBDB 空档人物核验 |
| 6 | `mrzj_index.py`、`mrzj_body_heads.py`、`mrzj_apply_fixes.py`、`mrzj_roman_fix.py`、`mrzj_recover.py` | 人名目录解析 / 正文校勘 / 罗马字定姓 / 页码修复 |
| 7 | `mrzj_cbdb.py`、`mrzj_cbdb_disamb.py` | 本地 CBDB 快照裁决、置信分层 |
| 8 | `mrzj_extract.py`、`mrzj_person_db.py`、`mrzj_reconcile.py` | 条目抽取 → 人物库 → 与 CBDB 逐字段对账 |

## 依赖

- Python 3.14（系统解释器），只用标准库 + 原书 PDF 渲染所需的 PyMuPDF（`import fitz`）；
- MinerU 云端 API（token 走环境变量 `MINERU_TOKEN`，**不硬编码**）；
- 本地 CBDB 快照：`../_cbdb/cbdb_20261010.sqlite3`（外部数据，不入仓）。

## 产物落在哪

- 结构化资产：`src/mingoff/data/mrzj/`（含 `mrzj_manifest.json` 校验和）；
- 逐页 OCR 原文：`src/mingoff/data/mrzj/raw_ocr/`；
- 报告：`docs/明人传记资料索引OCR与核验报告.md`、`docs/明人传记资料索引_人名目录核对报告.md`、`docs/人物数据库试点报告.md`。
