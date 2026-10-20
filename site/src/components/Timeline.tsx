"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BUYUAN_META,
  BUYUAN_PROFILES,
  CANVAS_FROM,
  CANVAS_SLOTS,
  CN_MONTHS,
  CUT_M,
  CUT_Y,
  DATA_FROM,
  ERA_JUMPS,
  META,
  M_PER_YEAR,
  PROFILES,
  PROFILE_META,
  REIGNS,
  SHILU,
  ageAt,
  assignLanes,
  eraLabel,
  fmtYM,
  fmtYearRange,
  ganzhi,
  slotOf,
  span,
  type PersonProfile,
  type Reign,
  type Tenure,
} from "@/lib/data";
import {
  ROWS,
  ROW_BY_OFFICE,
  periodAt,
  type PeriodSeg,
  type PeriodTone,
  type RowDef,
} from "@/lib/rows";

/* ============================================================
 * 时间轴（正式站）
 * 视觉与交互**逐项移植自项目负责人验收的 web/demo.template.html**：
 *   fixed 页头 + 月格等宽无限画布 + 单行皇帝（含周岁） + 泳道 + 游标
 *   + 同人联动 + 当前月淡化 + 详情抽屉（含《明實錄》命中）。
 * 与 demo 的差异只有两处（由全朝 242 年数据决定）：
 *   ① 皇帝行由单帝改为 16 帝单行分段；
 *   ② 增加「年号跳转」条 —— 76,000px 的画布必须能一键跳代。
 * 几何统一用像素坐标（格号 × 月格宽），不混百分比（demo 坑 4）。
 * ============================================================ */

const BAR_H = 20;
const BAR_GAP = 4;
const TRACK_PAD = 8;
const REIGN_TRACK_H = 38;
/** 默认档位；实际值从 CSS 变量 --slot-w / --label-w 读取（响应式会改） */
const DEF_SLOT_W = 26;
const DEF_LABEL_W = 132;

/** 人读的出处说明（抽屉展示；完整溯源字段见 cabinet/buyuan.json 的 meta.source、页脚） */

interface Dims {
  slotW: number;
  labelW: number;
}

/* ================= 静态图层（memo，避免拖滑块时重排 3000+ 节点）================= */

/** 长条内重复人名/年号：条可能横跨数十年（>10,000px），只标一次必然滚出视口 */
function barLabels(text: string, widthPx: number, step: number, offset: number) {
  const n = Math.max(1, Math.floor(widthPx / step));
  if (n === 1) return <span className="bar-label center">{text}</span>;
  return Array.from({ length: n }, (_, i) => (
    <span key={i} className="bar-label" style={{ left: i * step + offset }}>
      {text}
    </span>
  ));
}

const Axis = memo(function Axis({ slotW }: { slotW: number }) {
  const years = useMemo(
    () => Array.from({ length: CUT_Y - CANVAS_FROM + 1 }, (_, i) => CANVAS_FROM + i),
    []
  );
  return (
    <div className="axis">
      <div className="axis-label">職官 / 年月</div>
      <div className="axis-track">
        {years.map((y) => {
          const slotsThisYear = y === CUT_Y ? CUT_M : M_PER_YEAR;
          const mid = slotOf(y, 1) + slotsThisYear / 2;
          return (
            <span key={y}>
              <span
                className="yr"
                style={{ left: mid * slotW }}
                title={`${eraLabel(y)} ${ganzhi(y)}`}
              >
                {y}
                <span className="gz">{ganzhi(y)}</span>
              </span>
              <span className="year-line" style={{ left: slotOf(y, 1) * slotW }} />
            </span>
          );
        })}
        {Array.from({ length: CANVAS_SLOTS }, (_, s) =>
          s % M_PER_YEAR === 0 ? null : (
            <span key={"mt" + s} className="month-tick" style={{ left: s * slotW }} />
          )
        )}
      </div>
    </div>
  );
});

