# PRD 引用核查报告

> 核查日期：2026-10-16 · 方法：**逐条实测**（HTTP 状态、真实响应、数据规模、许可条款）
> 核查对象：`190508af-…_明代职官数据库需求文档(PRD).md` 与 `afa0807f-…_明实录结构化项目调研.md`
> 中提到的**每一个网站与数据库**。

---

## 一、总表

| # | PRD 提到的对象 | 实测结论 | 对项目的影响 |
|---|---|---|---|
| 1 | CBDB 在线检索 API | ✅ **可用**，端点与行为与 PRD 描述一致 | 主数据源确认可行 |
| 2 | CBDB 官方 SQLite 快照 | ✅ **存在**，`cbdb-project/cbdb_sqlite` ★235 | **回答了 PRD 待核实项 #4** |
| 3 | 中研院 明朝官职网 | ✅ 可用，`output.php` 接口**实测可用** | PRD 4.2 描述基本正确，但漏了关键参数 |
| 4 | 中研院 `wei-web` | ⚠️ **PRD 描述错误**——它是《明實錄》衛所檢索系統 | 需修正 PRD 竞品表 |
| 5 | 中研院 卫所事件平台 | ✅ 可用，事件类型分类很细 | 可用作卫所/军事事件参考 |
| 6 | 中研院 断句网 | ✅ 可用（Django + CSRF 表单） | 可作明实录断句工具 |
| 7 | 引得平台·历代职官 | ⚠️ **域名错误，但平台存在**——真名「引得数字人文资源平台」，域名 `www.inindex.com`；公网页是未配置的脚手架，需机构 IP | **修正 PRD 域名**；待机构访问才能评估 |
| 8 | CBDB Migration VisX | ❌ **GitHub 搜不到此名** | 待重新核实是否存在 |
| 9 | 全历史 AllHistory | ✅ 域名存活（商业站） | 无开放数据 |
| 10 | CText | ✅ 存活，但**需经代理** | 直连不通，非站点问题 |
| 11 | OpenKG 明代知识图谱 | ✅ **数据集真实**，CC-BY，1.77MB ZIP | **可复用**（但 TLS 证书已过期，须走 http） |
| 12 | CHisIEC | ✅ GitHub 存在（★27） | 可用于 NER 语料 |
| 13 | GuNER2023 | ❌ GitHub 搜不到此名 | 待核实 |
| 14 | **（PRD 未提及）大明职官图** | 🔴 **直接竞品，已上线 1 个月** | **最重要发现，见第四节** |

### 关键补充：CBDB 快照的许可**有硬约束**（回答 PRD 待核实项 #4）

`cbdb_sqlite/LICENSE.md` 原文实测：

