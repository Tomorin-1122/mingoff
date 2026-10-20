import cabinet from "@/data/cabinet.json";
import buyuan from "@/data/buyuan.json";
import profiles from "@/data/person_profiles.json";
import buyuanProfiles from "@/data/person_profiles_buyuan.json";

/* ============================================================
 * 正式数据（D23 v3 + D46 部院接入）
 *   - cabinet：张德信《明代职官年表》册1「內閣」逐年名单重建的任职段
 *   - buyuan ：同书「部院大臣年表（京師）」，六部 + 都察院等 12 衙
 *   - shilu  ：中研院《明實錄》检索命中（与本人任期相关者，每人最多 8 条）
 * 画布从洪武元年（1368）开始，内阁 1402 年始设，之前留空。
 * ============================================================ */

/** 任职段（与 official.py / official_buyuan.py 导出 schema 对应） */
export interface Tenure {
  person: string;
  /** 部院：同名拆分后的实体键（內閣数据无此字段） */
  person_id?: string;
  /** 部院：同名拆分后的展示名（如「顧佐（1429–1436）」） */
  person_label?: string;
  cbdb_id: number | null;
  cbdb_name: string | null;
  office: string;
  /** 部院：原书表头（与 office 可能不同，如「總會場」） */
  office_raw?: string;
  /** 部院：行→衙归属依据（D-11）：row-order / mixed / name-anchor / page-verified */
  office_status?: string | null;
  tenure_type: string;
  start_year: number;
  start_month: number | null;
  end_year: number;
  end_month: number | null;
  month_conflict: boolean;
  end_clamped: boolean;
  confidence: number;
  leave: string;
  note: string;
  years: number[];
  /** 部院：1–2 年 OCR 缺行合并的缺口年（前端画虚线段，D-11） */
  gap_years?: number[];
  /** 部院：gap 合并前的段数 */
  merged_segments?: number;
  /** 部院：原书页码（起/止） */
  start_book_page?: number | null;
  end_book_page?: number | null;
  /** 部院：同名风险（同名多实体） */
  same_name_risk?: boolean;
}

/** 《明實錄》单条命中（中研院检索结果） */
export interface ShiluHit {
  year: number;
  era: string | null;
  era_year: number | null;
  month: number | null;
  leap: boolean;
  source: string;
  content: string;
}

export interface ShiluBlock {
  count: number;
  hits: ShiluHit[];
}

export interface CabinetMeta {
  dataset: string;
  version: number;
  canvas_from: number;
  source: string;
  pipeline: string;
  generated_at: string;
  stats: {
    tenures: number;
    persons: number;
    years_covered: number[];
    with_start_month: number;
    with_end_month: number;
    cbdb_aligned: number;
    with_leave: number;
    shilu_persons: number;
    shilu_hits: number;
    person_years: number;
  };
}

export interface BuyuanMeta {
  dataset: string;
  version: number;
  canvas_from: number;
  source: string;
  pipeline: string;
  generated_at: string;
  stats: {
    tenures: number;
    persons: number;
    display_persons: number;
    split_entities: number;
    same_name_entities: number;
    offices: string[];
    gap_merged_tenures: number;
    gap_years_total: number;
    years_covered: number[];
    with_start_month: number;
    with_end_month: number;
    with_start_page: number;
    with_end_page: number;
    cbdb_aligned: number;
    with_leave: number;
    shu_li: number;
    same_name_risk: number;
    office_status_dist: Record<string, number>;
    shilu_persons: number;
    shilu_hits: number;
    person_years: number;
  };
}

const doc = cabinet as {
  meta: CabinetMeta;
  tenures: Tenure[];
  shilu: Record<string, ShiluBlock>;
};

const buyuanDoc = buyuan as {
  meta: BuyuanMeta;
  tenures: Tenure[];
  shilu: Record<string, ShiluBlock>;
};

export const META = doc.meta;
export const CABINET_TENURES = doc.tenures;
export const BUYUAN_META = buyuanDoc.meta;
export const BUYUAN_TENURES = buyuanDoc.tenures;

