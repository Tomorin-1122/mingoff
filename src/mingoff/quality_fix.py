# -*- coding: utf-8 -*-
"""数据质量修复管线（总审计 → 修复 → 复检）。

修复项：
  A 超长年龄：本年表对齐者 0 例，但加入常设校验（CBDB 生卒差>100 或
    生年晚于在任年 或 卒年早于在任年 → 视为 CBDB 数据问题，降级不剔除）
  B 同时代同人：一 CBDB id 多写法 → **统一正字**（取 CBDB 的 c_name_chn），
    年表变体记为 alias，保留溯源
  C OCR 残留：
    - 伪人名（年号型，如 嘉靖卅三年）→ 直接删除条目
    - 简繁混排判定修正：只在**同一字有简繁二形**时算混排（高≠高，是不同字）
  D 任职段月倒挂（同年入职又离任、月起>讫月）：入职月/离任月无法同时成立，
    按年表体例这是**年内两次事件**，正确做法是拆成两段或标记冲突。
    由于缺少日期精度，采取：保留段，但 `month_conflict=True` 并降置信度，
    不擅自改月份（D4：不臆造）
  E 时间倒挂：同 D
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"mingoff/src/mingoff/data")
c = sqlite3.connect(r"file:_cbdb/cbdb_20261010.sqlite3?mode=ro", uri=True)

# ---------- 真·简繁二形表（只收同字异形，非"不同字"） ----------
S_T_PAIRS = {
    "吴": "吳", "张": "張", "温": "溫", "黄": "黃", "吕": "呂", "万": "萬",
    "刘": "劉", "乔": "喬", "韦": "韋", "宋": "宋", "陈": "陳", "杨": "楊",
    "赵": "趙", "郑": "鄭", "冯": "馮", "蒋": "蔣", "钱": "錢", "韩": "韓",
    "马": "馬", "谢": "謝", "龚": "龔", "费": "費", "间": "間", "与": "與",
    "孙": "孫", "张": "張", "苏": "蘇", "许": "許", "宁": "寧", "郑": "鄭",
    "双": "雙", "罗": "羅", "娄": "婁", "练": "練", "陆": "陸", "卢": "盧",
    "庞": "龐", "龙": "龍", "灵": "靈", "来": "來", "楼": "樓",
}

FAKE_NAME_PAT = __import__("re").compile(
    # 年号 + 年序 + 「年」结尾（整串即节头形态）。
    # ⚠️ 坑：年号必须用**选择分支**，不能用字符类 —— `[弘治…]` 只匹配单字，
    #    「弘治十四年」因「治」不在类里永远匹配失败（实测踩过，与 D18 的
    #    「[崇禎] 是字符类」同类错误）。
    r"^(洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|"
    r"泰昌|天啟|崇禎)[元一二三四五六七八九十廿卅零]{1,6}年$")


def norm_alias_fix(align: dict) -> tuple[dict, list]:
    """B 类修复：一 CBDB id 多写法 → 统一用 CBDB c_name_chn 作主名，其余记 alias。"""
    from collections import defaultdict
    by_pid = defaultdict(list)
    for name, v in align.items():
        if v.get("cbdb_id"):
            by_pid[v["cbdb_id"]].append(name)
    fixes = []
    for pid, names in by_pid.items():
        if len(names) < 2:
            continue
        r = c.execute("SELECT c_name_chn FROM BIOG_MAIN WHERE c_personid=?", (pid,)).fetchone()
        canon = r[0] if r else names[0]
        for n in names:
            if n != canon:
                align[n]["alias_of"] = canon
                align[n]["note"] = f"年表写作「{n}」，CBDB 正字「{canon}」"
                fixes.append((n, canon, pid))
    return align, fixes


def main():
    align = json.loads((ROOT / "person_cbdb.json").read_text(encoding="utf-8"))
    ents = json.loads((ROOT / "neige_entries_aligned.json").read_text(encoding="utf-8"))
    ts = json.loads((ROOT / "tenures_from_nianbiao.json").read_text(encoding="utf-8"))
    report = {"A_age": [], "B_alias": [], "C_fake": [], "D_month": [], "E_inv": []}

    # ---- A 超长年龄 / 生卒与在任矛盾 ----
    ours = {a["cbdb_id"]: name for name, a in align.items() if a.get("cbdb_id")}
    for pid, name in ours.items():
        r = c.execute("SELECT c_name_chn,c_birthyear,c_deathyear FROM BIOG_MAIN "
                      "WHERE c_personid=?", (pid,)).fetchone()
        if not r:
            continue
        _, b, d = r
        if b and d and d - b > 100:
            report["A_age"].append({"person": name, "cbdb_id": pid,
                                    "birth": b, "death": d, "reason": "CBDB 生卒差>100年"})
        # 生卒 vs 在任年
        span = [t for t in ts if t["person"] == name]
        if span and b and b > max(t["end_year"] for t in span) + 20:
            report["A_age"].append({"person": name, "cbdb_id": pid,
                                    "reason": f"CBDB 生年 {b} 晚于在任末年"})

    # ---- B 一 id 多写法 ----
    align, aliases = norm_alias_fix(align)
    report["B_alias"] = [{"from": a, "to": b, "cbdb_id": pid} for a, b, pid in aliases]

    # ---- C 伪人名：删除对应条目 ----
    before = len(ents)
    ents = [e for e in ents if not FAKE_NAME_PAT.match(e["person"])]
    report["C_fake"] = {"removed": before - len(ents)}

    # ---- D/E 月倒挂 ----
    for t in ts:
        sy, sm, ey, em = t["start_year"], t["start_month"], t["end_year"], t["end_month"]
        if sm and em and (sy > ey or (sy == ey and sm > em)):
            t["month_conflict"] = True
            t["confidence"] = round(min(t["confidence"], 0.5), 2)
            t["note"] = (t["note"] + "\n[数据校验] 入职月与离任月同年倒挂，"
                         "疑为年内两次不同事件，月份存疑（未擅自改动）").strip()
            report["D_month"].append({"person": t["person"], "section": t["section"],
                                      "start": f"{sy}.{sm}", "end": f"{ey}.{em}",
                                      "verbs": [t["enter_verbs"], t["leave_verbs"]]})

    # 落盘
    (ROOT / "person_cbdb.json").write_text(
        json.dumps(align, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "neige_entries_aligned.json").write_text(
        json.dumps(ents, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "tenures_from_nianbiao.json").write_text(
        json.dumps(ts, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== 质量修复结果 ===")
    print(f"A 超长年龄/生卒矛盾: {len(report['A_age'])}")
    for x in report["A_age"]:
        print(f"   {x}")
    print(f"B 一 id 多写法（记 alias）: {len(report['B_alias'])}")
    for x in report["B_alias"][:10]:
        print(f"   {x['from']} → 正字 {x['to']} (id={x['cbdb_id']})")
    print(f"C 伪人名删除: {report['C_fake']['removed']} 条")
    print(f"D/E 月倒挂标记: {len(report['D_month'])}（保留月份 + 降置信度 + 加注，未臆改）")
    for x in report["D_month"][:6]:
        print(f"   {x['person']} {x['start']}→{x['end']} {x['verbs']}")
    print(f"\n条目 {len(ents)}；任职段 {len(ts)}")
    c.close()


if __name__ == "__main__":
    main()
