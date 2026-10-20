# 维护者说明（不进公开仓内容也在本地留存）

> 2026-10-20 老板拍板：**不再维护私有仓**。本地仓库直接提交公开仓
> <https://github.com/Tomorin-1122/mingoff>，`origin` 指向它。
> 本文件说明“哪些留在本地、为什么不提交”，以及改动后怎么自检。

## 一、仓库分工

| 位置 | 内容 |
|---|---|
| 公开仓（origin） | 代码 / 测试 / 站点 / 导出数据 `official_*.json` / 许可与 README |
| 本地未提交（`.gitignore`） | 过程文档 `docs/`、证据图、OCR 资产 `mrzj/`、重建输入 `vol1_*`、中研院检索导出、派生产物 `shilu_tags*` |

**原因**：① 原书扫描页与《明人傳記資料索引》OCR 有版权风险，不能再分发；
② `docs/` 是内部过程资料（报告、决策记录、本机路径），对读者无用；
③ 公开仓只发导出数据，不发重建输入。

## 二、每次改动后自检

```powershell
python scripts/check_public_scope.py          # 看有没有该排除却在版本库里的文件
python scripts/check_public_scope.py --strict # 有违规即非零退出（可挂 CI）
git status --short                            # 确认 docs/ 等没有出现在未跟踪列表
```

规则定义在 `scripts/public_scope.py`（目录级 / 文件级 / 重建输入三类）。

## 三、审计的两档输出

`python -m mingoff.audit_buyuan` 现在区分两种结论：

- **全资产**（本地）：所有门禁都跑，输出真实数字；
- **精简仓**（缺 `vol1_*`）：相关门禁显式打印 `SKIP（缺少…）`，
  并在末尾注明“blockers=0 不等于全量通过”，**不再以 0/None 冒充通过**。

## 四、重建输入在哪

`src/mingoff/data/vol1_*`、`sinica_*.json`、`mrzj/` 都还在**本地磁盘**上（未删），
只是不进版本库。需要重建数据时照 `docs/重建数据操作步骤.md` 在本机跑。
