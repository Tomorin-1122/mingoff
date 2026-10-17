import cabinet from "@/data/cabinet.json";

/** 任职段（与 official.py 导出 schema 一一对应，D23） */
export interface Tenure {
  person: string;
  cbdb_id: number | null;
  office: string;
  start_year: number;
  start_month: number | null;
  end_year: number;
  end_month: number | null;
  month_conflict: boolean;
  confidence: number;
  enter_verbs: string[];
  leave_verbs: string[];
  note: string;
  years: number[];
}

export interface CabinetMeta {
  dataset: string;
  version: number;
  source: string;
  pipeline: string;
  generated_at: string;
  stats: {
    tenures: number;
    persons: number;
    years_covered: [number, number];
    with_start_month: number;
    with_end_month: number;
    cbdb_aligned: number;
  };
}

const doc = cabinet as { meta: CabinetMeta; tenures: Tenure[] };

export const META = doc.meta;
export const TENURES = doc.tenures;

export const MIN_YEAR = doc.meta.stats.years_covered[0];
export const MAX_YEAR = doc.meta.stats.years_covered[1];

/** 崇祯十七年三月断限（D15/D17；数据目前只到 1644，界面先按年收口） */
export const END_LIMIT = 1644;

/** 干支（供年轴标注；60 甲子循环） */
const GAN = "甲乙丙丁戊己庚辛壬癸";
const ZHI = "子丑寅卯辰巳午未申酉戌亥";
export function ganzhi(year: number): string {
  const i = (year - 4) % 60; // 公元 4 年 = 甲子
  return GAN[((i % 10) + 10) % 10] + ZHI[((i % 12) + 12) % 12];
}

/** 年号表（era 起始公元年）。洪武元年前不入画布（数据自 1402 始）。 */
const ERAS: [string, number][] = [
  ["洪武", 1368], ["建文", 1399], ["永樂", 1403], ["洪熙", 1425],
  ["宣德", 1426], ["正統", 1436], ["景泰", 1450], ["天順", 1457],
  ["成化", 1465], ["弘治", 1488], ["正德", 1506], ["嘉靖", 1522],
  ["隆慶", 1567], ["萬曆", 1573], ["泰昌", 1620], ["天啟", 1621],
  ["崇禎", 1628],
];

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

/** 年号纪年：「1628」→「崇禎元年」、「1568」→「隆慶二年」。
    1620 特例：泰昌八月始改元，是年通行称萬曆四十八年。 */
export function eraLabel(year: number): string {
  if (year === 1620) return "萬曆四十八年";
  let name = "洪武";
  let start = 1368;
  for (const [n, s] of ERAS) {
    if (year >= s) { name = n; start = s; }
  }
  return `${name}${CN_NUM[year - start + 1] ?? year - start + 1}年`;
}

/** 皇帝世系行（在位区间按年号纪月；画布自 1402 始）。
    英宗两度临御（正統/天順），庙号同、行内注明两个年号。 */
export interface Reign {
  temple: string;
  dept: string;
  startY: number;
  startM: number;
  endY: number;
  endM: number;
  barLabel: string;
}
export const REIGNS: Reign[] = [
  { temple: "惠帝", dept: "建文", startY: 1402, startM: 1, endY: 1402, endM: 12, barLabel: "建文" },
  { temple: "成祖", dept: "永樂", startY: 1403, startM: 1, endY: 1424, endM: 12, barLabel: "永樂" },
  { temple: "仁宗", dept: "洪熙", startY: 1425, startM: 1, endY: 1425, endM: 12, barLabel: "洪熙" },
  { temple: "宣宗", dept: "宣德", startY: 1426, startM: 1, endY: 1435, endM: 12, barLabel: "宣德" },
  { temple: "英宗", dept: "正統", startY: 1436, startM: 1, endY: 1449, endM: 12, barLabel: "正統" },
  { temple: "代宗", dept: "景泰", startY: 1450, startM: 1, endY: 1456, endM: 12, barLabel: "景泰" },
  { temple: "英宗", dept: "天順（復辟）", startY: 1457, startM: 1, endY: 1464, endM: 12, barLabel: "天順" },
  { temple: "憲宗", dept: "成化", startY: 1465, startM: 1, endY: 1487, endM: 12, barLabel: "成化" },
  { temple: "孝宗", dept: "弘治", startY: 1488, startM: 1, endY: 1505, endM: 12, barLabel: "弘治" },
  { temple: "武宗", dept: "正德", startY: 1506, startM: 1, endY: 1521, endM: 12, barLabel: "正德" },
  { temple: "世宗", dept: "嘉靖", startY: 1522, startM: 1, endY: 1566, endM: 12, barLabel: "嘉靖" },
  { temple: "穆宗", dept: "隆慶", startY: 1567, startM: 1, endY: 1572, endM: 12, barLabel: "隆慶" },
  { temple: "神宗", dept: "萬曆", startY: 1573, startM: 1, endY: 1620, endM: 7, barLabel: "萬曆" },
  { temple: "光宗", dept: "泰昌（在位一月）", startY: 1620, startM: 8, endY: 1620, endM: 12, barLabel: "泰昌" },
  { temple: "熹宗", dept: "天啟", startY: 1621, startM: 1, endY: 1627, endM: 12, barLabel: "天啟" },
  { temple: "明思宗朱由檢", dept: "在位", startY: 1628, startM: 1, endY: 1644, endM: 3, barLabel: "崇禎" },
];

/** 排序：起点升序，同人相邻 */
export const SORTED_TENURES = [...TENURES].sort(
  (a, b) =>
    a.start_year - b.start_year ||
    (a.start_month ?? 0) - (b.start_month ?? 0) ||
    a.person.localeCompare(b.person, "zh-Hant")
);

/** 某年某月在任的段（含边界模糊者——D8 宁可多列） */
export function inOffice(year: number, month = 1): Tenure[] {
  const em = month ?? 12;
  return TENURES.filter((t) => {
    const sy = t.start_year, sm = t.start_month ?? 1;
    const ey = t.end_year, emx = t.end_month ?? 12;
    if (t.month_conflict) return year >= sy && year <= ey;
    return sy * 12 + sm <= year * 12 + em && year * 12 + em <= ey * 12 + emx;
  });
}

/** 泳道分配（demo assignLanes 同款区间图着色）：互不重叠的段共用一条 */
export function assignLanes(list: Tenure[]): Tenure[][] {
  const sp = (t: Tenure): [number, number] => {
    const s = (t.start_year - MIN_YEAR) * 12 + (t.start_month ?? 1) - 1;
    const e = (t.end_year - MIN_YEAR) * 12 + (t.end_month ?? 12) - 1;
    return [s, e];
  };
  const sorted = [...list].sort((a, b) => {
    const [as, ae] = sp(a), [bs, be] = sp(b);
    return as - bs || be - bs - (ae - as);
  });
  const lanes: Tenure[][] = [];
  for (const t of sorted) {
    const [s] = sp(t);
    let placed = false;
    for (const lane of lanes) {
      const last = lane[lane.length - 1];
      const [, le] = sp(last);
      if (s > le) { lane.push(t); placed = true; break; }
    }
    if (!placed) lanes.push([t]);
  }
  return lanes;
}

export const CN_MONTHS = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"];
