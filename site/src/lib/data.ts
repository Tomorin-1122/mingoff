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

/** 崇祯年号纪年（当前数据主体；其他年号后续按需扩展） */
const ERAS: [number, string, number][] = [
  [1402, "建文", 4],
  [1425, "洪熙", 1],
  [1620, "泰昌", 1],
  [1627, "崇禎", 17],
];
export function eraYear(year: number): string | null {
  for (let i = ERAS.length - 1; i >= 0; i--) {
    const [start, name, span] = ERAS[i];
    if (year >= start && year < start + span) {
      const n = year - start + 1;
      return `${name}${n === 1 ? "元" : n}年`;
    }
  }
  return null;
}

/** 排序：起点升序，同人相邻 */
export const SORTED_TENURES = [...TENURES].sort(
  (a, b) =>
    a.start_year - b.start_year ||
    (a.start_month ?? 0) - (b.start_month ?? 0) ||
    a.person.localeCompare(b.person, "zh-Hant")
);

/** 某年在任的段（D8：边界为 null 的宁可多列——本管线月 null 但年必有值） */
export function inOffice(year: number): Tenure[] {
  return TENURES.filter((t) => t.start_year <= year && year <= t.end_year);
}