const ReignRow = memo(function ReignRow({ slotW }: { slotW: number }) {
  const segments = REIGNS.map((r: Reign) => {
    const s = Math.max(0, slotOf(r.startY, r.startM));
    const e = Math.min(CANVAS_SLOTS - 1, slotOf(r.endY, r.endM, true));
    if (e < 0 || s > CANVAS_SLOTS - 1) return null;
    const years: number[] = [];
    for (let y = Math.max(r.startY, CANVAS_FROM); y <= Math.min(r.endY, CUT_Y); y++) {
      years.push(y);
    }
    return { r, s, e, years };
  });

  return (
    <div className="row reign">
      <div className="row-label">
        <span className="name">皇帝</span>
        <span className="dept">在位 · 16 帝</span>
      </div>
      <div className="track" style={{ height: REIGN_TRACK_H }}>
        {segments.map((seg) =>
          seg ? (
            <span
              key={seg.r.temple + seg.r.era}
              className="reign-bar"
              style={{ left: seg.s * slotW, width: (seg.e - seg.s + 1) * slotW }}
              title={`${seg.r.temple}·${seg.r.era}（${seg.r.startY}–${seg.r.endY}）`}
            >
              {barLabels(seg.r.barLabel, (seg.e - seg.s + 1) * slotW, 1600, 10)}
            </span>
          ) : null
        )}
        {segments.map((seg) =>
          seg
            ? seg.years.map((y) => {
                const age = ageAt(y, 2, seg.r);
                const left = Math.max(seg.s, slotOf(y, 1)) * slotW + 2;
                return (
                  <span
                    key={`${seg.r.temple}${seg.r.era}${y}`}
                    className="reign-age"
                    style={{ left, width: M_PER_YEAR * slotW - 4, textAlign: "left" }}
                    title={`${seg.r.temple}·${seg.r.era}${y}，帝周岁约 ${age}`}
                  >
                    {age}岁
                  </span>
                );
              })
            : null
        )}
      </div>
    </div>
  );
});

const ColumnLines = memo(function ColumnLines({ slotW, labelW }: Dims) {
  const years = useMemo(
    () => Array.from({ length: CUT_Y - CANVAS_FROM + 1 }, (_, i) => CANVAS_FROM + i),
    []
  );
  return (
    <span
      className="col-lines"
      style={{ left: labelW, width: CANVAS_SLOTS * slotW }}
      aria-hidden
    >
      {years.map((y) => (
        <span key={y} className="year-col" style={{ left: slotOf(y, 1) * slotW }} />
      ))}
      {Array.from({ length: CANVAS_SLOTS }, (_, s) =>
        s % M_PER_YEAR === 0 ? null : (
          <span key={"mc" + s} className="month-col" style={{ left: s * slotW }} />
        )
      )}
    </span>
  );
});

/* ================= 分期名带（D46）：行名固定，带上的表头随年代变 ================= */

const RIBBON_H = 18;

function periodLabels(text: string, widthPx: number) {
  const step = 1700;
  const n = Math.max(1, Math.floor(widthPx / step));
  return Array.from({ length: n }, (_, i) => (
    <span key={i} className="period-label" style={{ left: i * step + 8 }}>
      {text}
    </span>
  ));
}

const PeriodRibbon = memo(function PeriodRibbon({
  periods,
  slotW,
}: {
  periods: PeriodSeg[];
  slotW: number;
}) {
  return (
    <div className="period-ribbon" aria-hidden>
      {periods.map((p, i) => {
        const s = Math.max(0, slotOf(p.startY, p.startM));
        const e = Math.min(CANVAS_SLOTS - 1, slotOf(p.endY, p.endM, true));
        if (e < s) return null;
        const w = (e - s + 1) * slotW;
        return (
          <span
            key={i}
            className={`period-seg tone-${p.tone}`}
            style={{ left: s * slotW, width: w }}
            title={p.note ? `${p.label}｜${p.note}` : p.label}
          >
            {periodLabels(p.label, w)}
          </span>
        );
      })}
    </div>
  );
});

/* ================= 职官行（D46：内阁 / 六部 / 都察院 / 倉場） ================= */

const STATUS_TEXT: Record<string, string> = {
  "row-order": "行序兜底（该年对页无标签，按行序推断，未经页核）",
  mixed: "段内部分年份为行序推断，其余有人名锚/页核",
  "name-anchor": "人名锚定（该年对页无标签，但人名可锚定衙署）",
  "page-verified": "原书页核（D-04/D42 已回原书对页）",
};

interface OfficeRowProps {
  row: RowDef;
  open: boolean;
  onToggle: () => void;
  slotW: number;
  slot: number;
  hoverPerson: string | null;
  onHover: (person: string | null) => void;
  onSelect: (t: Tenure) => void;
}

