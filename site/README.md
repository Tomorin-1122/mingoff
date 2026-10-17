# MingOff 正式站（site/）

Next.js 15 静态导出站。**数据来自正式管线 `python -m mingoff.official`，
不包含 demo 数据**（D21）。

## 快速上手

```powershell
# 1. 数据更新（仓库根 mingoff/）
$env:PYTHONPATH="src"; python -m mingoff.official
#   → src/mingoff/data/official_cabinet.json

# 2. 同步到站点
Copy-Item src/mingoff/data/official_cabinet.json site/src/data/cabinet.json

# 3. 构建（site/）
pnpm install
pnpm build        # 产物在 out/，静态文件可直接部署
```

本地预览：`npx serve out -l 3456`（静态导出不能用 `next start`）。

## 结构

```
site/
├─ src/app/            页面（page.tsx 时间轴 + timeline.css）
├─ src/components/Timeline.tsx   月格等宽时间轴（D16/D19 几何，React 移植版）
├─ src/lib/data.ts     数据类型 + 干支/年号 + 在任查询（D8 宁可多列）
├─ src/data/cabinet.json         正式数据（official.py 导出的副本）
└─ next.config.ts      output: "export"（D22 静态导出）
```

## 设计令牌

沿用 `docs/界面设计方向.md`：墨 `#1B1A17` / 宣 `#FBFAF7` / 靛 `#1F3A5F` /
朱 `#A8322D`（只用于"不确定"语义）。字体三级：思源宋体（标题/年号）、
思源黑体（正文）、IBM Plex Mono（数据）。

## 纪律

- 月份未载显示为空（NULL ≠ 0，D4）；起月未载的条用渐隐形态区分
- 实录原文不内嵌（D10）；置信度 ≤ 0.8
- 数据许可 CC BY-NC-SA 4.0，代码 Apache-2.0（D11）
