import {
  BUYUAN_TENURES,
  CABINET_TENURES,
  JINGQING_TENURES,
  KEJISHIZHONG_TENURES,
  type Tenure,
} from "./data";

/* ============================================================
 * 展示层「行 / 泳道」配置（D46，2026-10-19 项目负责人拍板）
 *
 * 数据层仍按 D32 保留 12 个独立 office，不做合并；这里只做**展示分组**：
 *   - 六部：各一行，可折叠；预留侍郎等副貳泳道（后续表种接入）
 *   - 都察院：御史臺 → 都察院 → 御史府 合成一行，上置「分期名带」
 *   - 總督倉場：歸於戶部，作为户部行的子行；京儲/倉場/總倉場 合成一行
 *
 * 行名固定，分期名带随年代变；不把行名本身做成随滚动跳变。
 * ============================================================ */

export type PeriodTone = "base" | "alt" | "light" | "gap";

export interface PeriodSeg {
  label: string;
  startY: number;
  startM: number;
  endY: number;
  endM: number;
  tone: PeriodTone;
  /** 悬浮说明：沿革/异说/页证 */
  note?: string;
}

export type RowKind =
  | "cabinet"
  | "ministry"
  | "censor"
  | "granary"
  | "jingqing"
  | "keji";

export interface RowDef {
  id: string;
  label: string;
  sub: string;
  tenures: Tenure[];
  offices: string[];
  periods?: PeriodSeg[];
  collapsible?: boolean;
  /** 预留泳道（尚无数，只画占位） */
  reserved?: string[];
  /** 子行：父行折叠时隐藏 */
  parent?: string;
  indent?: boolean;
  /** 所属可折叠大块（京卿/六科）：块头隐藏时整组行隐藏 */
  group?: string;
  kind: RowKind;
}

/** 可折叠大块（2026-11-07 老板拍板：京卿/六科排在部院以下，默认折叠） */
export interface GroupDef {
  id: string;
  label: string;
  sub: string;
  defaultOpen: boolean;
}

export const GROUPS: Record<string, GroupDef> = {
  jingqing: {
    id: "jingqing",
    label: "京卿年表（京師）",
    sub: `九寺八衙 ${JINGQING_TENURES.length} 任 · ${new Set(JINGQING_TENURES.map((t) => t.person_id || t.person)).size} 人`,
    defaultOpen: false,
  },
  kejishizhong: {
    id: "kejishizhong",
    label: "六科都給事中",
    sub: `六科 ${KEJISHIZHONG_TENURES.length} 任 · ${new Set(KEJISHIZHONG_TENURES.map((t) => t.person_id || t.person)).size} 人`,
    defaultOpen: false,
  },
};

/** 御史系列分期（D46：1380 与 1398 按史实校正；1399 起点存异说，见 note） */
const CENSOR_PERIODS: PeriodSeg[] = [
  {
    label: "御史臺",
    startY: 1368, startM: 1, endY: 1380, endM: 5,
    tone: "base",
    note: "洪武十三年五月罷御史臺（《明會要》卷33）。原书 1380 页表头作「都察院」，但页眉注「五月罷御史臺」、安然注「左御史中丞」；D46 按史实归御史臺。",
  },
  {
    label: "罷廢",
    startY: 1380, startM: 6, endY: 1381, endM: 12,
    tone: "gap",
    note: "洪武十三年五月罷御史臺，至十五年（1382）另置都察院，中间约两年无此机构。",
  },
  {
    label: "都察院",
    startY: 1382, startM: 1, endY: 1398, endM: 12,
    tone: "base",
    note: "洪武十五年更置都察院。原书 1398 页表头作「御史臺」，但《建文年譜》洪武三十一年十月仍称「景清署都察院左僉都御史」、《憲章類編》十二月仍有「都御史劉觀」；D46 校正为都察院。",
  },
  {
    label: "御史府",
    startY: 1399, startM: 1, endY: 1402, endM: 12,
    tone: "light",
    note: "建文改都察院為御史府（原书与《明會要》系建文元年；《憲章類編》《建文年譜》作建文二年二月，异说并存）。",
  },
  {
    label: "都察院",
    startY: 1403, startM: 1, endY: 1644, endM: 3,
    tone: "base",
    note: "靖难后复旧制，永乐元年（1403）复为都察院。",
  },
];

/** 倉場系列分期（D46：原书同一栏前后异名；1631/32「督倉場」= 總倉場省文） */
const GRANARY_PERIODS: PeriodSeg[] = [
  {
    label: "總督京儲",
    startY: 1431, startM: 1, endY: 1549, endM: 12,
    tone: "base",
    note: "原书部院表第 7 行，表头作「總督京儲」；为户部堂上官總督京通倉場糧儲之职。",
  },
  {
    label: "總督倉場",
    startY: 1550, startM: 1, endY: 1552, endM: 12,
    tone: "alt",
    note: "原书 1551 页表头作「總督倉場」，1550/1552 为对页续行，行序继承。",
  },
  {
    label: "總督京儲",
    startY: 1553, startM: 1, endY: 1555, endM: 12,
    tone: "base",
    note: "原书 1553/1555 页表头回作「總督京儲」——同一栏的异名，不是两个职位。",
  },
  {
    label: "缺載",
    startY: 1556, startM: 1, endY: 1556, endM: 12,
    tone: "gap",
    note: "1556 页第 7 行整行缺载（D-04 已出证据，待 D-11 页核补行）。",
  },
  {
    label: "總倉場",
    startY: 1557, startM: 1, endY: 1644, endM: 3,
    tone: "light",
    note: "1557 原书作「總會場」（總字印刷残缺），1559 起作「總倉場」；1631/32 竖排「督倉場」为省文，D46 归總倉場。",
  },
];