const OfficeRow = memo(function OfficeRow({
  row,
  open,
  onToggle,
  slotW,
  slot,
  hoverPerson,
  onHover,
  onSelect,
}: OfficeRowProps) {
  const lanes = useMemo(() => assignLanes(row.tenures), [row.tenures]);
  const ribbon = row.periods?.length ? RIBBON_H : 0;
  const reservedH = row.reserved?.length ? row.reserved.length * (BAR_H + BAR_GAP) : 0;
  const barsH = Math.max(0, lanes.length * (BAR_H + BAR_GAP) - BAR_GAP);
  const trackH = ribbon + TRACK_PAD + barsH + reservedH + TRACK_PAD;

  const cursorYear = CANVAS_FROM + Math.floor(slot / M_PER_YEAR);
  const cursorMonth = (slot % M_PER_YEAR) + 1;
  const currentPeriod = row.periods
    ? periodAt(row, cursorYear, cursorMonth)
    : null;

  return (
    <div className={`row ${row.indent ? "row-sub" : ""}`}>
      <div className="row-label">
        {row.collapsible && (
          <button
            type="button"
            className="row-toggle"
            aria-expanded={open}
            aria-label={`${open ? "折叠" : "展开"}${row.label}`}
            onClick={onToggle}
          >
            {open ? "▾" : "▸"}
          </button>
        )}
        <span className="name">{row.label}</span>
        <span className="dept" title={row.sub}>
          {open && currentPeriod ? `本段：${currentPeriod.label}` : row.sub}
        </span>
      </div>
      {open && (
        <div className="track" style={{ height: trackH }}>
          {/* 内阁：洪武—建文三年（1368–1401）未设，画布留空并明确标注 */}
          {row.kind === "cabinet" && (
            <>
              <span
                className="void-span"
                style={{ left: 0, width: slotOf(DATA_FROM, 1) * slotW }}
                aria-hidden
              />
              <span className="void-note" style={{ left: 10, top: TRACK_PAD }}>
                洪武元年—建文三年（1368–1401）內閣未設 · 留空
              </span>
            </>
          )}

          {row.periods && <PeriodRibbon periods={row.periods} slotW={slotW} />}

          {lanes.map((lane, li) =>
            lane.map((t, ti) => {
              const { s, e } = span(t);
              if (e < 0 || s > CANVAS_SLOTS - 1 || e < s) return null;
              const idle = slot < s || slot > e;
              const label = t.person_label || t.person;
              const hoverKey = t.person_id || t.person;
              const period = row.periods
                ? periodAt(row, t.start_year, t.start_month)
                : null;
              const cls = [
                "bar",
                row.kind === "cabinet" ? "t-shishou" : "bar-bu",
                `office-${t.office}`,
                t.start_month == null && "fuzzy",
                t.month_conflict && "conflict",
                t.office_status === "row-order" && "st-row-order",
                t.office_status === "mixed" && "st-mixed",
                t.end_clamped && "clamped",
                idle && "is-idle",
                hoverPerson === hoverKey && "peer",
              ]
                .filter(Boolean)
                .join(" ");
              const titleParts = [
                label,
                `${t.office}${period ? `（${period.label}）` : ""}`,
                `${t.start_year}${t.start_month ? "." + t.start_month : ""}–${t.end_year}${t.end_month ? "." + t.end_month : ""}`,
                `置信度 ${t.confidence}`,
                t.office_status ? `归属：${STATUS_TEXT[t.office_status] ?? t.office_status}` : null,
                t.start_book_page ? `原书 p${t.start_book_page}` : null,
              ].filter(Boolean);
              return (
                <span
                  key={`${hoverKey}-${t.office}-${t.start_year}-${t.start_month}-${li}-${ti}`}
                  className={cls}
                  style={{
                    left: s * slotW,
                    width: (e - s + 1) * slotW,
                    top: ribbon + TRACK_PAD + li * (BAR_H + BAR_GAP),
                    height: BAR_H,
                  }}
                  tabIndex={0}
                  role="button"
                  title={titleParts.join("｜")}
                  aria-label={`${label}，${t.office}，${t.start_year} 至 ${t.end_year}`}
                  onMouseEnter={() => onHover(hoverKey)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(hoverKey)}
                  onBlur={() => onHover(null)}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    onSelect(t);
                  }}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      onSelect(t);
                    }
                  }}
                >
                  {barLabels(label, (e - s + 1) * slotW, 1100, 8)}
                </span>
              );
            })
          )}

          {/* 六部预留：侍郎等副貳泳道（后续表种接入，先占位） */}
          {row.reserved?.map((txt, ri) => (
            <span
              key={txt}
              className="reserved-lane"
              style={{
                top: ribbon + TRACK_PAD + barsH + ri * (BAR_H + BAR_GAP),
                height: BAR_H,
              }}
            >
              <span className="reserved-label">{txt}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
});

/* ================= 详情抽屉 ================= */

/* ================= 人物小传（CBDB） ================= */

function ProfileBlock({ person, profile }: { person: string; profile: PersonProfile }) {
  const p = profile;
  const hasBio = !!(
    p.birth || p.death || p.native_place || p.alt_names.length || p.entry.length
  );
  const cbdbUrl = p.cbdb_id
    ? PROFILE_META.cbdb_person_url.replace("{id}", String(p.cbdb_id))
    : null;
  const altText = p.alt_names.map((a) => `${a.type}：${a.name}`).join("；");

  /** 中研院检索是 POST：用隐藏表单新窗口提交，等于“一键检索” */
  const openSinicaSearch = () => {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = PROFILE_META.sinica_output_url;
    form.target = "_blank";
    form.style.display = "none";
    const i1 = document.createElement("input");
    i1.type = "hidden";
    i1.name = "input[]";
    i1.value = person;
    const i2 = document.createElement("input");
    i2.type = "hidden";
    i2.name = "check[]";
    i2.value = "3";
    form.append(i1, i2);
    document.body.appendChild(form);
    form.submit();
    form.remove();
  };
  return (
    <section className="person-card">
      <h3>
        人物小傳 <span className="tag">CBDB</span>
      </h3>
      {hasBio ? (
        <>
          <dl className="field">
            <dt>生卒</dt>
            <dd>
              {fmtYearRange(p.birth, p.death)}
              {p.death_age ? <span className="hint">（享年 {p.death_age}）</span> : null}
            </dd>
          </dl>
          {p.native_place && (
            <dl className="field">
              <dt>籍貫</dt>
              <dd>{p.native_place}</dd>
            </dl>
          )}
          {altText && (
            <dl className="field">
              <dt>字號</dt>
              <dd>{altText}</dd>
            </dl>
          )}
          {p.entry.length > 0 && (
            <dl className="field">
              <dt>入仕</dt>
              <dd>
                {p.entry
                  .slice(0, 3)
                  .map((e) => `${e.year ? `${e.year}年` : "—"} ${e.desc}`)
                  .join("；")}
              </dd>
            </dl>
          )}
        </>
      ) : (
        <p className="small">
          {p.cbdb_id
            ? "CBDB 有該人記錄，但生卒/籍貫等欄位為空。"
            : "CBDB 未對齊（無可靠同名候選），僅提供中研院檢索入口。"}
        </p>
      )}

      <div className="ext-links">
        {cbdbUrl ? (
          <a href={cbdbUrl} target="_blank" rel="noopener noreferrer">
            CBDB #{p.cbdb_id}
            {p.cbdb_name && p.cbdb_name !== person ? `（${p.cbdb_name}）` : ""} ↗
          </a>
        ) : (
          <span className="small">CBDB 未對齊（無可靠同名候選）</span>
        )}
        <a
          href={PROFILE_META.sinica_url}
          target="_blank"
          rel="noopener noreferrer"
          title={`中研院站內檢索：${person}`}
        >
          中研院「明代職官資料庫」 ↗
        </a>
        <button type="button" className="ext-btn" onClick={openSinicaSearch}>
          中研院一鍵檢索（明實錄）↗
        </button>
      </div>
      <p className="hint">
        中研院檢索詞：<b>{person}</b>（站內輸入後檢索；命中含《明實錄》原文）
      </p>

      {p.office_total > 0 && (
        <details className="offices">
          <summary>歷任官職（{p.office_total}）</summary>
          <ul>
            {p.offices.map((o, i) => (
              <li key={i}>
                <span className="mono">
                  {o.from ?? "?"}
                  {o.to != null || o.from != null ? `–${o.to ?? "?"}` : ""}
                </span>{" "}
                {o.office}
              </li>
            ))}
          </ul>
          {p.office_total > p.offices.length && (
            <p className="hint">…另有 {p.office_total - p.offices.length} 條未列（CBDB 原始記錄）</p>
          )}
        </details>
      )}
    </section>
  );
}

/** 部院人物的小传占位：profiles 目前只覆盖内阁 167 人，部院 789 实体待扩展 */
function ProfileFallback({ tenure }: { tenure: Tenure }) {
  const url = tenure.cbdb_id
    ? PROFILE_META.cbdb_person_url.replace("{id}", String(tenure.cbdb_id))
    : null;
  return (
    <section className="person-card">
      <h3>
        人物小傳 <span className="tag">CBDB</span>
      </h3>
      <p className="small">
        {url
          ? "CBDB 有該人記錄（見下方直達鏈接）；部院人物小傳欄位尚未接入本站，待人物庫擴展。"
          : "CBDB 未對齊（無可靠同名候選），僅提供中研院檢索入口；可查《明人傳記資料索引》出處層。"}
      </p>
      <div className="ext-links">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer">
            CBDB #{tenure.cbdb_id}
            {tenure.cbdb_name && tenure.cbdb_name !== tenure.person
              ? `（${tenure.cbdb_name}）`
              : ""}{" "}
            ↗
          </a>
        ) : (
          <span className="small">CBDB 未對齊</span>
        )}
        <a href={PROFILE_META.sinica_url} target="_blank" rel="noopener noreferrer">
          中研院「明代職官資料庫」 ↗
        </a>
      </div>
      <p className="hint">
        中研院檢索詞：<b>{tenure.person}</b>
      </p>
    </section>
  );
}

