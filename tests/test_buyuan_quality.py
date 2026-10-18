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
