# -*- coding: utf-8 -*-
"""部院 v2 质量门（G6）：把《数据接入规范》3.6/3.7 的硬规则写成测试。

覆盖：伪人名=0、注文错挂=0、重复条目=0、CBDB 多正名/生卒冲突=0、
无法解释的短断段=0、衙署归并、manifest 与实测一致，以及原书补注锚点。
"""
import json
from pathlib import Path

import pytest

from mingoff import official_buyuan as ob
from mingoff.audit_buyuan import audit

DATA = Path(ob.DATA)
has_asset = (DATA / "vol1_buyuan_entries_v2.json").is_file() and \
            (DATA / "official_buyuan.json").is_file() and \
            (DATA / "vol1_buyuan_person_cbdb_v2.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="部院 v2 资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_buyuan.json").read_text(encoding="utf-8"))


def test_g6_audit_has_no_blockers():
    """G6：审计 blockers 为空才可标 accepted / 接入站点。"""
    r = audit()
    assert r["blockers"] == [], r["blockers"]


def test_book_patched_cases():
    """原书页可定的多格注文错配（p466/467/468/484/建文页）。"""
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))

    def note(year, person, office):
        return next(e["note"] for e in entries
                    if (e["year"], e["person"], e["office"]) == (year, person, office))

    assert "卒" in note(1431, "郭敦", "戶部")
    assert "兼掌" in note(1431, "胡濙", "戶部")
    assert "卒" not in note(1431, "胡濙", "戶部")
    assert "改南京戶部" in note(1432, "黃福", "戶部")
    assert note(1432, "胡濙", "戶部") == ""
    assert "追封湯陰伯" in note(1433, "郭資", "戶部")
    assert note(1433, "胡濙", "戶部") == ""
    assert "死難" not in note(1449, "于謙", "兵部")
    assert "死難" in note(1449, "鄺埜", "兵部")
    people_1399 = {e["person"] for e in entries if e["year"] == 1399 and e["office"] == "御史府"}
    assert "練子寧" in people_1399


def test_offices_not_merged(doc):
    """不同衙署不得合并：御史臺/都察院/御史府、總督京儲/總督倉場各自独立。"""
    offices = {t["office"] for t in doc["tenures"]}
    assert {"御史臺", "都察院", "御史府", "總督京儲", "總督倉場"} <= offices
    assert {"吏部", "戶部", "禮部", "兵部", "刑部", "工部"} <= offices
    assert all("office_lineage" not in t for t in doc["tenures"])


def test_gap_flags_are_explicit(doc):
    """合并的缺口必须写 gap_years；未合并的长缺口必须写 gap_after（不得静默）。"""
    for t in doc["tenures"]:
        if t.get("gap_years"):
            assert set(t["gap_years"]) <= set(t["years"]), t
        if t.get("gap_after"):
            assert all(y > t["end_year"] for y in t["gap_after"]), t


def test_note_review_d02_is_exhaustive():
    """D-02：所有隔离注文必须 100% 有处置记录（数量随 D-03 补行变化）。"""
    p = DATA / "vol1_buyuan_note_review.json"
    rp = DATA / "vol1_buyuan_repair.json"
    if not p.is_file() or not rp.is_file():
        pytest.skip("note review 未生成")
    nr = json.loads(p.read_text(encoding="utf-8"))
    expected = len(json.loads(rp.read_text(encoding="utf-8"))["note_quarantine"])
    assert len(nr["decisions"]) == expected
    counts = nr["counts"]
    assert sum(counts.values()) == expected
    allowed = {"restored-self", "reassigned", "reassigned-inferred",
               "restored-prefix-inferred", "manual-review"}
    assert {d["action"] for d in nr["decisions"]} <= allowed


