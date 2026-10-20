# 数据许可（Data License）

本项目采用**代码与数据分层许可**（见 `docs/DECISIONS.md` D11）。

| 层 | 许可 | 范围 |
|---|---|---|
| **代码** | Apache-2.0 | `src/mingoff/**/*.py`、`site/src/**`、`tests/**`、`scripts/**`、构建配置 |
| **本项目自整理的结构化数据** | **CC BY-NC-SA 4.0** | `official_cabinet.json`、`official_buyuan.json`、`person_profiles*.json`、`vol1_*` 等由本项目整理/校勘的导出物 |
| **CBDB 衍生数据** | **CC BY-NC-SA 4.0** | 人物小传、CBDB 对齐字段（`cbdb_id`/生卒/籍贯/历任等） |
| **第三方原始资料** | 不随本仓授权 | 见 `THIRD_PARTY.md`；原始扫描页、逐页 OCR、数据库快照不纳入公开仓 |

## CC BY-NC-SA 4.0 要点

- **署名（BY）**：须注明「MingOff（明代職官數據庫）」及数据来源；
- **非商业（NC）**：不得用于商业目的；站点不得接广告、卖数据或设付费墙；
- **相同方式共享（SA）**：改编后的数据须以同一许可发布；
- 完整许可文本：<https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode>

## 第三方数据不因本项目许可而改变

本仓**不发布**以下第三方原始资料，也不对其授予任何权利：

- 张德信《明代職官年表》（黄山书社）的扫描页、逐页 OCR 与表格图像；
- 《明人傳記資料索引》的扫描页与 OCR 全文；
- CBDB 官方 SQLite 快照；
- 中研院「明代職官資料庫」的批量检索原文（站点仅展示与任期相关的命中摘要并附出处）。

本仓中的结构化数据是上述资料的研究性整理；**第三方权利仍归原权利人**。
如权利人认为本仓内容超出合理使用/授权范围，请联系移除。

## 引用

见 `CITATION.cff`。建议引用：

> MingOff contributors. MingOff：明代职官数据库（2026）. https://github.com/Tomorin-1122/mingoff

（仓库地址以实际创建为准；正式发布后请替换。）
