# -*- coding: utf-8 -*-
"""数据库 schema —— PRD 第 6 节「初版四表 + 校勘表」的落地。

设计要点（每条都对应 PRD 里的一条主张）：

1. **`tenure` 是核心表**，不是 `person` —— 本项目的价值在"某人某时任何职"，
   `person` 与 `office` 都是它的维度。
2. **`source_ref` 不是外键而是文本**：一条任职可能同时被《明实录》《张德信年表》
   CBDB 记载，且引用粒度不同（卷/页/条目号）。用 `tenure_source` 关联表承载，
   一条任职对应多个来源。
3. **`confidence` 是显式字段**，不是隐含判断 —— PRD 第 7 节明写"不追求绝对正确，
   不确定性显式标注"。
4. **`discrepancy` 表让异文成为一等公民**：多源冲突不是"数据脏"，是本项目要做
   出来给人看的东西。
5. 时间用 `start_year/end_year` 整数 + 可空的月，**不用日期类型** —— 明代史料
   多数只到年，硬凑月日会造假精度。`None` 表示"史料未载"，与 0 含义不同。

所有表都带 `note` 字段留人工注记；`source` 表带 `url` 以便"一键跳转原文出处"。
"""
from __future__ import annotations

SCHEMA_VERSION = 1

#: 任职类型。PRD 要求区分实授/署理/加衔 —— 这是明代职官研究的关键区分：
#: 兵部尚書（实授）、權兵部尚書（署理）、兵部尚書銜（加衔，如督师带衔）是三种
#: 完全不同的政治事实，混为一谈会让"历任兵部尚书"的统计出错。
TENURE_TYPES = (
    "实授",   # 正式任命
    "署理",   # 代理/署任，如"權""署"
    "加衔",   # 加官虚衔，如督师带兵部尚书衔
    "管",     # 管事
    "检校",   # 检校
)

#: 离任原因。PRD 列举：致仕/下狱/战死/自尽/降贼/丁忧/调任。
LEAVE_REASONS = (
    "致仕", "下狱", "战死", "自尽", "降贼", "丁忧", "调任",
    "罢免", "迁转", "卒于任", "其他",
)