def test_d03_1440_book_rows():
    """D-03 原书 p475：1440 应有 9 人，含王驥/胡濙/吳中；魏源/劉中敷注已清。"""
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
    rows = [e for e in entries if e["year"] == 1440]
    assert len(rows) == 9, [(e["person"], e["office"]) for e in rows]
    keys = {(e["person"], e["office"]) for e in rows}
    assert {("王驥", "兵部"), ("胡濙", "禮部"), ("吳中", "工部")} <= keys
    assert next(e for e in rows if e["person"] == "魏源")["note"] == ""
    assert next(e for e in rows if e["person"] == "劉中敷")["note"] == ""


def test_d03_more_book_rows():
    """D-03 后续补行：1369 湯和/鄧愈拆分；1539/1541 毛伯溫、1539 翟鑾、1620 孫慎行。"""
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))

    def has(year, person, office):
        return any((e["year"], e["person"], e["office"]) == (year, person, office)
                   for e in entries)

    assert has(1369, "湯和", "御史臺") and has(1369, "鄧愈", "御史臺")
    assert not any(e["person"] == "湯和鄧愈" for e in entries)
    assert has(1539, "翟鑾", "兵部") and has(1539, "毛伯溫", "都察院")
    assert has(1541, "毛伯溫", "都察院")
    assert has(1620, "孫慎行", "禮部")


def test_d08_page_index_coverage():
    """D-08：277 年全有页码；条目页码覆盖 ≥90%。"""
    pages = json.loads((DATA / "vol1_buyuan_pages.json").read_text(encoding="utf-8"))
    assert len(pages) == 277
    assert pages["1368"]["pdf_page"] == 417
    assert pages["1440"]["book_page"] == 475
    assert pages["1644"]["pdf_page"] == 694
    entries = json.loads((DATA / "vol1_buyuan_entries_v2.json").read_text(encoding="utf-8"))
    covered = sum(1 for e in entries if e.get("book_page"))
    assert covered / len(entries) >= 0.9


def test_d03_gap_review_complete():
    """D-03 筛查：117 条长缺口均有 status，且 0 条 unexplained。"""
    p = DATA / "vol1_buyuan_gap_review.json"
    if not p.is_file():
        pytest.skip("gap review 未生成")
    gr = json.loads(p.read_text(encoding="utf-8"))
    assert len(gr["gaps"]) == 117
    assert gr["counts"].get("unexplained", 0) == 0
    assert {g["status"] for g in gr["gaps"]} <= {"verified-real", "screened-real", "unexplained"}


def test_identity_split_d01(doc):
    """D-01：同名多人必须拆成独立 person_id；同一实体跨度不得跨代。"""
    tenures = doc["tenures"]
    assert all(t.get("person_id") and t.get("person_label") for t in tenures)
    # person_id 是实体主键，姓名可以重名
    by_id = {}
    for t in tenures:
        by_id.setdefault(t["person_id"], []).append(t)
    spans = {pid: (min(t["start_year"] for t in ts), max(t["end_year"] for t in ts))
             for pid, ts in by_id.items()}
    assert spans["李本#1"][1] <= 1400
    assert spans["李本#2"][0] == 1556
    assert spans["王佐#1"][1] <= 1500
    assert spans["王佐#2"][0] >= 1600
    # 6 组同名各 2 个实体
    groups = {}
    for t in tenures:
        groups.setdefault(t["person"], set()).add(t["person_id"])
    for name in ("李本", "李敏", "王佐", "顧佐", "吳山", "胡松"):
        assert len(groups[name]) == 2, (name, groups[name])
    # 張鳳 1629 已改名張鳳翔，不再与正统張鳳串人
    assert "張鳳" not in {t["person"] for t in tenures if "#" in t["person_id"]}
    assert "張鳳翔" in {t["person"] for t in tenures}
    # CBDB 只挂到有证据的实体
    assert doc["tenures"] and any(t["person_id"] == "李本#2" and t["cbdb_id"] == 223131
                                  for t in tenures)
    assert all(t["cbdb_id"] is None for t in tenures if t["person_id"] == "李本#1")
