# 对标调研：《大明职官图》GitHub 仓库（dingbo3603-ui/ming-official-atlas）

> 调研对象：<https://github.com/dingbo3603-ui/ming-official-atlas>（线上：<http://dmwc.cc/>）
> 调研日期：2026-10-18。方式：浅克隆到工作区 `_scratch/ming-atlas/`（307 MB，未入仓），
> 读源码/数据/脚本/部署文档，并用浏览器实测线上桌面与手机版。
> 结论速览：**它的产品形态与数据治理值得精读；代码与数据不要直接采用（无 LICENSE，
> 且体量与依赖都超出我们当前阶段）。最该学的是「模型 + 治理 + 交付纪律」三件事。**

---

## 0. 与既有判断的关系

D13（2026-10-16）已把它定为**借鉴对象**，并记录了三点可借鉴：
实职与兼衔分开、无日期资料不填入年度、空间维度有需求。
本次深读确认 D13 的判断（无 LICENSE、依赖本地原始资料、数据不可复现），
并补充 **7 项可落地的具体做法**（见第 6 节）与 4 项风险（见第 7 节）。

---

## 1. 项目概况（实测）

| 项 | 实测 |
|---|---|
| 仓库 | `dingbo3603-ui/ming-official-atlas`，公开，**无 LICENSE** |
| 描述 | 大明职官图：明代官署、人物履历、年号检索与府州县交互图谱 |
| 语言 / 规模 | TypeScript；GitHub 仓库 49 MB（压缩），**浅克隆工作区 307 MB** |
| 其中 | `public/` 154 MB（快照 API 147 MB）、`research/` 152 MB（最大的增量包 52.9 MB） |
| 数据量（站点自报） | **12,395 位人物 / 1,088 职官 / 200 府州**；年表 1368–1644；默认年 **1566** |
| 技术栈 | React 19 + Vite 8（NAS 构建）+ vinext/Cloudflare（另一构建）；线上静态站 + PHP 8.2 + MySQL 8.0 |
| 部署 | 虚拟主机 `dmwc1566`（FTP，无 TLS），域名 `dmwc.cc`；已上线 |
| 状态 | 最后 push 2026-09-09；55 stars；自述「资料持续校订，不代表完整名册」 |

**线上实测**：首访弹窗四条原则（永久开源免费 / 史料讲究出处 / 欢迎指正 / 资料愿意分享）；
主界面为「明代年表 + 年号条 + 年份滑块 + 天下舆图」，右侧为省/府面板；
可切到「京师」场景（皇帝—内阁—文武朝班—六部—清吏司的组织图）；
手机版是独立布局（顶部年号、地图卡、两京卡片、十三省 chips、底部 天下/京师/人物/史料 导航）。

---

## 2. 产品与信息架构（最值得学的一层）

### 2.1 三层空间 + 一个时间轴

```
天下（两京十三省 / 边卫所 / 三宣六慰）
 └ 京师（皇帝 · 内阁 · 文武朝班 · 六部 · 清吏司 · 中央官署）
     └ 地方（府 / 州 / 县衙署场景）
时间轴：1368–1644，年号条 + 滑块 + 年份跳转（默认 1566）
```

- **入口不是"一屏时间轴"**，而是「地—官署—人」三向可点，年份是全局过滤器；
- 顶部常驻「年度人物名册（90）→」：以年为单位的名单页，正是我们 D14 的核心竞争点
  的另一种产品化；
- 「全明职官目录」与「品秩考证」是独立页面，把工具书型内容做成可浏览资产；
- 首访原则弹窗 + `/data/history-provenance.html` 史料说明页 + 反馈入口，
  构成**信任前台**（开源/免费/可纠错/可下载）。

### 2.2 对我们的启示

我们的现状是「单层内阁时间轴 + 人物抽屉」，入口单一、没有"年→名单"的二级页。
**不必做地图**（超出阶段），但可低成本借鉴：
- 加「该年在任名单」侧栏/弹窗（数据已有，按年聚合即可）；
- 加一页「数据说明 / 史料与校勘」静态页（我们已有 docs 与 meta，做成前台页面即可）；
- 首访轻提示（一句"数据如何来、如何纠错"，不必做长弹窗）。

---

## 3. 技术架构与交付（可学纪律，不必学复杂度）

