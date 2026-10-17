"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  type Tenure,
  type Reign,
  MIN_YEAR,
  MAX_YEAR,
  TENURES,
  META,
  inOffice,
  assignLanes,
  ganzhi,
  eraLabel,
  CN_MONTHS,
  REIGNS,
} from "@/lib/data";

/* ===== 画布几何（D19：统一像素坐标系，一格 = 一月）===== */
const M_PER_YEAR = 12;
const SLOT_W = 26; // 与 CSS --slot-w 一致
const LABEL_W = 132; // 与 CSS --label-w 一致
const BAR = 20;
const GAP = 4;
const PAD = 8;

const CUT_Y = 1644;
const CUT_M = 3;
/** 画布：1402.1 → 1644.3 */
const CANVAS_SLOTS = (CUT_Y - MIN_YEAR) * M_PER_YEAR + CUT_M;

const slotOf = (year: number, month: number | null, isEnd = false): number => {
  let m: number;
  if (month == null) m = isEnd ? M_PER_YEAR - 1 : 0;
  else m = Math.max(0, Math.min(M_PER_YEAR - 1, month - 1));
  return (year - MIN_YEAR) * M_PER_YEAR + m;
};

/** 断限截断（D17）：end 落在 1644 或之后 → 截到 1644.3，并告知调用方（end_clamped 语义） */
function span(t: Tenure): { s: number; e: number; clamped: boolean } {
  let eY = t.end_year;
  let eM = t.end_month;
  let clamped = false;
  if (eY > CUT_Y) { eY = CUT_Y; eM = CUT_M; clamped = true; }
  else if (eY === CUT_Y && (eM == null || eM > CUT_M)) { eM = CUT_M; clamped = t.end_month == null || t.end_month > CUT_M; }
  const s = Math.max(0, slotOf(t.start_year, t.start_month, false));
  const e = Math.min(CANVAS_SLOTS - 1, Math.max(slotOf(eY, eM, true), s));
  return { s, e, clamped };
}

const MONTH_TAG = (m: number) => CN_MONTHS[m - 1] + "月";