/** 两套数据的实录命中合并（内阁 155 人 + 部院 130 人，取并集） */
export const SHILU: Record<string, ShiluBlock> = {
  ...doc.shilu,
  ...buyuanDoc.shilu,
};

/* ================= 人物小传（CBDB） ================= */

export interface AltName {
  type: string;
  name: string;
}

export interface OfficeRecord {
  office: string;
  from: number | null;
  to: number | null;
}

export interface PersonProfile {
  cbdb_id: number | null;
  cbdb_name: string | null;
  birth: number | null;
  death: number | null;
  death_age: number | null;
  native_place: string | null;
  alt_names: AltName[];
  entry: { year: number | null; desc: string }[];
  offices: OfficeRecord[];
  office_total: number;
}

const profileDoc = profiles as unknown as {
  meta: {
    cbdb_person_url: string;
    sinica_url: string;
    sinica_output_url: string;
  };
  persons: Record<string, PersonProfile>;
};

export const PROFILES = profileDoc.persons;
export const PROFILE_META = profileDoc.meta;

/** 部院人物小传：按 person_id 键（顧佐#1 / 顧佐#2 各自独立，D46） */
const buyuanProfileDoc = buyuanProfiles as unknown as {
  meta: { persons: number; with_cbdb_id: number };
  persons: Record<string, PersonProfile>;
};

export const BUYUAN_PROFILES = buyuanProfileDoc.persons;
export const BUYUAN_PROFILE_META = buyuanProfileDoc.meta;

/** 年份区间显示：缺一端用 ?，两端皆缺用「未載」 */
export function fmtYearRange(a: number | null, b: number | null): string {
  if (!a && !b) return "未載";
  return `${a ?? "?"}–${b ?? "?"}`;
}

/** 断限：崇祯十七年三月（D15/D17）。画布与数据都止于此 */
export const CUT_Y = 1644;
export const CUT_M = 3;
/** 画布起点：洪武元年（1368） */
export const CANVAS_FROM = 1368;
/** 内阁数据起点：建文四年（1402，内阁始设） */
export const DATA_FROM = META.stats.years_covered[0];
export const M_PER_YEAR = 12;
/** 画布总月格：1368.1 → 1644.3 */
export const CANVAS_SLOTS = (CUT_Y - CANVAS_FROM) * M_PER_YEAR + CUT_M;

/* ================= 干支 / 年号 ================= */

const GAN = "甲乙丙丁戊己庚辛壬癸";
const ZHI = "子丑寅卯辰巳午未申酉戌亥";

/** 干支（公元 4 年 = 甲子） */
export function ganzhi(year: number): string {
  const i = (year - 4) % 60;
  return GAN[((i % 10) + 10) % 10] + ZHI[((i % 12) + 12) % 12];
}

const CN_NUM: Record<number, string> = {
  1: "元", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七",
  8: "八", 9: "九", 10: "十", 11: "十一", 12: "十二", 13: "十三",
  14: "十四", 15: "十五", 16: "十六", 17: "十七", 18: "十八", 19: "十九",
  20: "二十", 21: "二十一", 22: "二十二", 23: "二十三", 24: "二十四",
  25: "二十五", 26: "二十六", 27: "二十七", 28: "二十八", 29: "二十九",
  30: "三十", 31: "三十一", 32: "三十二", 33: "三十三", 34: "三十四",
  35: "三十五", 36: "三十六", 37: "三十七", 38: "三十八", 39: "三十九",
  40: "四十", 41: "四十一", 42: "四十二", 43: "四十三", 44: "四十四",
  45: "四十五", 46: "四十六", 47: "四十七", 48: "四十八",
};

/** 年号起始公元年（用于「崇禎二年」式纪年） */
const ERA_TABLE: [string, number][] = [
  ["洪武", 1368], ["建文", 1399], ["永樂", 1403], ["洪熙", 1425],
  ["宣德", 1426], ["正統", 1436], ["景泰", 1450], ["天順", 1457],
  ["成化", 1465], ["弘治", 1488], ["正德", 1506], ["嘉靖", 1522],
  ["隆慶", 1567], ["萬曆", 1573], ["泰昌", 1620], ["天啟", 1621],
  ["崇禎", 1628],
];