- **源 → 发布**：MySQL 为审校后真源 → 脚本导出**内容寻址快照**
  （`public/api/snapshots/<16位hash>/`：`bootstrap.json` + `years/1368..1644` +
  `people/<两位hex>.json` 共 256 片 + `datasets/*.json` + `manifest.json`）；
- 前端优先读静态快照，`readHistoryJson` 失败时回退 PHP API；revision 不匹配提示
  「资料版本正在更新」，失败不缓存；
- 快照按年、按人（FNV-1a 取尾两位分 256 片）切分，避免单文件过大；
- 部署：`npm run build:nas` → 上传 `dist-nas/`，FTP 脚本先备份、上传临时文件、
  SHA-256 逐文件回读、回执 `ftp-deployment-receipt.json`；公网 DNS+Host 头复核；
  HTTPS 自签问题如实记录（不假装已完成）；
- 双构建（NAS / Sites）是历史包袱，但**静态优先 + 可选服务端**的形态与我们的
  Next.js static export 同路。

**取舍提醒**：快照总体 147 MB、`bootstrap.json` 单文件 3.6 MB（12,395 人）。
分片解决"单文件过大"，但没有解决"总量过大"。我们若扩到部院/全官，
应设总预算（例如首屏 <1 MB、按需 <10 MB），必要时把搜索索引与正文分离。

---

## 4. 数据模型（本次最大收获）

### 4.1 七张表 / 七类实体

`atlas_people / atlas_tenures / atlas_sources / atlas_eras / atlas_years /
atlas_offices / atlas_datasets`；每行 = `id + 索引列 + body JSON`。
导出快照时只投影展示字段，完整出处留在人物详情与 MySQL。

### 4.2 五个关键设计（直接可移植）

| 设计 | 含义 | 我们的对应问题 |
|---|---|---|
| `record_kind` / `record_role` | 实任 `office_appointment`、署理 `acting_office`、兼衔 `concurrent_title_or_duty`、赠官 `honorary_title`、未赴任 `not_assumed`、非服务事件 `nonservice_event`；场景名单只取服务类 | 我们只有 `tenure_type: 实授`，D26 已意识到"实授/署理/加衔"需区分，这是现成词表 |
| `institution_ids` vs `office_ids` vs `duty_title` | 机构隶属、官职条目、职事名（首辅/阁臣）三者分离；**隶属按"实际工作地"而不是加衔**；南京与 CBDB 记录不硬挂 | 我们只有 `office: 內閣`，扩部院时必然遇到"加衔≠任职" |
| 左/右拆分 `split_offices` | **只有原典明写"左、右"才拆**；泛称"侍郎"不猜；`combined_record_id` 留原合并 id | 我们扩部院时必然遇到左/右侍郎 |
| `title_periods` | 官名随时间改称（华盖殿→中极殿 1562、谨身殿→建极殿），按区间给名称 | 对应我们的殿阁/年号分期 |
| `local_scope` + `ambiguousLocalPlaceNames` + `catalog_only_office_ids` | 地方官的辖属路径（names + from/to）；同名州府歧义不硬匹配；只有目录、未证实地任职的记录不进场景名单 | 我们若做地方/督抚层，这是防"张冠李戴"的关键 |

### 4.3 其他可学字段

- `attested_year`：只有纪年、不能断言整年在职的记录单列（与 `start/end` 并列）；
- `review_status` / `rank_review`：品秩考证分「已核 / 已修正 / 有条件说明 / 待核」，
  每次修正保留 `original_rank`、`evidence`、`source_url`；
- `empty_slots_evidence`：区分「当年确实未授此职」与「资料未齐」；
- `identity_resolution`：同名人物合并只列有证据的，保留原 id；
- `sources[]`：每条 `id/title/url/bundle`，可逐条引用（明史卷次、CBDB、方志）。

---

## 5. 数据治理与管线（可复制的纪律）

### 5.1 增量数据包（research bundles）

`research/history/*.json` 是"可合并的史料包"，每包含：
`meta.merge_instructions`（怎么合、不能用 null 覆盖已有值、哪些 id upsert）、
`people/sources/tenures`、`record_patches`（按 id 覆盖指定字段）、
`cabinet_year_coverage`、`empty_slots_evidence`、`identity_resolution`、`statistics`。
`prepare-history.py` 逐包合并后跑硬断言：人物/官职/出处 id 必须存在、id 唯一且格式合法、
`start<=end`、年份恰好 1368–1644。

