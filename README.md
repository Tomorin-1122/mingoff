# MingOff —— 明代职官数据库与可视化平台

专注明代（1368–1644）276 年职官的结构化数据库：每条任职记录**可追溯史料来源**，
并显式标注异文与置信度。

> 需求基线见父目录的 `190508af-…_明代职官数据库需求文档(PRD).md`；
> 竞品调研见 `afa0807f-…_明实录结构化项目调研.md`。
> 本项目是该 PRD 阶段①（MVP）的实现。

---

## 一、这个项目做什么

| 维度 | 做法 |
|------|------|
| **垂直** | 只做明代职官，不与 CBDB 拼规模 |
| **可溯源** | 每条任职挂一个或多个史料来源（CBDB / 明实录 / 张德信年表…） |
| **可校勘** | 多源冲突进 `discrepancy` 表，是产品功能而非"脏数据" |
| **显式不确定** | `confidence` 字段 + `NULL` 表示史料未载（**不是 0**） |
| **可视化** | 任职时间轴 / 朝堂快照 / 人物流转网（后置，先保证数据对） |

**核心取舍**：不追求"绝对正确"，追求**每条记录都说清自己有多可信、依据是什么**。

---

## 二、当前进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段① MVP | 崇祯朝兵部尚书：清洗→入库→查询→校勘链路 | ✅ 完成 |
| 阶段①½ demo | 九职位可视化原型（无限画布·月格等宽·实录月份接入） | ✅ 完成（2026-10-16） |
| 阶段② 中高层全量 | 六部七卿+内阁+督抚+科道；167 处同年多月实录校勘 | ⬜ |
| 阶段③ 全朝中层 | 接入 CBDB 全量 + NLP 半自动抽取 | ⬜ |
| 阶段④ 地方官 | 府州县官 + 卫所武官（百万级） | ⬜ |

已完成：6 张表 schema、数据存取层、崇祯朝兵部尚书 14 任种子数据、CLI、
134 个测试、单文件可视化 demo（`web/demo.html`，双击即开）。
demo 要点：**月格等宽无限画布**（拖滑块精确到月看"那一年那月在任"）、
皇帝行朱色 + 周岁年龄带、实录月份回填（起月 33%）+ 抽屉贴《明实录》原文。
本轮开发经验见 `docs/demo开发经验总结.md`。

---

## 三、快速上手

```powershell
cd mingoff
$env:PYTHONPATH="src"          # 或先 pip install -e ".[dev]"

python -m mingoff.cli init      # 建库
python -m mingoff.cli seed      # 导入崇祯朝兵部尚书 14 任
python -m mingoff.cli list-bingbu
```

输出（MVP 的核心验收场景）：

```
兵部尚书历任（共 14 任）

#   姓名       任期           类型    离任     置信度
--------------------------------------------------------
1   閻鳴泰      1627–1628    实授    罢免     0.8
...
4   申用懋      1629–1629    署理    迁转     0.7
...
14  張縉彥      1644–1644    实授    降贼     0.8
```

### 其他命令

```powershell
python -m mingoff.cli snapshot 1629      # 某年在任快照
python -m mingoff.cli person 楊嗣昌       # 某人的仕途流转（含来源）
python -m mingoff.cli todo               # 待校勘队列
python -m mingoff.cli stats              # 库内计数
python -m mingoff.backfill_months        # 实录月份回填（需先抓 sinica_months.json）
python -m mingoff.export_demo            # 重建 web/demo.html
python -m pytest tests                   # 134 个测试
```

---

## 四、数据模型

六张表，详见 `src/mingoff/schema.py`。

```
person ──┐
         ├──< tenure >──┐
office ──┘              ├──< tenure_source >── source
                        └──< discrepancy >──── source(a/b)
```

| 表 | 作用 | 关键点 |
|----|------|--------|
| `person` | 人物 | `cbdb_id` 对齐外部库；生卒年可空 |
| `office` | 官职 | `parent_office_id` 构成官职树（兵部→兵部尚書） |
| `tenure` | **任职（核心）** | `tenure_type` 区分实授/署理/加衔；`confidence` 显式不确定 |
| `source` | 史料来源 | 带 `url` 以支持"一键跳原文出处" |
| `tenure_source` | 任职↔来源 | 一条任职可挂多源 |
| `discrepancy` | 异文/待校 | 多源冲突是一等公民 |