/** 年号纪年：「1628」→「崇禎元年」。1620 年八月改元泰昌，通行记作万历四十八年 */
export function eraLabel(year: number): string {
  if (year === 1620) return "萬曆四十八年";
  let name = "洪武";
  let start = 1368;
  for (const [n, s] of ERA_TABLE) {
    if (year >= s) { name = n; start = s; }
  }
  return `${name}${CN_NUM[year - start + 1] ?? year - start + 1}年`;
}

/** 皇帝世系行：一个皇帝一段（英宗两度临御 = 正統/天順两段）。
 *  画布自 1368（洪武元年）起；内阁 1402 始设，洪武—建文三年为空。
 *  birth：生年/生月（公历月份），用于年在位行的周岁标注。 */
export interface Reign {
  temple: string;
  era: string;
  startY: number;
  startM: number;
  endY: number;
  endM: number;
  birthY: number;
  birthM: number;
  barLabel: string;
}

export const REIGNS: Reign[] = [
  { temple: "太祖", era: "洪武", startY: 1368, startM: 1, endY: 1398, endM: 12, birthY: 1328, birthM: 10, barLabel: "洪武" },
  { temple: "惠帝", era: "建文", startY: 1399, startM: 1, endY: 1402, endM: 12, birthY: 1377, birthM: 12, barLabel: "建文" },
  { temple: "成祖", era: "永樂", startY: 1403, startM: 1, endY: 1424, endM: 12, birthY: 1360, birthM: 5, barLabel: "永樂" },
  { temple: "仁宗", era: "洪熙", startY: 1425, startM: 1, endY: 1425, endM: 12, birthY: 1378, birthM: 8, barLabel: "洪熙" },
  { temple: "宣宗", era: "宣德", startY: 1426, startM: 1, endY: 1435, endM: 12, birthY: 1399, birthM: 3, barLabel: "宣德" },
  { temple: "英宗", era: "正統", startY: 1436, startM: 1, endY: 1449, endM: 12, birthY: 1427, birthM: 11, barLabel: "正統" },
  { temple: "代宗", era: "景泰", startY: 1450, startM: 1, endY: 1456, endM: 12, birthY: 1428, birthM: 9, barLabel: "景泰" },
  { temple: "英宗", era: "天順（復辟）", startY: 1457, startM: 1, endY: 1464, endM: 12, birthY: 1427, birthM: 11, barLabel: "天順" },
  { temple: "憲宗", era: "成化", startY: 1465, startM: 1, endY: 1487, endM: 12, birthY: 1447, birthM: 12, barLabel: "成化" },
  { temple: "孝宗", era: "弘治", startY: 1488, startM: 1, endY: 1505, endM: 12, birthY: 1470, birthM: 7, barLabel: "弘治" },
  { temple: "武宗", era: "正德", startY: 1506, startM: 1, endY: 1521, endM: 12, birthY: 1491, birthM: 10, barLabel: "正德" },
  { temple: "世宗", era: "嘉靖", startY: 1522, startM: 1, endY: 1566, endM: 12, birthY: 1507, birthM: 9, barLabel: "嘉靖" },
  { temple: "穆宗", era: "隆慶", startY: 1567, startM: 1, endY: 1572, endM: 12, birthY: 1537, birthM: 3, barLabel: "隆慶" },
  { temple: "神宗", era: "萬曆", startY: 1573, startM: 1, endY: 1620, endM: 7, birthY: 1563, birthM: 9, barLabel: "萬曆" },
  { temple: "光宗", era: "泰昌", startY: 1620, startM: 8, endY: 1620, endM: 12, birthY: 1582, birthM: 8, barLabel: "泰昌" },
  { temple: "熹宗", era: "天啟", startY: 1621, startM: 1, endY: 1627, endM: 12, birthY: 1605, birthM: 12, barLabel: "天啟" },
  { temple: "思宗", era: "崇禎", startY: 1628, startM: 1, endY: 1644, endM: 3, birthY: 1611, birthM: 2, barLabel: "崇禎" },
];

