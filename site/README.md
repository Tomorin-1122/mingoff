# MingOff 正式站（site/）

Next.js 15 静态导出站。按老板验收的 `web/demo.template.html` 逐项复刻（D24），
数据为 **v3 重建版**（D25）：全朝内阁 184 任职段 / 163 人；**部院六部+都察院**
1,196 段 / 789 实体（D46，2026-10-19 接入）。画布自洪武元年（1368）起，
崇祯十七年三月（1644.3）断限。

## 快速上手

```powershell
# 1. 数据更新（仓库根 mingoff/）
$env:PYTHONPATH="src"; python -m mingoff.official
$env:PYTHONPATH="src"; python -m mingoff.official_buyuan

# 2. 同步到站点
Copy-Item src/mingoff/data/official_cabinet.json site/src/data/cabinet.json
Copy-Item src/mingoff/data/official_buyuan.json site/src/data/buyuan.json

# 3. 构建（site/）
pnpm install
pnpm build        # 产物在 out/，静态文件可直接部署
```

本地预览：`npx serve out -l 3456`（静态导出不能用 `next start`）。

## 与 demo 的对应

| demo（web/demo.template.html） | 正式站（site/） |
|---|---|
| fixed 页头 + 滑块 + 无限画布 | 同（滑块并入页头——demo 里滑块实际被页头遮住，这里修掉） |
| 月格等宽（26px/月，像素统一坐标） | 同，`slotOf/span` 全像素 |
| 单帝朱色行 + 年周岁小字 | **17 帝段单行**（英宗两度临御分正統/天順），1368–1644.3 |
| 9 个职位行 + 泳道 | **内阁 + 六部 + 都察院 8 行**（D46）；六部可折叠、预留侍郎泳道；洪武—建文三年内阁留空并标注 |
| 年份刻度/月刻度/年列线/断限线 1644.3 | 同 |
| 游标 + 在任高亮/不在任淡化 | 同（`is-idle`） |
| 悬浮同人跨行联动 | 同（`peer`，按 `person_id` 区分同名） |
| 详情抽屉：任期/精度/性质/离任/置信度/出处/原文 | 同 + 《明實錄》命中块 + CBDB 正名 + 归属依据/原书页/缺口年 |
| 点击空白跳月、←/→ 逐月 | 同，另加 Shift+←/→ 逐年 |
| —— | **17 个年号跳转 chip**（全朝 86,000px 画布） |
| —— | **分期名带**（D46）：都察院行（御史臺/都察院/御史府）、倉場子行（京儲/倉場/總倉場） |

## 数据（v3 + 部院 D46）

`src/data/cabinet.json` = `official.py` 导出物；`src/data/buyuan.json` = `official_buyuan.py` 导出物：

- `cabinet.tenures[]`：内阁 **184 段**（1402–1644.3），字段含 `cbdb_id/cbdb_name`、`leave`、
  `end_clamped`、`confidence`；
- `buyuan.tenures[]`：部院 12 衙 **1,196 段 / 789 实体**（1368–1644.3），另有
  `person_id/person_label`（同名拆分）、`office_status`（D-11 归属依据）、
  `gap_years`（缺行合并）、`start_book_page/end_book_page`；
- `rows.ts`：展示层行/泳道配置——六部折叠、御史系列合并、倉場归戶部子行、分期名带；
- `shilu{}`：内阁 155 人 + 部院 130 人命中合并；
- `person_profiles.json`：现仅内阁 167 人；部院人物抽屉用 CBDB 链接兜底（待扩展）。

### 人物抽屉的外链与信息

- **CBDB**：直接链到人物页 `https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=<id>`；
  显示 CBDB 正名（如 楊士奇→楊寓、張孚敬→張璁）。
- **中研院「明代職官資料庫」**：站内检索是 POST，不能把检索词编码进普通 URL；
  抽屉提供「中研院一鍵檢索（明實錄）」按钮，用隐藏表单 `POST output.php`
  （`input[]=人名` + `check[]=3`）新窗口打开结果；另保留检索入口
  `https://dh.rchss.sinica.edu.tw/MingChaoffTitle/` 作为兜底。
- **人物小传**块显示生卒/籍贯/字号/入仕/历任；未对齐 CBDB 的人物显示
  「CBDB 未对齐」并仍给中研院入口，不硬挂 id。

### 重建做了什么（D25）

1. 重写表格解析：**保留无注文人名行**、展开 colspan/rowspan、容错年号头；
   OCR 缺块（1403/1408/1424/1479–81/1515/1567/1609–11）以原书 PDF 页补录；
2. 人-年 594 → 1,039；任职段 360（事件碎片）→ **192（连续任期）**；
   起月覆盖 47% → 98%（明确入职事件与本年纪月分开计置信度）；
3. D15：**剔除 1644 年三月后的南明任命**（高弘圖、王應熊 1644、史可法、
   馬士英、王鐸、姜曰廣），末任截到 1644.3；
4. CBDB 修复：旧映射 5 处错挂（楊士奇→楊寓 66729、楊溥 66746、曹鼐 67222、
   張孚敬→張璁 68266、方逢年 339044），并补 15 人；7 人因 CBDB 无可靠候选留 NULL。
5. **去重**：人名归一后同一人同年重复（1402 解縉、1441 曹鼐）已合并；
   另据原书补 1403 年解縉（OCR 丢行），解縉现为 1402–1407 单段。

## 纪律

- `NULL ≠ 0`：月份未载 → `null`，条上以左端虚线开口表示「起月未载」；
- 断限：截断产物（`end_clamped`）与史料原记月份在抽屉里分开陈述（D17）；
- 南明不做：1644 年三月后的任命一律不入库（D15）；
- 实录原文不批量入自建库，只在抽屉展示与任期相关的命中并给出处（D10）；
- 数据 CC BY-NC-SA 4.0，代码 Apache-2.0（D11）；字体系统回退，无 Google Fonts。

## 已知限制

- CBDB 有 7 人无可靠候选（陳山、劉宇、黃立極、王一寧、蔣德璟、蔡奕琛、高夢箕），
  其中后两人已是 1645 南明、不进入正式数据；其余保持 `cbdb_id = null`，不硬挂。
- 起月 98% 中含“本年第一个人名事件月”的 fallback（置信度 0.6/0.7），
  详情抽屉不把它冒充“精确到月”的入职事件。