### 三条贯穿全项目的规则

1. **`NULL` ≠ `0`**。史料未载就是 `NULL`。写 0 会被误读成"生于公元 0 年"，
   是最常见也最难发现的录入错误。
2. **一条任职可挂多个来源**。单一 `source_ref` 字段表达不了"《明实录》与 CBDB
   都记了这条"。
3. **不确定性显式**。`confidence` 不用 1.0（除非真的无歧），冲突进 `discrepancy`。

---

## 五、为什么这些设计（决策记录）

完整理由见 `docs/DECISIONS.md`，几条要点：

- **为什么用 SQLite 而不是 PRD 建议的 PostgreSQL**：MVP 单人开发，SQLite 省掉部署；
  schema 用标准 SQL 写，迁移时只换连接层。
- **为什么不用 ORM**：表少、查询以只读统计为主，原生 SQL 更容易看出"哪些字段是
  史料未载"。而 `NULL` 语义正是本项目最需要小心的地方。
- **为什么 `tenure` 是核心表而不是 `person`**：本项目的价值在"某人某时任何职"。
- **为什么去重按 (姓名+籍贯) 而非仅姓名**：明代同名者众，误合并比留两份更糟。

---

## 六、与 `guji-pipeline` 的关系

MingOff 是独立产品，但**复用父项目的古籍取文能力**做校勘：

```powershell
# 在父项目里取《明实录》某卷原文，用于核对任职记载
cd ..
python -m guji.cli shidian toc LS0026        # 明實錄 3118 章
python -m guji.cli shidian chapter LS0026 <chapterId>
```

父项目的 `catalog find` / `shidian chapter` 提供"现取现核"的原文出处，
**不把明实录全文搬进本库**（PRD 4.3 的合规硬约束）。

> 实测结论：识典《明實錄》书 ID = `LS0026`，3118 章（PRD 4.2 写 2909 卷，
> 章数口径不同），章节页一次请求即可拿到完整目录，无需 JS 交互枚举。

---

## 七、目录结构

```
mingoff/
├─ README.md              本文件
├─ docs/DECISIONS.md      设计决策记录（D1–D20）
├─ docs/demo开发经验总结.md  本轮 demo 开发的坑与方法
├─ docs/数据源月份精度实测.md  CBDB/中研院月份能力实测
├─ pyproject.toml         包定义（一期零第三方依赖）
├─ src/mingoff/
│  ├─ schema.py           6 张表 + 受控词表
│  ├─ db.py               连接与建库
│  ├─ repo.py             数据存取（含三条规则的落实）
│  ├─ seed.py             MVP 种子数据（崇祯朝兵部尚书）
│  ├─ chronology.py       干支/年号/周岁
│  ├─ timeline.py         月格等宽时间轴（Python 侧基准）
│  ├─ shilu.py            明实录出處列年月解析
│  ├─ backfill_months.py  实录月份回填（同年唯一记录才回填）
│  ├─ merge_demo_data.py  研究数据 + ground truth 合并
│  ├─ export_demo.py      导出内嵌 JSON 并产出单文件 demo
│  └─ cli.py              命令行入口
├─ web/demo.template.html demo 模板（数据构建时注入）
├─ web/demo.html          产出的单文件 demo（双击即开，仅评审用，D21）
├─ src/mingoff/official.py ★ 正式数据管线：年表→内阁任职段（D21）
├─ docs/正式数据管线报告.md  正式版产出规模与源质量发现
├─ site/                  ★ 正式网站（Next.js 静态导出，D22；见 site/README.md）
└─ data/mingoff.sqlite    运行时数据库（不入库）
```

---

## 八、合规

- **主数据走 CBDB 官方快照**（官方支持研究用途）；
- 识典 / 中研院仅作**在线出处与校勘链接**，不批量搬全文入自建库；
- 网站发布需做来源标注与许可声明；数据许可与代码许可分开声明。