/** 内阁行（数据 1402 始，洪武—建文三年留空） */
const cabinetRow: RowDef = {
  id: "cabinet",
  label: "內閣大臣",
  sub: `內閣 ${CABINET_TENURES.length} 任 · ${new Set(CABINET_TENURES.map((t) => t.person)).size} 人`,
  tenures: CABINET_TENURES,
  offices: ["內閣"],
  collapsible: true,
  kind: "cabinet",
};

const six = (office: string, label: string): RowDef => {
  const ts = BUYUAN_TENURES.filter((t) => t.office === office);
  return {
    id: office,
    label,
    sub: `尚書等 ${ts.length} 任`,
    tenures: ts,
    offices: [office],
    collapsible: true,
    reserved: ["侍郎 / 副貳（待接入）"],
    kind: "ministry",
  };
};

const granaryTenures = BUYUAN_TENURES.filter((t) =>
  ["總督京儲", "總督倉場", "總倉場"].includes(t.office)
);

const granaryRow: RowDef = {
  id: "granary",
  label: "總督倉場",
  sub: `倉場系 ${granaryTenures.length} 任`,
  tenures: granaryTenures,
  offices: ["總督京儲", "總督倉場", "總倉場"],
  periods: GRANARY_PERIODS,
  collapsible: true,
  parent: "戶部",
  indent: true,
  kind: "granary",
};

const censorTenures = BUYUAN_TENURES.filter((t) =>
  ["御史臺", "都察院", "御史府"].includes(t.office)
);

const censorRow: RowDef = {
  id: "censor",
  label: "都察院",
  sub: `御史系列 ${censorTenures.length} 任`,
  tenures: censorTenures,
  offices: ["御史臺", "都察院", "御史府"],
  periods: CENSOR_PERIODS,
  collapsible: true,
  kind: "censor",
};

/* ============ 京卿 / 六科（2026-11-07 接入，两大块排在部院以下，默认折叠） ============ */

const JQ_OFFICES: [string, string, string][] = [
  ["通政使", "通政使", "通政使司"],
  ["大理卿", "大理卿", "大理寺"],
  ["太常卿", "太常卿", "太常寺"],
  ["光祿卿", "光祿卿", "光祿寺"],
  ["太僕卿", "太僕卿", "太僕寺"],
  ["鴻臚卿", "鴻臚卿", "鴻臚寺"],
  ["尚寶卿", "尚寶卿", "尚寶司"],
  ["順天府府尹", "順天府府尹", "順天府"],
];

const jingqingRows: RowDef[] = JQ_OFFICES.map(([office, label, org]) => {
  const ts = JINGQING_TENURES.filter((t) => t.office === office);
  return {
    id: `jq-${office}`,
    label,
    sub: `${org} ${ts.length} 任`,
    tenures: ts,
    offices: [office],
    collapsible: true,
    group: "jingqing",
    kind: "jingqing" as const,
  };
});

const KE_OFFICES = ["吏科", "戶科", "禮科", "兵科", "刑科", "工科"];

const kejiRows: RowDef[] = KE_OFFICES.map((office) => {
  const ts = KEJISHIZHONG_TENURES.filter((t) => t.office === office);
  return {
    id: `ke-${office}`,
    label: office,
    sub: `都給事中 ${ts.length} 任`,
    tenures: ts,
    offices: [office],
    collapsible: true,
    group: "kejishizhong",
    kind: "keji" as const,
  };
});

/** 渲染顺序：皇帝行之后依次排列（六部按吏戶禮兵刑工，倉場随戶部，都察院殿后；
 *  京卿/六科两大块收尾，默认折叠） */
export const ROWS: RowDef[] = [
  cabinetRow,
  six("吏部", "吏部"),
  six("戶部", "戶部"),
  granaryRow,
  six("禮部", "禮部"),
  six("兵部", "兵部"),
  six("刑部", "刑部"),
  six("工部", "工部"),
  censorRow,
  ...jingqingRows,
  ...kejiRows,
];

/** 由 office 反查所在行（抽屉用） */
export const ROW_BY_OFFICE = new Map<string, RowDef>();
for (const row of ROWS) {
  for (const off of row.offices) ROW_BY_OFFICE.set(off, row);
}

/** 某月落在哪个分期（抽屉/行名「本段」用） */
export function periodAt(
  row: RowDef,
  year: number,
  month: number | null
): PeriodSeg | null {
  if (!row.periods) return null;
  const m = month ?? 0;
  for (const p of row.periods) {
    const afterStart = year > p.startY || (year === p.startY && m >= p.startM);
    const beforeEnd = year < p.endY || (year === p.endY && m <= p.endM);
    if (afterStart && beforeEnd) return p;
  }
  // 只给年份时：取该年最后一段（年表为「年在位」体）
  const y = year;
  const sameYear = row.periods.filter((p) => p.startY <= y && p.endY >= y);
  return sameYear.length ? sameYear[sameYear.length - 1] : null;
}