export default function Timeline() {
  const [slot, setSlot] = useState((1628 - MIN_YEAR) * 12); // 默认崇祯元年正月
  const [selected, setSelected] = useState<Tenure | null>(null);
  const [hoverPerson, setHoverPerson] = useState<string | null>(null);
  const [fixedH, setFixedH] = useState(150);
  const boardWrapRef = useRef<HTMLDivElement>(null);

  const { y: cursorYear, m: cursorMonth } = useMemo(
    () => ({
      y: MIN_YEAR + Math.floor(slot / M_PER_YEAR),
      m: (slot % M_PER_YEAR) + 1,
    }),
    [slot]
  );

  const current = useMemo(() => inOffice(cursorYear, cursorMonth), [cursorYear, cursorMonth]);

  /* fixed 页头/滑块占位补偿（demo 同款） */
  useEffect(() => {
    const measure = () => {
      const hh = document.querySelector(".site-header")?.getBoundingClientRect().height ?? 0;
      const sh = document.querySelector(".slider-strip")?.getBoundingClientRect().height ?? 0;
      setFixedH(hh + sh);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  /* 键盘 ←/→ 逐月步进 */
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.tagName === "INPUT") return;
      if (ev.key === "Escape") setSelected(null);
      if (ev.key === "ArrowLeft") setSlot((s) => Math.max(0, s - 1));
      if (ev.key === "ArrowRight") setSlot((s) => Math.min(CANVAS_SLOTS - 1, s + 1));
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  /* 画布点击空白跳月（demo 同款：轨道坐标反推月份格） */
  const onBoardClick = (ev: React.MouseEvent) => {
    if ((ev.target as HTMLElement).closest(".bar")) return;
    const track = (ev.target as HTMLElement).closest(".track");
    if (!track) return;
    const r = (track as HTMLElement).getBoundingClientRect();
    const s = Math.floor((ev.clientX - r.left) / SLOT_W);
    setSlot(Math.min(CANVAS_SLOTS - 1, Math.max(0, s)));
  };

  const reignLabel = (r: Reign) => `${r.temple}·${r.dept}`;

  return (
    <div onDoubleClick={() => {}}>
      {/* ============ 页头（fixed 钉视口） ============ */}
      <header className="site-header">
        <div className="masthead">
          <h1>明代职官数据库</h1>
          <span className="sub">MingOff</span>
          <span className="spacer" />
          <span className="scope">
            內閣 {META.stats.years_covered[0]}–{CUT_Y}.{CUT_M} · {META.stats.tenures} 任职
          </span>
        </div>
        <div className="control">
          <div className="era">
            <span className="regnal">{eraLabel(cursorYear)}</span>
            <span className="gz">{ganzhi(cursorYear)}</span>
            <span className="anno">{cursorYear}</span>
            <span className="anno">{MONTH_TAG(cursorMonth)}</span>
          </div>
          <div className="stepper">
            <button aria-label="上一月" disabled={slot <= 0}
              onClick={() => setSlot(Math.max(0, slot - 1))}>←</button>
            <button aria-label="下一月" disabled={slot >= CANVAS_SLOTS - 1}
              onClick={() => setSlot(Math.min(CANVAS_SLOTS - 1, slot + 1))}>→</button>
          </div>
        </div>
      </header>

      <div className="slider-strip">
        <input type="range" min={0} max={CANVAS_SLOTS - 1} step={1} value={slot}
          aria-label="年月"
          onChange={(e) => setSlot(+e.target.value)} />
      </div>

      {/* ============ 画布 ============ */}
      <main style={{ paddingTop: fixedH }}>
        <div className="legend">
          <span className="item"><i className="swatch s-shishou" />实授</span>
          <span className="item"><i className="swatch s-fuzzy" />起月未载</span>
          <span className="item"><i className="swatch s-uncertain" />同年并格待校</span>
          <span className="item"><i className="cursor-demo" />当前年月</span>
        </div>

        <div className="board-wrap" ref={boardWrapRef}>
          <div className="board" style={{ width: LABEL_W + CANVAS_SLOTS * SLOT_W }}
            onClick={onBoardClick}>
            {/* 顶部刻度尺 */}
            <div className="axis">
              <div className="axis-label">職官 / 年月</div>
              <div className="axis-track">
                {Array.from({ length: CUT_Y - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((yr) => {
                  const yearSlots = yr === CUT_Y ? CUT_M : M_PER_YEAR;
                  const mid = slotOf(yr, 1) + yearSlots / 2;
                  return (
                    <div key={yr}>
                      <span className="yr" style={{ left: mid * SLOT_W }}
                        title={`${eraLabel(yr)} ${ganzhi(yr)}`}>
                        {yr}
                        <span className="gz">{ganzhi(yr)}</span>
                      </span>
                      <span className="year-line" style={{ left: slotOf(yr, 1) * SLOT_W }} />
                    </div>
                  );
                })}
                {Array.from({ length: CANVAS_SLOTS }, (_, s) =>
                  s % M_PER_YEAR === 0 ? null : (
                    <span key={"mt" + s} className="month-tick" style={{ left: s * SLOT_W }} />
                  )
                )}
              </div>
            </div>

            {/* 皇帝行们（朱底，按世系分段） */}
            {REIGNS.map((r, i) => {
              const s = Math.max(0, slotOf(r.startY, r.startM));
              const e = Math.min(CANVAS_SLOTS - 1, slotOf(r.endY, r.endM, true));
              if (e < 0 || s > CANVAS_SLOTS - 1) return null;
              return (
                <div className="row reign" key={i}>
                  <div className="row-label">
                    <span className="name">{r.temple}</span>
                    <span className="dept">{r.dept}</span>
                  </div>
                  <div className="track" style={{ height: 38 }}>
                    <span className="reign-bar" style={{
                      left: s * SLOT_W,
                      width: (e - s + 1) * SLOT_W,
                    }}>{r.barLabel}</span>
                  </div>
                </div>
              );
            })}

            {/* 内阁行：泳道分配 */}
            {(() => {
              const lanes = assignLanes(TENURES);
              return lanes.map((lane, li) => (
                <div className="row" key={"lane" + li}>
                  <div className="row-label">
                    {li === 0 && (
                      <>
                        <span className="name">內閣大臣</span>
                        <span className="dept">內閣 · {lane.length + (lanes.length - 1) * 0}人任</span>
                      </>
                    )}
                  </div>
                  <div className="track" style={{ height: BAR + PAD * 2 }}>
                    {lane.map((t, ti) => {
                      const { s, e, clamped } = span(t);
                      const active = slot >= s && slot <= e;
                      const hot = hoverPerson === t.person ||
                        (selected && selected.person === t.person && selected.office === t.office &&
                         selected.start_year === t.start_year);
                      return (
                        <span key={ti}
                          className={[
                            "bar", "t-shishou",
                            t.start_month == null && "fuzzy",
                            t.month_conflict && "conflict",
                            clamped && "clamped",
                            !active && "is-idle",
                            hot && "peer",
                          ].filter(Boolean).join(" ")}
                          style={{ left: s * SLOT_W, width: (e - s + 1) * SLOT_W, top: PAD, height: BAR }}
                          tabIndex={0}
                          role="button"
                          aria-label={`${t.person}，內閣，${t.start_year}至${t.end_year}`}
                          onMouseEnter={() => setHoverPerson(t.person)}
                          onMouseLeave={() => setHoverPerson(null)}
                          onClick={(ev) => { ev.stopPropagation(); setSelected(t); }}
                          onKeyDown={(ev) => {
                            if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setSelected(t); }
                          }}
                        >{t.person}</span>
                      );
                    })}
                  </div>
                </div>
              ));
            })()}

            {/* 贯穿年/月列线（z-index 压在标签之下，demo 坑 5） */}
            <span className="col-lines" style={{ left: LABEL_W, width: CANVAS_SLOTS * SLOT_W }} aria-hidden>
              {Array.from({ length: CUT_Y - MIN_YEAR + 1 }, (_, i) => MIN_YEAR + i).map((yr) => (
                <span key={yr} className="year-col" style={{ left: slotOf(yr, 1) * SLOT_W }} />
              ))}
              {Array.from({ length: CANVAS_SLOTS }, (_, s) =>
                s % M_PER_YEAR === 0 ? null : (
                  <span key={"mc" + s} className="month-col" style={{ left: s * SLOT_W }} />
                )
              )}
            </span>

            {/* 断限线：1644.3 月末 = 数据区右缘（含标签列的 board 坐标） */}
            <span className="cutoff" style={{ left: LABEL_W + CANVAS_SLOTS * SLOT_W }} />
            <span className="cutoff-label" style={{ left: LABEL_W + CANVAS_SLOTS * SLOT_W }}>
              1644.3
            </span>

            {/* 游标：指在当前月格右缘（"在该月内"） */}
            <span className="cursor" style={{ left: LABEL_W + (slot + 1) * SLOT_W }} aria-hidden />
          </div>
        </div>
      </main>

      {/* ============ 页脚 ============ */}
      <footer>
        <div className="rule" />
        <p><span className="k">数据范围</span>　明代內閣（{META.stats.years_covered[0]}–{CUT_Y}.{CUT_M}），{META.stats.tenures} 任职段、{META.stats.persons} 人。<b>缺载处留空，不作填补。</b></p>
        <p><span className="k">断限</span>　止于崇祯十七年三月（1644.3）。</p>
        <p><span className="k">时间轴</span>　每月一格、各格等宽（无限画布，随内容横向滚动）；月份未载者占满整年，详情中注明。</p>
        <p><span className="k">史料依据</span>　張德信《明代職官年表》冊1·內閣大臣年表；人物对齐 CBDB（{META.stats.cbdb_aligned} 段）。</p>
        <p><span className="k">数据说明</span>　年表为「年在位」体：某年列名即该年在任；注文记任免动作。年份空档按源保留，不填补。</p>
        <p style={{ marginTop: 12 }}>开源非商业项目 · 代码 Apache-2.0 · 本项目整理数据 CC BY-NC-SA 4.0</p>
      </footer>

      {/* ============ 详情抽屉 ============ */}
      <aside className={"drawer" + (selected ? " open" : "")} aria-hidden={!selected} role="dialog" aria-label="任职详情">
        {selected && (() => {
          const { clamped } = span(selected);
          const confPct = Math.round(selected.confidence * 100);
          return (
            <>
              <div className="drawer-head">
                <div>
                  <h2>{selected.person}</h2>
                  <div className="drawer-office">內閣{selected.cbdb_id != null && ` · CBDB #${selected.cbdb_id}`}</div>
                </div>
                <button className="close" aria-label="关闭" onClick={() => setSelected(null)}>关闭</button>
              </div>
              <div className="drawer-body">
                <dl className="field"><dt>任期</dt><dd>
                  {selected.start_year}年{selected.start_month ? MONTH_TAG(selected.start_month) : ""}
                  {" – "}
                  {selected.end_year}年{selected.end_month ? MONTH_TAG(selected.end_month) : ""}
                </dd></dl>
                <dl className="field"><dt>精度</dt><dd>
                  {selected.start_month || (selected.end_month && !clamped)
                    ? "已精确到月（据年表注文）"
                    : clamped
                      ? <>仅到年；终年按<b>断限</b>截到 1644 年 3 月（非史料所载月份）</>
                      : "仅到年（史料未载月份）"}
                  {selected.month_conflict && <span className="vermilion">（同年入离并格，月份待校）</span>}
                </dd></dl>
                <dl className="field"><dt>在任年</dt><dd className="mono">{selected.years.join("、")}</dd></dl>
                <dl className="field"><dt>任免</dt><dd>
                  入：{selected.enter_verbs.join("、") || "—"}　
                  离：{selected.leave_verbs.join("、") || "—"}
                </dd></dl>
                <dl className="field"><dt>置信度</dt><dd><div className="conf">
                  <div className="conf-bar">
                    <i className={selected.confidence < 0.6 ? "low" : ""}
                      style={{ width: `${confPct}%` }} />
                  </div>
                  <span className="conf-num">{selected.confidence.toFixed(1)}</span>
                </div></dd></dl>
                <dl className="field"><dt>出处</dt><dd>{META.source}</dd></dl>
                {selected.note && <dl className="field"><dt>年表原文</dt><dd className="serif">{selected.note}</dd></dl>}
                <div className="caveat"><b>关于本条的确定性</b><br />
                  {selected.confidence < 0.8
                    ? "本条置信度低于 0.8，史料对任期记载可能有歧，引用前请核对原书。"
                    : "任期为年表口径；月份未载处以整年表示，未作推断。"}
                </div>
              </div>
            </>
          );
        })()}
      </aside>
    </div>
  );
}