→ 对照我们：目前是"脚本重跑 + 一次性数据资产"，**没有把每次修补做成可合并的包**。
可借鉴：以后每次修数据（如 2026-10-18 年份头修复）都产出一个
`research/patches/<date>.json`（变更 + 依据 + 影响），由管线幂等合并。

### 5.2 导入与发布

- 导入幂等：`CREATE TABLE IF NOT EXISTS` + `INSERT ... ON DUPLICATE KEY UPDATE`；
- **改前整表备份**；空输入拒绝清库；导入后 `DELETE ... NOT IN` 对账并断言集合相等；
- 读回验证（readback）：特定人物/年份的抽查断言 + 回执 JSON；
- **快照只从已提交的 MySQL 导出，绝不从 seed/中间产物导出**；
- 快照带 revision，新旧目录自动清理，只保留一个版本。

### 5.3 测试与交付检查

- Python `unittest` 三类：`SourceIntegrityTests`（出处/左右拆分/首辅=职事/时间分期/
  无日期不填年）、`ProductionYearSQLTests`（生产年度切片）、`LiveAPIContractTests`（接口契约）；
- 浏览器无关的前端检查：`check-mobile.mjs` / `check-office-scope.mjs` 用 Vite SSR 加载
  组件与函数，`renderToStaticMarkup` 后断言 13 条语义规则（同名州府、catalog-only、
  赠官不占席位、锦衣卫职官等）；
- 构建后检查 `check-dialog-css.mjs`（弹框样式真实生效）；
- 部署后 `verify-history-snapshot.mjs` / `verify-ftp.py` 逐文件核对 + 回执。

→ 我们的 Playwright 截图是"看得见"的检查，但缺少**数据语义级 SSR/函数级断言**。
可把 10–20 条"领域不变量"写成 Node/Python 测试（无需浏览器）。

---

## 6. 能学到的十件事（按优先级）

| # | 学什么 | 在我们项目里的落点 | 成本 |
|---|---|---|---|
| 1 | **实职/署理/兼衔/赠官/未赴 词表** | `数据接入规范` 新增 `record_role` 字段与取值；部院/殿阁扩展前先定 | 低 |
| 2 | **机构隶属 vs 官职 vs 职事三分** | 现在 `office: 內閣` 升级为 `office_ids/institution_ids/duty_title`；首辅作为 duty_title | 中 |
| 3 | **左/右拆分规则** | 部院侍郎层；只按原典明写拆，泛称不猜 | 低 |
| 4 | **`title_periods` 分期官名** | 华盖/谨身→中极/建极（1562）；年号/殿阁分期 | 低 |
| 5 | **`local_scope` + 同名歧义处理** | 未来督抚/地方层；先写入规范，不急于建数据 | 中 |
| 6 | **"年度名单"二级页** | 时间轴增加「该年在任名单」（按年聚合，已有 167 人数据） | 低 |
| 7 | **"资料版本/出处/校勘"前台页** | 把 `docs/` 的校勘规则与 2026-10-18 修复记录做成 `/about` 静态页 | 低 |
| 8 | **快照分片 + revision + 回退** | 部院/全官扩展时：按年/按人分片、bootstrap+manifest；先设体积预算 | 中 |
| 9 | **增量补丁包 + 幂等合并** | `research/patches/*.json` + 合并断言；把每次修复变成可审计资产 | 中 |
| 10 | **语义级测试/交付回执** | 领域不变量测试（10–20 条）+ 部署核对脚本/回执 | 低-中 |

**明确不学**：
- 不做 307 MB 仓库 / 147 MB 快照（我们的静态 J S O N 目标 <20 MB）；
- 不引入 PHP/MySQL 依赖（我们的静态导出已够，最多加只读查询）；
- 不做 32 KB 单页 + 49 KB 全局 context 的耦合（按组件/数据域拆分）；
- 不抄插画/地图资产与未授权数据。

---

## 7. 风险与保留意见

| 风险 | 说明 |
|---|---|
| **无 LICENSE** | GitHub 显示 `license: null`；代码默认"保留所有权利"，不能直接复制。CBDB 改编数据自述 CC BY-NC-SA 4.0，但仓库未附完整许可文件 |
| **数据不可复现** | README 自述部分重建脚本依赖本地原始资料目录与数据库导出，不能把仓库当数据库备份 |
| **体量** | 工作区 307 MB，快照 147 MB，bootstrap 3.6 MB；对克隆、部署、移动首屏都重 |
| **口径** | 自述"12,395 位人物不代表完整名册"；CBDB 派生、有选择与筛选，不能当全量权威 |
| **运维复杂度** | 静态站 + PHP + MySQL + 双构建 + FTP 部署，单人维护成本高；HTTPS 仍未有效 |
| **工程债** | 巨型 `page.tsx`、`lib` 反向从 `app/page` 导入类型、数据与 UI 强耦合，扩展时易碰坏 |