function Drawer({
  tenure,
  onClose,
}: {
  tenure: Tenure | null;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (tenure) closeRef.current?.focus();
  }, [tenure]);

  const body = useMemo(() => {
    if (!tenure) return null;
    const t = tenure;
    const { clamped } = span(t);
    const realMonth = !!t.start_month || (!!t.end_month && !clamped);
    const confPct = Math.round(t.confidence * 100);
    const label = t.person_label || t.person;
    const row = ROW_BY_OFFICE.get(t.office);
    const period = row ? periodAt(row, t.start_year, t.start_month) : null;
    const blk = SHILU[t.person] ?? (t.person_label ? SHILU[t.person_label] : undefined);
    // 部院按 person_id 取（顧佐#1/#2 各自独立）；内阁按姓名取
    const profile = t.person_id
      ? BUYUAN_PROFILES[t.person_id]
      : PROFILES[t.person];
    const isCabinet = row?.kind === "cabinet";
    const sourceText = isCabinet
      ? "张德信《明代职官年表》册1·內閣大臣年表（MinerU OCR 提取）；" +
        "《明實錄》命中据中研院「明代职官资料库」检索。"
      : "张德信《明代职官年表》册1·部院大臣年表（京師）（MinerU OCR 表格重解析）；" +
        "人物对齐 CBDB；《明實錄》命中据中研院「明代职官资料库」检索。";

    return (
      <>
        <div className="drawer-head">
          <div>
            <h2>{label}</h2>
            <div className="drawer-office">
              {row && row.label !== t.office ? `${row.label} · ` : ""}
              {t.office}
              {period && ` · 本段表头「${period.label}」`}
              {t.cbdb_id != null && ` · CBDB #${t.cbdb_id}`}
              {t.cbdb_name && t.cbdb_name !== t.person && `（${t.cbdb_name}）`}
            </div>
          </div>
          <button className="close" ref={closeRef} aria-label="关闭" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="drawer-body">
          <dl className="field">
            <dt>任期</dt>
            <dd>
              {fmtYM(t.start_year, t.start_month)} – {fmtYM(t.end_year, t.end_month)}
            </dd>
          </dl>

          <dl className="field">
            <dt>精度</dt>
            <dd>
              {realMonth
                ? "已精确到月（据年表注文）"
                : clamped
                  ? <>仅到年；终年按<b>断限</b>截到 1644 年 3 月（非史料所载月份）</>
                  : "仅到年（史料未载月份）"}
              {t.month_conflict && (
                <span className="vermilion">（同年入离并格，月份待校）</span>
              )}
            </dd>
          </dl>

          <dl className="field">
            <dt>性质</dt>
            <dd>
              <span className="tag t-shishou">{t.tenure_type}</span>{" "}
              <span className="hint">
                {isCabinet
                  ? "内阁年表不区分署理 / 加衔，不作推断"
                  : "部院年表区分实授 / 署理，以注文为准"}
              </span>
            </dd>
          </dl>

          {t.office_status && (
            <dl className="field">
              <dt>归属依据</dt>
              <dd>
                {STATUS_TEXT[t.office_status] ?? t.office_status}
                {t.office_status === "row-order" || t.office_status === "mixed" ? (
                  <span className="vermilion">（灰显；引用前请回原书页核对）</span>
                ) : null}
              </dd>
            </dl>
          )}

          {t.start_book_page && (
            <dl className="field">
              <dt>原书页</dt>
              <dd className="mono">
                p{t.start_book_page}
                {t.end_book_page && t.end_book_page !== t.start_book_page
                  ? `–${t.end_book_page}`
                  : ""}
                {period ? <span className="hint">（本段表头：{period.label}）</span> : null}
              </dd>
            </dl>
          )}

          {t.office_raw && t.office_raw !== t.office && (
            <dl className="field">
              <dt>原书表头</dt>
              <dd>
                {t.office_raw}
                <span className="hint">（本库归「{t.office}」，异名不合并实体）</span>
              </dd>
            </dl>
          )}

          <dl className="field">
            <dt>离任</dt>
            <dd>{t.leave}</dd>
          </dl>

          <dl className="field">
            <dt>在任年</dt>
            <dd className="mono">{t.years.join("、")}</dd>
          </dl>

          {t.gap_years && t.gap_years.length > 0 && (
            <dl className="field">
              <dt>缺载年</dt>
              <dd>
                <span className="mono">{t.gap_years.join("、")}</span>
                <span className="hint">
                  （年表该年无此人；系 1–2 年缺行合并，非连续在任，画布上以缺口表示）
                </span>
              </dd>
            </dl>
          )}

          {t.same_name_risk && (
            <p className="hint">
              同名风险：该姓名下有多个实体，本站按「{label}」区分；引用时请核对年代与衙署。
            </p>
          )}

          {profile ? (
            <ProfileBlock person={t.person} profile={profile} />
          ) : (
            <ProfileFallback tenure={t} />
          )}

          <dl className="field">
            <dt>置信度</dt>
            <dd>
              <div className="conf">
                <div className="conf-bar">
                  <i
                    className={t.confidence < 0.6 ? "low" : ""}
                    style={{ width: `${confPct}%` }}
                  />
                </div>
                <span className="conf-num">{t.confidence.toFixed(1)}</span>
              </div>
            </dd>
          </dl>

          <dl className="field">
            <dt>出处</dt>
            <dd className="small">{sourceText}</dd>
          </dl>

          {t.note && (
            <dl className="field">
              <dt>年表原文</dt>
              <dd className="serif pre">{t.note}</dd>
            </dl>
          )}

          {blk ? (
            <div className="shilu-block">
              <h3>《明實錄》命中（中研院检索，与任期相关）</h3>
              {blk.hits.map((h, i) => {
                const ym = h.month
                  ? `${h.year}年${CN_MONTHS[h.month - 1]}月${h.leap ? "（閏）" : ""}`
                  : `${h.year}年`;
                return (
                  <div className="shilu-item" key={i}>
                    <span className="src">
                      {h.source}　【{ym}】
                    </span>
                    <span className="txt">{h.content || "（无内容摘要）"}</span>
                  </div>
                );
              })}
              {blk.count > blk.hits.length && (
                <div className="shilu-item more">
                  …另有 {blk.count - blk.hits.length} 条，略
                </div>
              )}
            </div>
          ) : (
            <div className="shilu-empty">
              《明實錄》检索无命中（该人未见于实录，或检索词未命中）。
            </div>
          )}

          <div className="caveat">
            <b>关于本条的确定性</b>
            <br />
            {t.confidence < 0.8
              ? "本条置信度低于 0.8，年表对任期记载可能有歧，引用前请核对原书。"
              : "任期为年表口径；月份未载处以整年表示，未作推断。"}
          </div>
        </div>
      </>
    );
  }, [tenure, onClose]);

  return (
    <aside
      className={"drawer" + (tenure ? " open" : "")}
      aria-hidden={!tenure}
      role="dialog"
      aria-label="任职详情"
    >
      {body}
    </aside>
  );
}