#: 史料来源类型。前三项是 PRD 4.1 确定的数据源。
SOURCE_TYPES = (
    "CBDB",           # 主数据底座（结构化履历）
    "明实录",          # 出处检索与校勘
    "张德信年表",      # 权威现代整理本，含署理区分
    "明史",           # 《明史·七卿年表》等
    "会典",           # 《大明会典》
    "方志",
    "文集",
    "碑传",
    "其他",
)

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ============ 人物 ============
CREATE TABLE IF NOT EXISTS person(
  person_id     INTEGER PRIMARY KEY,
  name_chn      TEXT NOT NULL,          -- 中文姓名
  name_proper   TEXT,                   -- 拼音/英文，便于与 CBDB 对齐
  birth_year    INTEGER,                -- 生年，NULL = 未载
  death_year    INTEGER,
  native_addr   TEXT,                   -- 籍贯
  bio           TEXT,
  -- 与外部库对齐：CBDB 的 personid。留空表示尚未对齐
  cbdb_id       INTEGER,
  note          TEXT,
  created_at    TEXT,
  updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_person_name ON person(name_chn);
CREATE UNIQUE INDEX IF NOT EXISTS idx_person_cbdb
  ON person(cbdb_id) WHERE cbdb_id IS NOT NULL;

-- ============ 官职 ============
CREATE TABLE IF NOT EXISTS office(
  office_id        INTEGER PRIMARY KEY,
  office_chn       TEXT NOT NULL,       -- 「兵部尚書」
  pinyin           TEXT,
  office_type      TEXT,                -- 文/武/内官等
  parent_office_id INTEGER REFERENCES office(office_id),  -- 官职树：兵部 → 兵部尚書
  department       TEXT,                -- 所属衙门
  dynasty_scope    TEXT DEFAULT '明',
  note             TEXT,
  created_at       TEXT,
  updated_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_office_name ON office(office_chn);
CREATE INDEX IF NOT EXISTS idx_office_parent ON office(parent_office_id);

-- ============ 任职（核心表）============
CREATE TABLE IF NOT EXISTS tenure(
  tenure_id     INTEGER PRIMARY KEY,
  person_id     INTEGER NOT NULL REFERENCES person(person_id),
  office_id     INTEGER NOT NULL REFERENCES office(office_id),
  start_year    INTEGER,                -- NULL = 史料未载，不是 0
  end_year      INTEGER,
  start_month   INTEGER,                -- 多数史料只到年，月常为 NULL
  end_month     INTEGER,
  -- 任职类型：见 TENURE_TYPES。NOT NULL 因为"什么性质的任命"是本表的核心信息
  tenure_type   TEXT NOT NULL DEFAULT '实授',
  leave_reason  TEXT,                   -- 见 LEAVE_REASONS
  -- 置信度 0.0~1.0。PRD 要求显式标注不确定性
  confidence    REAL DEFAULT 0.5,
  note          TEXT,
  created_at    TEXT,
  updated_at    TEXT,
  CHECK (tenure_type IN ('实授','署理','加衔','管','检校')),
  CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
  -- 起止年颠倒视为录入错误（允许单边为 NULL）
  CHECK (start_year IS NULL OR end_year IS NULL OR start_year <= end_year)
);
CREATE INDEX IF NOT EXISTS idx_tenure_person ON tenure(person_id);
CREATE INDEX IF NOT EXISTS idx_tenure_office ON tenure(office_id);
CREATE INDEX IF NOT EXISTS idx_tenure_years ON tenure(start_year, end_year);

-- ============ 史料来源 ============
CREATE TABLE IF NOT EXISTS source(
  source_id    INTEGER PRIMARY KEY,
  source_name  TEXT NOT NULL,           -- 见 SOURCE_TYPES
  citation     TEXT,                    -- 完整引用文字（卷次/篇名）
  url          TEXT,                    -- 在线原文出处（识典/中研院）
  url_type     TEXT,                    -- shidianguji / sinica / ...
  note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_name ON source(source_name);

-- ============ 任职 ↔ 来源（一条任职可有多源）============
CREATE TABLE IF NOT EXISTS tenure_source(
  tenure_id   INTEGER NOT NULL REFERENCES tenure(tenure_id) ON DELETE CASCADE,
  source_id   INTEGER NOT NULL REFERENCES source(source_id) ON DELETE CASCADE,
  -- 该来源对这条任职的记载是否与其他来源冲突（冗余但查起来快）
  is_primary  INTEGER DEFAULT 0,
  note        TEXT,
  PRIMARY KEY (tenure_id, source_id)
);

-- ============ 异文 / 待校勘 ============
CREATE TABLE IF NOT EXISTS discrepancy(
  discrepancy_id INTEGER PRIMARY KEY,
  tenure_id   INTEGER REFERENCES tenure(tenure_id) ON DELETE CASCADE,
  source_a    INTEGER REFERENCES source(source_id),
  source_b    INTEGER REFERENCES source(source_id),
  field       TEXT NOT NULL,            -- 冲突字段：start_year / office_chn / ...
  value_a     TEXT,
  value_b     TEXT,
  status      TEXT NOT NULL DEFAULT '待校',
  note        TEXT,
  CHECK (status IN ('待校','已校','存疑')),
  CHECK (field <> '')
);
CREATE INDEX IF NOT EXISTS idx_discrepancy_status ON discrepancy(status);
CREATE INDEX IF NOT EXISTS idx_discrepancy_tenure ON discrepancy(tenure_id);

-- ============ 元信息（schema 版本、导入批次）============
CREATE TABLE IF NOT EXISTS meta(
  key   TEXT PRIMARY KEY,
  value TEXT
);
"""