---

## 8. 对比：MingOff vs 大明职官图

| 维度 | MingOff（当前） | 大明职官图 |
|---|---|---|
| 范围 | 内阁一层（167 人 / 192 段 / 1,039 人-年） | 全官+地理（12,395 人 / 1,088 官 / 200 府州） |
| 深度 | 逐年+逐月、注文原文、CBDB/实录/中研院外链 | 人物生涯、机构层级、地图与场景 |
| 时间 | 1368–1644.3，单层时间轴，崇祯起手 | 1368–1644，年号条+滑块+年度名册，默认 1566 |
| 数据模型 | 宽表 JSON，`tenure_type` 单一 | 多表+角色词表+机构/官职/职事三分 |
| 溯源 | meta + note + 外链；docs 详尽 | sources 数组、每官每支 source_url+evidence、前台史料页 |
| 校勘 | G1–G5 / O1–O6 门 + 200+ 测试 | 审计页 + 语义测试 + 补丁包 |
| 交付 | Next static export；未部署 | 静态站 + PHP/MySQL；已上线；FTP 回执 |
| 许可 | 代码/数据许可已定（D11） | **无 LICENSE**，CBDB 部分 CC BY-NC-SA |
| 体量 | site 数据 ~1 MB | 快照 147 MB、工作区 307 MB |

**判断**：它验证了"按年横切 + 可溯源"的路线，并在**数据治理与交付纪律**上领先；
我们在**数据深度与可复现性/许可清晰度**上更好。不要因为它体量大就自卑，
也不要照抄它的技术债。

---

## 9. 建议行动（待老板拍板）

**P0（本周可做，1–2 天）**
1. 加「该年在任名单」：时间轴右侧/弹窗，按年聚合 `cabinet.json`（低风险）；
2. 加 `/about` 静态页：数据来源、断限、NULL 规则、校勘记录（把 DECISIONS/报告精选成前台文字）；
3. 首访一句提示（"数据来源与纠错方式"），不做二维码/长弹窗。

**P1（部院扩展前，写进规范）**
4. 在《数据接入规范》新增：`record_role` 词表、`institution_ids/office_ids/duty_title` 三分、
   左右拆分规则、`title_periods`、`local_scope` 与同名歧义规则；
5. 把每次修复做成 `research/patches/<date>.json`（含依据/影响/断言），管线幂等合并。

**P2（部院/全官扩展时）**
6. 数据资产按年/按人分片 + bootstrap+manifest+revision，设首屏体积预算；
7. 10–20 条领域不变量测试 + 部署核对回执。

---

## 10. 结论

- **产品**：它证明"地图+官署+人物+按年"是可行且吸引人的；我们的"时间轴+内阁"是另一种正确，
  可补"年度名单/关于页"两个低成本入口。
- **数据**：最值钱的是**角色词表、机构/官职/职事三分、左右拆分、地方 scope/歧义处理、
  补丁包+合并断言**——这些正是我们扩部院/地方时会踩的坑。
- **交付**：静态快照分片+revision+回退、幂等导入+备份+对账+回执、语义测试、部署逐文件核对，
  都是可以按比例缩小后移植的纪律。
- **不采用**：代码/数据（无 LICENSE）、307 MB 体量、PHP/MySQL 依赖、巨型单页与双构建。
- 与 D13 一致：**它是借鉴对象**；本次把"借鉴什么"从 3 条细化到 10 条。

---

## 附：调研证据（本机，不入仓）

- 克隆：`_scratch/ming-atlas/`（307 MB，浅克隆）
- 线上截图：`mingoff/.test-tmp/atlas-01-empire.png`（天下）、
  `atlas-02-京师.png`（京师六部组织图）、`atlas-04-mobile.png`（手机版）
- 关键文件：`lib/office-people.ts`、`scripts/history_model.py`、
  `scripts/history_import.py`、`scripts/history_snapshot.py`、`scripts/prepare-history.py`、
  `public/data/history-provenance.html`、`DEPLOYMENT.md`、`scripts/check-office-scope.mjs`