/* ================= 主组件 ================= */

export default function Timeline() {
  const [dims, setDims] = useState<Dims>({ slotW: DEF_SLOT_W, labelW: DEF_LABEL_W });
  const [fixedH, setFixedH] = useState(0);
  const [slot, setSlot] = useState(() => slotOf(1628, 1));
  const [hoverPerson, setHoverPerson] = useState<string | null>(null);
  const [selected, setSelected] = useState<Tenure | null>(null);
  const [openRows, setOpenRows] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(ROWS.map((r) => [r.id, true]))
  );

  const toggleRow = useCallback((id: string) => {
    setOpenRows((prev) => ({ ...prev, [id]: !(prev[id] ?? true) }));
  }, []);

  const headerRef = useRef<HTMLElement | null>(null);
  const didInitScroll = useRef(false);
  const { slotW, labelW } = dims;

  /* --- 读取 CSS 变量（响应式会改 --slot-w / --label-w）与页头高度 --- */
  useEffect(() => {
    const read = () => {
      const cs = getComputedStyle(document.documentElement);
      const sw = parseFloat(cs.getPropertyValue("--slot-w")) || DEF_SLOT_W;
      const lw = parseFloat(cs.getPropertyValue("--label-w")) || DEF_LABEL_W;
      setDims({ slotW: sw, labelW: lw });
    };
    read();
    window.addEventListener("resize", read);
    return () => window.removeEventListener("resize", read);
  }, []);

  useEffect(() => {
    const el = headerRef.current;
    if (!el) return;
    const measure = () => {
      const h = el.getBoundingClientRect().height;
      setFixedH(h);
      document.documentElement.style.setProperty("--fixed-h", `${h}px`);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* --- 初始定位：打开即崇祯元年（demo 同款观感），而非画布最左 1402 --- */
  useEffect(() => {
    if (didInitScroll.current || fixedH <= 0) return;
    didInitScroll.current = true;
    const target = Math.max(0, labelW + slot * slotW - 240);
    window.scrollTo({ left: target });
  }, [fixedH, labelW, slot, slotW]);

  /* --- 视口/响应式尺寸变化后按新几何重新定位游标（否则缩放后游标跑出屏外）--- */
  const prevDims = useRef<string>("");
  useEffect(() => {
    const key = `${labelW}:${slotW}`;
    if (prevDims.current === key) return;
    const first = prevDims.current === "";
    prevDims.current = key;
    if (first || !didInitScroll.current) return;
    const target = Math.max(0, labelW + slot * slotW - window.innerWidth * 0.38);
    window.scrollTo({ left: target });
  }, [labelW, slotW, slot]);

  /* --- 让游标保持在视口内（拖滑块/键盘逐月时画布跟随） --- */
  const ensureVisible = useCallback(
    (s: number) => {
      const x = labelW + (s + 1) * slotW;
      const left = window.scrollX;
      const right = left + window.innerWidth;
      if (x < left + labelW + 80 || x > right - 220) {
        const target = Math.max(0, labelW + s * slotW - window.innerWidth * 0.38);
        window.scrollTo({ left: target });
      }
    },
    [labelW, slotW]
  );

  const goToSlot = useCallback(
    (next: number, mode: "ensure" | "center" | "none" = "ensure") => {
      const s = Math.min(CANVAS_SLOTS - 1, Math.max(0, next));
      setSlot(s);
      if (mode === "center") {
        const target = Math.max(0, labelW + s * slotW - window.innerWidth * 0.38);
        window.scrollTo({ left: target });
      } else if (mode === "ensure") {
        ensureVisible(s);
      }
    },
    [ensureVisible, labelW, slotW]
  );

  /* --- 键盘：←/→ 逐月，Shift+←/→ 逐年，Esc 关抽屉 --- */
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") {
        setSelected(null);
        return;
      }
      const tag = (ev.target as HTMLElement)?.tagName;
      if (tag === "INPUT") return;
      const step = ev.shiftKey ? M_PER_YEAR : 1;
      if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        goToSlot(slot - step);
      }
      if (ev.key === "ArrowRight") {
        ev.preventDefault();
        goToSlot(slot + step);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [slot, goToSlot]);

  /* --- 点击画布空白处跳月 --- */
  const onBoardClick = useCallback(
    (ev: React.MouseEvent<HTMLDivElement>) => {
      const el = ev.target as HTMLElement;
      if (el.closest(".bar")) return;
      const track = el.closest(".track") as HTMLElement | null;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const s = Math.floor((ev.clientX - rect.left) / slotW);
      goToSlot(s);
    },
    [goToSlot, slotW]
  );

  const cursorYear = CANVAS_FROM + Math.floor(slot / M_PER_YEAR);
  const cursorMonth = (slot % M_PER_YEAR) + 1;

  const activeEra = useMemo(() => {
    let cur = ERA_JUMPS[0].name;
    for (const e of ERA_JUMPS) {
      if (slotOf(e.year, e.month) <= slot) cur = e.name;
    }
    return cur;
  }, [slot]);

  return (
    <>
      {/* ================= 页头（fixed 钉视口） ================= */}
      <header className="site-header" ref={headerRef}>
        <div className="masthead">
          <h1>明代职官数据库</h1>
          <span className="sub">MingOff</span>
          <span className="spacer" />
          <span className="scope">
            內閣 {META.stats.tenures} 任 · 部院 {BUYUAN_META.stats.tenures} 任 ·{" "}
            {BUYUAN_META.stats.display_persons} 人 · {CANVAS_FROM}–{CUT_Y}.{CUT_M}
          </span>
        </div>

        <div className="control">
          <div className="era">
            <span className="regnal">{eraLabel(cursorYear)}</span>
            <span className="gz">{ganzhi(cursorYear)}</span>
            <span className="anno">{cursorYear}</span>
            <span className="anno">{CN_MONTHS[cursorMonth - 1]}月</span>
          </div>
          <div className="stepper">
            <button
              aria-label="上一月"
              disabled={slot <= 0}
              onClick={() => goToSlot(slot - 1)}
            >
              ←
            </button>
            <button
              aria-label="下一月"
              disabled={slot >= CANVAS_SLOTS - 1}
              onClick={() => goToSlot(slot + 1)}
            >
              →
            </button>
          </div>
        </div>

        {/* 全朝导航：16 个年号一键跳转（242 年画布必需） */}
        <nav className="era-chips" aria-label="年号跳转">
          {ERA_JUMPS.map((e) => (
            <button
              key={e.name}
              className={activeEra === e.name ? "on" : ""}
              onClick={() => goToSlot(slotOf(e.year, e.month), "center")}
              title={`跳到${e.name}`}
            >
              {e.name}
            </button>
          ))}
        </nav>

        <div className="slider-strip">
          <input
            type="range"
            min={0}
            max={CANVAS_SLOTS - 1}
            step={1}
            value={slot}
            aria-label="年月"
            onChange={(ev) => goToSlot(Number(ev.target.value))}
          />
        </div>
      </header>

      {/* ================= 画布 ================= */}
      <main style={{ paddingTop: fixedH || undefined }}>
        <div className="legend">
          <span className="item">
            <i className="swatch s-shishou" />
            任职（实授）
          </span>
          <span className="item">
            <i className="swatch s-fuzzy" />
            起月未载
          </span>
          <span className="item">
            <i className="swatch s-conflict" />
            同年并格待校
          </span>
          <span className="item">
            <i className="swatch s-roworder" />
            归属待核（灰显）
          </span>
          <span className="item">
            <i className="swatch s-period" />
            分期名带
          </span>
          <span className="item">
            <i className="cursor-demo" />
            当前年月
          </span>
        </div>

        <div className="board-wrap">
          <div
            className="board"
            style={{ width: labelW + CANVAS_SLOTS * slotW }}
            onClick={onBoardClick}
          >
            <Axis slotW={slotW} />
            <ReignRow slotW={slotW} />
            {ROWS.map((row) => {
              if (row.parent && !(openRows[row.parent] ?? true)) return null;
              return (
                <OfficeRow
                  key={row.id}
                  row={row}
                  open={openRows[row.id] ?? true}
                  onToggle={() => toggleRow(row.id)}
                  slotW={slotW}
                  slot={slot}
                  hoverPerson={hoverPerson}
                  onHover={setHoverPerson}
                  onSelect={setSelected}
                />
              );
            })}

            <ColumnLines slotW={slotW} labelW={labelW} />

            {/* 断限线：1644 年 3 月末 = 数据区右缘（board 坐标含标签列） */}
            <span
              className="cutoff"
              style={{ left: labelW + CANVAS_SLOTS * slotW }}
            />
            <span
              className="cutoff-label"
              style={{ left: labelW + CANVAS_SLOTS * slotW }}
            >
              1644.3
            </span>
          </div>

          {/* 游标：指在当前月格右缘（"在该月内"） */}
          <span
            className="cursor"
            style={{ left: labelW + (slot + 1) * slotW }}
            aria-hidden
          />
        </div>
      </main>

      {/* ================= 页脚 ================= */}
      <footer>
        <div className="rule" />
        <p>
          <span className="k">数据范围</span>　画布自洪武元年（1368）至崇祯十七年三月
          （1644.3）；内阁大臣 {DATA_FROM}–1644.3（内阁始设于建文四年），
          {META.stats.tenures} 任职段、{META.stats.persons} 人；部院大臣（六部 +
          都察院等）1368–1644.3，{BUYUAN_META.stats.tenures} 任职段、
          {BUYUAN_META.stats.display_persons} 人。
          <b>缺载处留空，不作填补；洪武—建文三年内阁未设，画布留空。</b>
        </p>
        <p>
          <span className="k">断限</span>　止于崇祯十七年三月（1644.3）；已剔除三月之后
          的南明任命（高弘圖、王應熊、史可法、馬士英等），不做南明。
        </p>
        <p>
          <span className="k">时间轴</span>　每月一格、各格等宽（无限画布，随内容横向
          滚动）；月份未载者占满整年，详情中注明。年号条可一键跳代，←/→ 逐月
          （Shift 逐年）。六部与都察院行可折叠；行名固定，行上「分期名带」按年代
          显示原书表头（御史臺 / 都察院 / 御史府；總督京儲 / 總督倉場 / 總倉場）。
        </p>
        <p>
          <span className="k">皇帝行</span>　每位皇帝一段（英宗两度临御分正統/天順）；
          年内小字为<b>当年二月周岁</b>（生年据通行史料；生日未到者取"年差减一"，
          保守不虚报）。
        </p>
        <p>
          <span className="k">月份依据</span>　年表注文所记任免月份；详情抽屉另列
          中研院「明代职官资料库」检索《明實錄》命中（取与本人任期相关者，每条
          附出处）。
        </p>
        <p>
          <span className="k">史料依据</span>　张德信《明代职官年表》册1·內閣大臣年表、
          部院大臣年表（京師）（MinerU OCR 表格重解析；缺块以原书 PDF 页补录）；
          人物对齐 CBDB（内阁 {META.stats.cbdb_aligned} 段 / 部院{" "}
          {BUYUAN_META.stats.cbdb_aligned} 段）。
        </p>
        <p>
          <span className="k">数据说明</span>　年表为「年在位」体：某年列名即该年在任。
          部院数据 12 衙按原书表头各自独立（不合并实体）；画布上把御史系列、倉場系列
          分组显示，仅为阅读便利。「归属待核」灰显段 = 对页无标签年按行序推断，
          引用前请回原书页核对（D-11 方案 B）。
        </p>
        <p style={{ marginTop: 12 }}>
          开源非商业项目 · 代码 Apache-2.0 · 本项目整理数据 CC BY-NC-SA 4.0
        </p>
      </footer>

      <Drawer tenure={selected} onClose={() => setSelected(null)} />
    </>
  );
}