/** 周岁（按当年二月计：崇祯帝生日 1611-02-06 已过 → 年差；其余生日未到 → 年差减一） */
export function ageAt(year: number, month: number, r: Reign): number {
  return year - r.birthY - (month < r.birthM ? 1 : 0);
}

/** 年号跳转点（全朝导航）：画布 1368 起，洪武/建文朝无内阁记录 */
export interface EraJump {
  name: string;
  year: number;
  month: number;
}

export const ERA_JUMPS: EraJump[] = [
  { name: "洪武", year: 1368, month: 1 },
  { name: "建文", year: 1399, month: 1 },
  { name: "永樂", year: 1403, month: 1 },
  { name: "洪熙", year: 1425, month: 1 },
  { name: "宣德", year: 1426, month: 1 },
  { name: "正統", year: 1436, month: 1 },
  { name: "景泰", year: 1450, month: 1 },
  { name: "天順", year: 1457, month: 1 },
  { name: "成化", year: 1465, month: 1 },
  { name: "弘治", year: 1488, month: 1 },
  { name: "正德", year: 1506, month: 1 },
  { name: "嘉靖", year: 1522, month: 1 },
  { name: "隆慶", year: 1567, month: 1 },
  { name: "萬曆", year: 1573, month: 1 },
  { name: "泰昌", year: 1620, month: 8 },
  { name: "天啟", year: 1621, month: 1 },
  { name: "崇禎", year: 1628, month: 1 },
];

/* ================= 时间轴几何：月格等宽 ================= */

/**
 * 年月 → 画布月格号。
 * 月份未载时：起点取该年第一格，终点取该年最后一格（占满整年，D4/D8）。
 */
export function slotOf(
  year: number,
  month: number | null,
  isEnd = false
): number {
  const m =
    month == null
      ? isEnd
        ? M_PER_YEAR - 1
        : 0
      : Math.max(0, Math.min(M_PER_YEAR - 1, month - 1));
  return (year - CANVAS_FROM) * M_PER_YEAR + m;
}

export interface Span {
  s: number;
  e: number;
  /** 终年是否因断限被截到 1644.3（区分「史料记 3 月」与「截断产物」，D17） */
  clamped: boolean;
}

/** 一段任职的画布区间（格号）。断限截断在这里统一处理，前端只有一套坐标系。 */
export function span(t: Tenure): Span {
  let eY = t.end_year;
  let eM = t.end_month;
  let clamped = false;

  if (eY > CUT_Y) {
    eY = CUT_Y; eM = CUT_M; clamped = true;
  } else if (eY === CUT_Y && (eM == null || eM > CUT_M)) {
    eM = CUT_M;
    clamped = t.end_month == null || t.end_month > CUT_M;
  }

  const s = Math.max(0, slotOf(t.start_year, t.start_month, false));
  const e = Math.min(CANVAS_SLOTS - 1, Math.max(slotOf(eY, eM, true), s));
  return { s, e, clamped };
}

/** 泳道分配（区间图着色）：互不重叠的段共用一条泳道，最少泳道数 */
export function assignLanes(list: Tenure[]): Tenure[][] {
  const sp = (t: Tenure): [number, number] => {
    const { s, e } = span(t);
    return [s, e];
  };
  const sorted = [...list].sort((a, b) => {
    const [as, ae] = sp(a);
    const [bs, be] = sp(b);
    return as - bs || be - bs - (ae - as);
  });
  const lanes: Tenure[][] = [];
  for (const t of sorted) {
    const [s] = sp(t);
    let placed = false;
    for (const lane of lanes) {
      const last = lane[lane.length - 1];
      const [, le] = sp(last);
      if (s > le) {
        lane.push(t);
        placed = true;
        break;
      }
    }
    if (!placed) lanes.push([t]);
  }
  return lanes;
}

export const CN_MONTHS = [
  "正", "二", "三", "四", "五", "六",
  "七", "八", "九", "十", "十一", "十二",
];

/** 年月文本；闰月另注「閏」 */
export function fmtYM(
  y: number | null,
  m: number | null,
  leap = false
): string {
  if (y == null) return "未載";
  if (!m) return `${y}年`;
  return `${y}年${leap ? "閏" : ""}${CN_MONTHS[m - 1]}月`;
}
