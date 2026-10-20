# -*- coding: utf-8 -*-
"""从 CBDB 快照导出人物小传（生卒/籍贯/别名/入仕/历任），供正式站抽屉展示。

输入：
  src/mingoff/data/vol1_person_cbdb.json         内阁人物→cbdb_id
  src/mingoff/data/vol1_buyuan_person_cbdb_v3.json 部院实体（person_id）→cbdb_id
  _cbdb/cbdb_20261010.sqlite3
输出：
  src/mingoff/data/person_profiles.json          内阁（按姓名；兼容 D23）
  src/mingoff/data/person_profiles_buyuan.json   部院（按 person_id，D46）

口径：
  * 生卒年只取年（CBDB 年精度；月日不显示，避免虚报精度）；
  * 籍贯取 BIOG_ADDR_DATA type=1（籍貫/基本地址），无则退回 BIOG_MAIN 索引地址；
  * 别名只保留 字/号/谥/别名 四类；
  * 历任按首年排序，最多 30 条（另记总数）；官职与年份原样保留，未载年不补；
  * 不做任何史实推断，只做 CBDB 数据的搬运与排版。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import sqlite3

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]          # mingoff/
DATA = ROOT / "src" / "mingoff" / "data"
CBDB = Path(__file__).resolve().parents[3] / "_cbdb" / "cbdb_20261010.sqlite3"
if not CBDB.is_file():
    CBDB = Path("_cbdb/cbdb_20261010.sqlite3")

OUT_CABINET = DATA / "person_profiles.json"
OUT_BUYUAN = DATA / "person_profiles_buyuan.json"
OFFICE_LIMIT = 30

ALT_TYPES = {"字", "別號", "室名、別號", "諡號", "别名、曾用名"}


def connect():
    return sqlite3.connect(f"file:{CBDB}?mode=ro", uri=True)


def empty_profile(pid=None, cbdb_name=None) -> dict:
    return {
        "cbdb_id": pid,
        "cbdb_name": cbdb_name,
        "birth": None,
        "death": None,
        "death_age": None,
        "native_place": None,
        "alt_names": [],
        "entry": [],
        "offices": [],
        "office_total": 0,
    }


def fill_profile(conn: sqlite3.Connection, pid: int, prof: dict, mapping: dict,
                 span: tuple[int, int] | None = None) -> None:
    """把某 cbdb_id 的小传字段填进 prof；mapping 的出生/卒年作兜底。

    span 为该实体在年表里的任职年区间：mapping 的兜底生卒若与任职区间明显冲突
    （如 顧佐#1 映射误抄了同名者的 1443 生年，而其任期 1429–1436），则不采用。
    """
    row = conn.execute(
        "SELECT c_birthyear,c_deathyear,c_death_age,c_index_addr_id FROM BIOG_MAIN "
        "WHERE c_personid=?", (pid,)
    ).fetchone()
    if row:
        prof["birth"] = row["c_birthyear"] or None
        prof["death"] = row["c_deathyear"] or None
        prof["death_age"] = row["c_death_age"] or None
    # 映射表里的生卒（人工裁决/百科）作兜底：CBDB 空壳记录也能显示
    mb, md = mapping.get("birth"), mapping.get("death")
    if span:
        lo, hi = span
        if mb is not None and mb > hi + 1:
            mb = None
        if md is not None and md < lo - 1:
            md = None
    if prof["birth"] is None and mb:
        prof["birth"] = mb
    if prof["death"] is None and md:
        prof["death"] = md

    # 籍贯：BIOG_ADDR_DATA type=1 优先，退回 BIOG_MAIN 索引地址
    addr = conn.execute(
        "SELECT a.c_name_chn FROM BIOG_ADDR_DATA d "
        "JOIN ADDR_CODES a ON a.c_addr_id=d.c_addr_id "
        "WHERE d.c_personid=? AND d.c_addr_type=1 "
        "ORDER BY d.c_natal DESC LIMIT 1", (pid,)
    ).fetchone()
    if not addr and row and row["c_index_addr_id"]:
        addr = conn.execute(
            "SELECT c_name_chn FROM ADDR_CODES WHERE c_addr_id=?",
            (row["c_index_addr_id"],)
        ).fetchone()
    if addr:
        prof["native_place"] = addr["c_name_chn"]

    # 别名
    seen = set()
    for r in conn.execute(
        "SELECT a.c_alt_name_chn,t.c_name_type_desc_chn FROM ALTNAME_DATA a "
        "LEFT JOIN ALTNAME_CODES t ON t.c_name_type_code=a.c_alt_name_type_code "
        "WHERE a.c_personid=?", (pid,)
    ):
        typ = (r["c_name_type_desc_chn"] or "").strip()
        nm = (r["c_alt_name_chn"] or "").strip()
        if not nm or typ not in ALT_TYPES:
            continue
        key = (typ, nm)
        if key in seen:
            continue
        seen.add(key)
        prof["alt_names"].append({"type": typ, "name": nm})

    # 入仕
    for r in conn.execute(
        "SELECT e.c_year, ec.c_entry_desc_chn FROM ENTRY_DATA e "
        "LEFT JOIN ENTRY_CODES ec ON ec.c_entry_code=e.c_entry_code "
        "WHERE e.c_personid=? ORDER BY e.c_year", (pid,)
    ):
        desc = (r["c_entry_desc_chn"] or "").strip()
        if not desc or desc in ("未知", "[缺乏信息]"):
            continue
        prof["entry"].append({"year": r["c_year"] or None, "desc": desc})

    # 历任
    rows = conn.execute(
        "SELECT o.c_office_chn,p.c_firstyear,p.c_lastyear,p.c_fy_month,p.c_ly_month "
        "FROM POSTED_TO_OFFICE_DATA p JOIN OFFICE_CODES o ON o.c_office_id=p.c_office_id "
        "WHERE p.c_personid=? "
        "ORDER BY COALESCE(p.c_firstyear, 9999), p.c_office_id", (pid,)
    ).fetchall()
    seen_off = set()
    offices = []
    for r in rows:
        key = (r["c_office_chn"], r["c_firstyear"], r["c_lastyear"])
        if key in seen_off:
            continue
        seen_off.add(key)
        offices.append({
            "office": r["c_office_chn"],
            "from": r["c_firstyear"] or None,
            "to": r["c_lastyear"] or None,
        })
    prof["office_total"] = len(offices)
    prof["offices"] = offices[:OFFICE_LIMIT]


def build_persons(conn, keys, mapping, spans=None) -> dict[str, dict]:
    spans = spans or {}
    persons: dict[str, dict] = {}
    for key in sorted(keys):
        m = mapping.get(key, {})
        pid = m.get("cbdb_id")
        prof = empty_profile(pid, m.get("cbdb_name"))
        if pid:
            fill_profile(conn, int(pid), prof, m, spans.get(key))
        persons[key] = prof
    return persons


def main():
    conn = connect()
    conn.row_factory = sqlite3.Row
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ---- 内阁（按姓名，保持 D23 兼容） ----
    cabinet_map = json.loads((DATA / "vol1_person_cbdb.json").read_text(encoding="utf-8"))
    cabinet = json.loads((DATA / "official_cabinet.json").read_text(encoding="utf-8"))
    cabinet_keys = {t["person"] for t in cabinet["tenures"]}
    cabinet_spans: dict[str, tuple[int, int]] = {}
    for t in cabinet["tenures"]:
        lo, hi = cabinet_spans.get(t["person"], (t["start_year"], t["end_year"]))
        cabinet_spans[t["person"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    cabinet_persons = build_persons(conn, cabinet_keys, cabinet_map, cabinet_spans)
    cabinet_doc = {
        "meta": {
            "dataset": "cabinet",
            "generated_at": generated,
            "persons": len(cabinet_persons),
            "office_limit": OFFICE_LIMIT,
            "cbdb_person_url": "https://cbdb.fas.harvard.edu/cbdbapi/person.php?id={id}",
            "sinica_url": "https://dh.rchss.sinica.edu.tw/MingChaoffTitle/",
            "sinica_output_url": "https://dh.rchss.sinica.edu.tw/MingChaoffTitle/output.php",
        },
        "persons": cabinet_persons,
    }
    OUT_CABINET.write_text(json.dumps(cabinet_doc, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    # ---- 部院（按 person_id：顧佐#1 / 顧佐#2 各自独立，D46） ----
    buyuan_map = json.loads(
        (DATA / "vol1_buyuan_person_cbdb_v3.json").read_text(encoding="utf-8")
    )
    buyuan = json.loads((DATA / "official_buyuan.json").read_text(encoding="utf-8"))
    buyuan_keys = {t["person_id"] for t in buyuan["tenures"]}
    buyuan_spans: dict[str, tuple[int, int]] = {}
    for t in buyuan["tenures"]:
        key = t["person_id"]
        lo, hi = buyuan_spans.get(key, (t["start_year"], t["end_year"]))
        buyuan_spans[key] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    buyuan_persons = build_persons(conn, buyuan_keys, buyuan_map, buyuan_spans)
    with_id = sum(1 for p in buyuan_persons.values() if p["cbdb_id"])
    buyuan_doc = {
        "meta": {
            "dataset": "buyuan",
            "generated_at": generated,
            "persons": len(buyuan_persons),
            "with_cbdb_id": with_id,
            "office_limit": OFFICE_LIMIT,
            "cbdb_person_url": "https://cbdb.fas.harvard.edu/cbdbapi/person.php?id={id}",
            "sinica_url": "https://dh.rchss.sinica.edu.tw/MingChaoffTitle/",
            "sinica_output_url": "https://dh.rchss.sinica.edu.tw/MingChaoffTitle/output.php",
        },
        "persons": buyuan_persons,
    }
    OUT_BUYUAN.write_text(json.dumps(buyuan_doc, ensure_ascii=False, indent=1),
                          encoding="utf-8")

    print(f"内阁 {len(cabinet_persons)} 人 → {OUT_CABINET.name}"
          f"（{OUT_CABINET.stat().st_size/1024:.0f} KB）")
    print(f"部院 {len(buyuan_persons)} 实体（{with_id} 有 CBDB id）→ "
          f"{OUT_BUYUAN.name}（{OUT_BUYUAN.stat().st_size/1024:.0f} KB）")

    for nm in ("楊士奇", "張居正", "申時行", "嚴嵩", "蔣德璟"):
        p = cabinet_persons.get(nm)
        if p:
            print(f"  {nm}: {p['birth']}-{p['death']} {p['native_place']} "
                  f"别名{len(p['alt_names'])} 历任{p['office_total']} 入仕{len(p['entry'])}")
    for key in ("胡濙", "顧佐#1", "顧佐#2", "胡松#1", "高燿"):
        p = buyuan_persons.get(key)
        if p:
            print(f"  {key}: {p['birth']}-{p['death']} {p['native_place']} "
                  f"别名{len(p['alt_names'])} 历任{p['office_total']}")
    conn.close()


if __name__ == "__main__":
    main()