> CBDB SQLite 数据库适用 [CBDB 資料授權條款](https://cbdb.hsites.harvard.edu/cbdb-data-licensing-terms)
> （**2026 年 8 月 20 日起生效**）：于当前 CBDB 单机版发布日期当日或之前发布、
> 且在其数据量范围内者仍适用 **CC BY-NC-SA 4.0**，**其餘適用 CBDB 自訂條款**。
> 代码（`scripts/` 等）采用 CC BY-NC-SA 4.0。

**这是本项目的硬约束**：CC BY-NC-SA 4.0 = **署名 + 限非商业 + 相同方式共享**。
含义有三：

1. **不能商用**，且**衍生数据必须以相同许可发布**（ShareAlike 有传染性）；
2. 「其餘適用 CBDB 自訂條款」意味着**新数据可能不是 CC BY-NC-SA**，
   导入前必须逐批确认适用哪一套；
3. 若 MingOff 想用 MIT/Apache 开源，**CBDB 衍生部分必须单独声明为 CC BY-NC-SA**，
   不能整体套一个宽松许可——这与 PRD 3.2「开源，吸引学术协作」的设想有张力。

**当前最新快照**（实测 `latest.json`）：

```json
{
  "sqlite_filename": "cbdb_20261010.sqlite3",
  "sha256": "b43de31b298546ad8605ab52cd78d2a70d7b946abc01bf0d4efd18dd7853782d",
  "generated_at_utc": "2026-10-10T19:17:07Z",
  "huggingface_url": "https://huggingface.co/datasets/cbdb/cbdb-sqlite/resolve/main/history/cbdb_202610/cbdb_20261010.zip"
}
```

**生成于 6 天前，带 SHA-256 校验**——说明它确实在持续更新，可作长期数据底座。
（`cbdb.hsites.harvard.edu` 的条款页返回 403，需人工用浏览器确认条款全文。）

> ⚠️ 竞品「大明职官图」自述其在**同一批数据上采用了 CC BY-NC-SA 4.0**，
> 与上述条款一致。这说明该许可链条是实际在跑的，不是纸面条款。

---

## 二、逐条实测细节

### 1. CBDB 在线检索 API ✅

```
GET https://input.cbdb.fas.harvard.edu/api/select/search/office?q=兵部尚書
→ 200，7,983 字节，17 条结果
GET 同端点 q=兵部尚书（简体）
→ 200，787 字节，0 条结果
```

**PRD 说「官职须繁体，简体 0 条」——完全属实。**

返回字段（实测）：`c_office_id`, `c_dy`(朝代码), `c_office_pinyin`,
`c_office_chn`, `c_office_trans`(Hucker 英译), `c_source`, `c_pages`, `c_notes`。

**对本项目的直接价值**——CBDB 实测确实区分实授/署理/加衔，与 MingOff 的
`tenure_type` 词表可一一对应：

| CBDB 官职 | Hucker 英译 | 对应 MingOff 类型 |
|---|---|---|
| 兵部尚書 (id=142) | Minister of the Ministry of War | `实授` |
| **權兵部尚書** (id=2507) | **Provisional** Minister | `署理` |
| **檢校兵部尚書** (id=354) | **Acting** Minister | `檢校` |

> ⚠️ 注意：同名官职有多个 id（兵部尚書 出现 142 / 3771 / 3842 / 10027 / 60082），
> 按 `c_dy` 区分朝代。导入时**必须用 id 而非名称**关联，否则会串朝代。

### 2. CBDB 官方 SQLite 快照 ✅ —— 回答 PRD 待核实项 #4

```
github.com/cbdb-project/cbdb_sqlite   ★235  fork 38
描述: The latest SQLite version of the China Biographical Database
创建 2019-11-14  最后推送 2026-10-10（活跃维护）
许可: NOASSERTION（需人工确认条款）
```

**这就是 PRD 4.1 指定的「主数据底座」，且一直在更新。** 待确认：具体许可
文字（GitHub 显示 NOASSERTION 表示未用标准 SPDX 标识，不等于无许可）。

### 3. 中研院 明朝官职网 ✅ —— PRD 4.2 基本正确，但有遗漏

PRD 原文：「`output.php`（POST，`input[]`+`check[]`），返回《明实录》原文+出处」

**实测订正**：`check[]` 的值是 **`1`/`2`/`3`**，不是中文标签：

```html
<form method="post" action="output.php">
  <input name="input[]" required>
  <input type="checkbox" name="check[]" value="1">   ← 人名
  <input type="checkbox" name="check[]" value="2">   ← 官職
  <input type="checkbox" name="check[]" value="3">   ← 明實錄
```

用对取值后实测（检索「兵部尚書」）：

| `check[]` | 返回 | 内容 |
|---|---|---|
| `2`（官職） | 5.7 MB | **权威号 / 姓名 / 職類類型 / 出身 / 原始紀錄 / 整理後紀錄 / 隸屬部門 / 官職隸屬類型** |
| `1` 或 `3` | 4.2 MB | **時間 / 年號 / 出處 / 內容**（明實錄原文） |

**这是本项目最有价值的外部数据源**：`check[]=2` 直接给出结构化任职记录，
含「兵部尚書(太子太保兼)」这类**加衔**写法，正是 PRD 5.2 校勘功能所需。

> ⚠️ 两个工程注意点：① 单次响应 **4~6 MB**，不是 JSON 而是 HTML 表格，
> 解析要流式处理；② 表单要求 `check[]` 至少一项，否则返回「請選擇至少勾選一個！」。

### 4. 中研院 `wei-web` ⚠️ PRD 描述错误

PRD 竞品表把它描述成「**明朝官职网互动式呈现**：官职履历表 + 时间轴 + 共现图 +
地图」。**实测其 `<title>` 是《明實錄》衛所檢索系統**：

```
<title>《明實錄》衛所檢索系統</title>
表单字段: search, ToSearch, SearchMode, SearchTimeMin, SearchTimeMax
端点: SearchData.php, index.php
```

它做的是**卫所检索**，不是官职履历可视化。**PRD 的竞品表需要修正**——
否则会基于错误认知判断"差异化窗口"。

### 5. 中研院 卫所事件平台 ✅

`<title>明實錄衛所事件`，事件类型分类很细且已枚举（可用于我们的受控词表参考）：

天災（因災免稅/火災/雨雹/地震）· 賞懲（賞殺賊功/因罪謫戍/因過降職）·
行政設置（襲職/任命/置衛設員/陞職/銓註）· 外交（貢賞/來歸/寇邊）·
軍事（派命守邊/平亂/命管操）· 軍役（修築/造船漕運/操練/鹽糧分配/屯田）·
宮廷相關（遣祭/賜祭葬/冊封）

### 6. 中研院 断句网 ✅

`<title>Automatic Punctuation for Ming Shilu`，Django 表单（含
`csrfmiddlewaretoken`），提供 Punctuation 与 NER 两个提交按钮。

### 7. 引得平台 ⚠️ PRD 域名错误，但平台真实存在

`yinde.cn` **不是引得平台**，实测是**爱名网的域名待售展示页**：

> 「yinde.cn域名出售 …… 实际持有者设置了本出售展示页」

**真实平台**（经图书馆公告核实）是「**引得数字人文资源平台**」：

- 网址：**`www.inindex.com`**（实测 200）
- 收录：中国历代人物传记资料库（CBDB）、中国历代古籍文献数据库、
  中国历代地名沿革数据库、**中国历代职官数据库**、中国历代机构数据库
- 访问方式：**需机构 IP 范围内**（「在学校 IP 范围内，访问网址默认登录」）

**开放度评估（对应 PRD 待核实项 #3）**：

| 项 | 实测 |
|---|---|
| 域名 | ✅ `www.inindex.com` 存活（200） |
| 页面性质 | ⚠️ umi/Ant Design SPA，`<meta description>` 是 **"Web site created using create-react-app"**，即**未配置的脚手架** |
| `<meta keywords>` | `CBDB,数字人文,引得,元引` ← 佐证是引得平台 |
| `/api/*` | 全部返回 200，但那是 SPA 的 catch-all；`umi.js` 里只有 `/api/currentUser`、`/api/notices` 等 **Ant Design Pro 演示端点** |
| 实际可用性 | ❌ **公网无法评估**——需机构 IP 登录 |

**结论**：PRD 待核实项 #3 **仍未能核实**，但已定位到正确入口。
需老板用**校园网 IP**（浙师大图书馆）访问 `www.inindex.com` 才能评估其
「历代职官数据库」的实际数据量与开放程度。**这是需要人工完成的一步。**

> 旧记录：PRD 原文与两份调研文档均未给出引得平台域名，`yinde.cn` 疑为猜测。

### 8. CBDB Migration VisX ❌ 搜不到

GitHub 搜索 `cbdb visx` → **0 条结果**。检索 `cbdb 可视化` 得到的是另外两个项目：
- `YLDJack/CBDB-VisualizationSystem` ★61（CBDB 可视化项目）
- `believemysel/CBDB-history_figure_analysis` ★3

**PRD 待核实项 #2 未能核实**——该名称可能不准确或项目已删除。

### 9. 全历史 AllHistory ✅ 域名存活

`allhistory.com` → 200。商业站，无开放数据。

### 10. CText ✅ 存活（需代理）

直连超时（rc=28），经 Clash 7897 → **200，3.7s**。属路由问题不是站点问题。

### 11. OpenKG 明代历史知识图谱 ✅ 数据集真实可用

```
数据集页: http://data.openkg.cn/en/dataset/minghistory
许可: Creative Commons Attribution (CC-BY)
作者: 丁智；黄家名；李皓宇；孟特石
更新: 2021-12-01   下载量: 839
下载: http://data.openkg.cn/dataset/f29c044d-.../download/mingdynastykg.zip
      → Content-Type: application/zip, Content-Length: 1,774,271 (1.77 MB)
```

内容：明代重要人物、历史事件、历史地名、著作等实体 + 知识图谱可视化。

> ⚠️ **`openkg.cn` 的 TLS 证书已过期**（`SEC_E_CERT_EXPIRED`），https 直连必失败；
> 走 http 或经代理均 200。脚本里要显式处理。

### 12. CHisIEC ✅

`github.com/tangxuemei1995/CHisIEC` ★27 —— 古代中国历史信息抽取语料库
（arXiv 2403.15088 论文配套）。

### 13. GuNER2023 ❌ 搜不到

GitHub 搜索 0 条。该名称可能指 CCL23 评测任务而非独立仓库。

---

## 三、环境问题汇总（都是环境而非站点）

| 站点 | 现象 | 根因 | 解法 |
|---|---|---|---|
| `openkg.cn` | https rc=35 | **站点证书已过期** | 走 http 或代理 |
| `data.openkg.cn` | 直连 rc=7 拒绝 | 需 http | 走 http |
| `ctext.org` | 直连 rc=28 超时 | 路由 | 经 Clash 7897 |
| `raw.githubusercontent.com` | 0 字节静默失败 | 路由 | **必须经 Clash 7897** |
| `github.com` / `api.github.com` | ✅ 直连可用 | — | — |
| `yinde.cn` | 200 但非目标站 | **域名待售** | 需重新定位引得平台 |

> **教训**：`raw.githubusercontent.com` 直连会**返回 0 字节而不报错**（curl rc=0），
> 静默失败最难发现。抓取脚本必须校验响应长度，不能只看退出码。

---

## 四、🔴 最重要发现：PRD 未识别的直接竞品

`dingbo3603-ui/ming-official-atlas` —— **「大明职官图」**

| 项 | 实测 |
|---|---|
| 描述 | 明代官署、人物履历、年号检索与府州县交互图谱 |
| 技术栈 | TypeScript / React |
| 创建 | **2026-09-07**（一个月前） |
| 规模 | 786 文件 / **321.6 MB**，数据集快照 154 MB |
| 星数 | ★54 |
| 许可 | 无 LICENSE 文件；package.json 无 license 字段 |

### 它已经做到了 PRD 声称"无人占据"的事

竞品自述的历史数据整理规则（原文摘录）：

> 「首辅、掌府、协理等实际职事与**本衔、兼衔分开记录**，不从品级高低推导机关隶属」
> 「来源采用原典、学术数据库、方志及非虚构人物年表，**不采影视剧情或小说设定**」
> 「生卒及任期发现冲突时另据史源纠正，**保留原库值和更正说明**」
> 「**同名人物只有证据足以对应时才合并**」
> 「完全无日期的资料进入人物履历的'尚未明确系年'分组，**不填入年度**」

**逐条对照 MingOff / PRD 的差异化主张**：

| PRD 主张 | 竞品状态 |
|---|---|
| 「专注明代」 | ✅ 同为 1368–1644 |
| 「本衔/兼衔分开」 | ✅ **已实现**（且比我们的 `tenure_type` 表述更细） |
| 「可溯源：每条挂出处」 | ✅ 已实现（「人物卡片列出具体卷次和在线出处」） |
| 「校勘：保留异文」 | ✅ 已实现（「保留原库值和更正说明」） |
| 「不追求绝对正确」 | ✅ 已实现（「资料缺录不能当作历史空缺」） |
| 「覆盖地方官」 | ✅ 已实现（府州县、行政建置数据集） |
| 「开源」 | ⚠️ **没有 LICENSE**——这是唯一空间 |

它还额外做了 PRD 没有的：地图/地形图、朝堂与州县衙署场景、手机端独立布局、
访问分析后台。

### 结论：PRD 第 3.2 节「机会窗口」判断需要重估

PRD 说「'专注明代 + 开源 + 结构化 + 可视化 + 可校勘'组合无人占据」。
**实测：除"开源"外，全部已被一个上线一个月的项目占据**，且其校勘规则比
PRD 设想的更细致。

**但仍有三点真实空间**（需在 PRD 中明确）：

1. **许可**：竞品无 LICENSE，其 CBDB 改编数据声明为 **CC BY-NC-SA 4.0**
   （限非商业、须相同方式共享）。若 MingOff 采用不同许可，仍有区别。
2. **数据开放**：竞品把数据放在 `public/api/snapshots/` 但**无开放 API 文档**，
   且明确说"不能把本仓库视为正式数据库备份"。
3. **校勘的可验证性**：竞品的数据整理脚本「还依赖本地原始资料目录和数据库导出」，
   **不可复现**；MingOff 若做到全流程可复现（脚本+来源+版本），是实质差异。

---

## 五、对 PRD 的修订建议

1. **3.1 竞品表**：修正 `wei-web` 的描述（它是卫所检索，不是官职履历可视化）；
   新增「大明职官图」并置于首位。
2. **3.2 差异化定位**：把「开源」从并列项提升为**核心差异**，并补充
   「数据可复现/可审计」这一条。
3. **4.1 数据源**：CBDB 主数据底座**已确认可用**（`cbdb-project/cbdb_sqlite`），
   建议补上该仓库地址。
4. **4.2 实测备忘**：补上 `check[]` 的真实取值 `1`/`2`/`3`（PRD 只写了参数名）。
5. **待核实项 #3**：「引得平台」需重新定位域名——`yinde.cn` 是待售域名。
6. **待核实项 #2**：「CBDB Migration VisX」在 GitHub 上搜不到，需重新确认名称。
7. **新增待核实项**：`cbdb_sqlite` 的具体许可条款（GitHub 显示 NOASSERTION）。
8. **新增建议**：中研院 `output.php` 的 `check[]=2` 输出对校勘价值最高，
   建议列为阶段② 的接入对象。

---

## 六、核查方法与可复现性

所有核实脚本在 `_verify/` 下，可直接重跑：

| 脚本 | 核实对象 |
|---|---|
| `check_sinica.py` | 中研院四工具页面内容 |
| `check_sinica_search.py` | `output.php` 的 `check[]` 取值实测 |
| `check_output_php.py` | `output.php` 接口契约 |
| `check_openkg.py` | OpenKG 数据集规模与许可 |
| `check_github.py` | PRD 提到的 GitHub 项目是否存在 |
| `check_key_repos.py` | CBDB SQLite 快照 / 竞品基础信息 |
| `check_atlas.py` / `check_atlas_scale.py` / `check_atlas_prov.py` | 竞品规模与来源 |
| `check_provenance.py` | 竞品的数据整理规则原文 |
| `check_yinde.py` | 引得平台域名核实 |

**未核实项**（需人工或有网络条件时补）：
- `cbdb_sqlite` 的许可条款细节（需读仓库内 LICENSE 文件内容）
- 引得平台真实域名
- 「CBDB Migration VisX」「GuNER2023」的准确名称或存在性
