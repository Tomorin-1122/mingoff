"use client";

import { useMemo, useState } from "react";
import {
  type Tenure,
  MIN_YEAR,
  MAX_YEAR,
  SORTED_TENURES,
  inOffice,
  ganzhi,
  eraYear,
  META,
} from "@/lib/data";

const SLOT_W = 14; // 月格宽 px（D16：每年 12 格等宽）
const LABEL_W = 220;
const ROW_H = 30;

/** 全期月格总数：1402–1644（月粒度；段按月画） */
const TOTAL_MONTHS = (MAX_YEAR - MIN_YEAR + 1) * 12;

/** 年 → 该年在月格轴上的起始格号 */
function yearOffset(year: number): number {
  return (year - MIN_YEAR) * 12;
}

function tenureLeft(t: Tenure): number {
  return yearOffset(t.start_year) + (t.start_month ? t.start_month - 1 : 0);
}
function tenureWidth(t: Tenure): number {
  const endMonths = yearOffset(t.end_year) + (t.end_month ?? 12);
  return Math.max(endMonths - tenureLeft(t), SLOT_W / 2);
}

function cn(...xs: (string | false | undefined)[]) {
  return xs.filter(Boolean).join(" ");
}

/** 年轴刻度：每 10 年 + 首末年 */
function yearTicks(): number[] {
  const ticks: number[] = [];
  for (let y = MIN_YEAR; y <= MAX_YEAR; y++) {
    if (y === MIN_YEAR || y === MAX_YEAR || y % 10 === 2) ticks.push(y);
  }
  return ticks;
}

export default function Timeline() {
  const [cursorYear, setCursorYear] = useState(1628);
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<Tenure | null>(null);

  const current = useMemo(() => inOffice(cursorYear), [cursorYear]);

  return (
    <div className="tl-root">
      {/* ── 视口固定区：标题 + 年份滑块 + 当前在任名单 ── */}
      <header className="tl-head">
        <div className="tl-title">
          <h1>
            MingOff <span className="era">內閣年表</span>
          </h1>
          <p className="tl-sub">
            {MIN_YEAR}–{MAX_YEAR} · {META.stats.tenures} 段 ·{" "}
            {META.stats.persons} 人 · 拖动游标看某年谁在任
          </p>
        </div>
        <div className="tl-cursor">
          <label className="mono">
            <span className="era">{eraYear(cursorYear)}</span>{" "}
            <b className="mono">{cursorYear}</b>
          </label>
          <input
            type="range"
            min={MIN_YEAR}
            max={MAX_YEAR}
            value={cursorYear}
            onChange={(e) => setCursorYear(+e.target.value)}
          />
          <div className="tl-office mono">
            在任 <b>{current.length}</b> 人：{" "}
            {current.map((t) => t.person).join("・") || "—"}
          </div>
        </div>
      </header>

      {/* ── 无限画布：月格等宽横向铺开（D19）── */}
      <div className="tl-scroll">
        <div
          className="tl-canvas"
          style={{ width: LABEL_W + TOTAL_MONTHS * SLOT_W }}
        >
          {/* 年轴 */}
          <div className="tl-yearaxis" style={{ paddingLeft: LABEL_W }}>
            {yearTicks().map((y) => (
              <span
                key={y}
                className="mono tl-yearlabel"
                style={{ left: yearOffset(y) * SLOT_W }}
              >
                <b>{y}</b>
                <i>{ganzhi(y)}</i>
              </span>
            ))}
            {/* 年份分隔线 */}
            {yearTicks().map((y) => (
              <span
                key={"l" + y}
                className="tl-vline"
                style={{ left: yearOffset(y) * SLOT_W }}
              />
            ))}
          </div>

          {/* 任职行（绝对定位行不撑高父容器，须显式高度） */}
          <div
            className="tl-rows"
            style={{ height: SORTED_TENURES.length * ROW_H }}
          >
            {SORTED_TENURES.map((t, i) => (
              <div className="tl-row" key={i} style={{ top: i * ROW_H }}>
                <span
                  className={cn(
                    "tl-name",
                    (hover === t.person || selected?.person === t.person) &&
                      "tl-name-hot"
                  )}
                >
                  {t.person}
                  {t.cbdb_id == null && <i title="未对齐 CBDB">?</i>}
                </span>
                <span
                  className={cn(
                    "tl-bar",
                    t.start_month == null && "tl-bar-fuzzy",
                    t.month_conflict && "tl-bar-conflict",
                    (hover === t.person || selected?.person === t.person) &&
                      "tl-bar-hot",
                    selected === t && "tl-bar-sel"
                  )}
                  style={{
                    left: LABEL_W + tenureLeft(t) * SLOT_W,
                    width: tenureWidth(t) * SLOT_W,
                  }}
                  onMouseEnter={() => setHover(t.person)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => setSelected(t)}
                />
              </div>
            ))}
          </div>

          {/* 年份游标（签名元素） */}
          <span
            className="tl-cursorline"
            style={{ left: LABEL_W + yearOffset(cursorYear) * SLOT_W }}
          />
        </div>
      </div>

      {/* ── 详情抽屉：年表原文 + 置信度（可溯源是本站核心） ── */}
      {selected && (
        <aside className="tl-drawer">
          <button className="tl-close" onClick={() => setSelected(null)}>
            ×
          </button>
          <h2>{selected.person}</h2>
          <p className="mono tl-tenure-range">
            {selected.start_year}
            {selected.start_month && `·${selected.start_month}`}–{selected.end_year}
            {selected.end_month && `·${selected.end_month}"}–`}
            {selected.end_month && `·${selected.end_month}`}
          </p>
          <p className="tl-note">{selected.note || "（年表未载注文）"}</p>
          <dl className="tl-meta">
            <dt>来源</dt>
            <dd>張德信《明代職官年表》冊1·內閣大臣年表</dd>
            <dt>任免动词</dt>
            <dd>
              {selected.enter_verbs.join("、") || "—"} →{" "}
              {selected.leave_verbs.join("、") || "—"}
            </dd>
            <dt>置信度</dt>
            <dd className="mono">
              {selected.confidence}
              {selected.month_conflict && (
                <span className="vermilion">（同年入离并格，月份待校）</span>
              )}
            </dd>
            {selected.cbdb_id != null && (
              <>
                <dt>CBDB</dt>
                <dd className="mono">#{selected.cbdb_id}</dd>
              </>
            )}
          </dl>
          <p className="tl-discipline">
            月份未载即空白显示，不作填补；置信度 ≤ 0.8，不设 1.0。
          </p>
        </aside>
      )}
    </div>
  );
}
