# -*- coding: utf-8 -*-
"""D46（2026-10-19）：部院接站前的编年校正与站点数据同步。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
SITE = ROOT / "site" / "src" / "data" / "buyuan.json"

pytestmark = pytest.mark.skipif(
    not (DATA / "official_buyuan.json").is_file(), reason="部院数据资产未生成"
)


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_buyuan.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def covered(tenures, person, office, year):
    return [
        t
        for t in tenures
        if t["person"] == person and t["office"] == office
        and t["start_year"] <= year <= t["end_year"]
    ]


def test_1380_censor_is_yushitai(tenures):
    """1380 原书页眉注「五月罷御史臺」；陳寧/安然归御史臺，不归都察院。"""
    assert covered(tenures, "陳寧", "御史臺", 1380)
    assert covered(tenures, "安然", "御史臺", 1380)
    assert not covered(tenures, "陳寧", "都察院", 1380)


def test_1398_bao_zhao_is_duchayuan(tenures):
    """1398 原书误作御史臺；《建文年譜》《憲章類編》证仍为都察院。"""
    assert covered(tenures, "暴昭", "都察院", 1398)
    assert not covered(tenures, "暴昭", "御史臺", 1398)


def test_1399_yushifu_kept(tenures):
    """1399 御史府起点保留原书（D46 决策三：只记异说，不改数据）。"""
    assert covered(tenures, "景清", "御史府", 1399)
    assert covered(tenures, "練子寧", "御史府", 1399)


def test_qianchun_1631_single_tenure(tenures):
    """1631/32「督倉場」= 總倉場省文；錢春只应有一段 1630–1634，不再双段重叠。"""
    rows = [t for t in tenures if t["person"] == "錢春" and 1631 in t["years"]]
    assert len(rows) == 1, rows
    t = rows[0]
    assert t["office"] == "總倉場"
    assert (t["start_year"], t["end_year"]) == (1630, 1634)
    assert not t.get("gap_years"), "合并后不应再留 1631–32 缺口"


def test_site_buyuan_copy_in_sync(doc):
    """站点 src/data/buyuan.json 必须与数据资产同步（防接站后忘同步）。"""
    if not SITE.is_file():
        pytest.skip("站点数据副本不存在")
    site = json.loads(SITE.read_text(encoding="utf-8"))
    assert site["meta"]["stats"]["tenures"] == doc["meta"]["stats"]["tenures"]
    assert site["meta"]["stats"]["persons"] == doc["meta"]["stats"]["persons"]


def test_buyuan_profiles():
    """D46：部院小传按 person_id 接入；同名拆分各自独立，生卒不张冠李戴。"""
    path = DATA / "person_profiles_buyuan.json"
    assert path.is_file(), "部院人物小传未生成（python -m mingoff.build_person_profiles）"
    doc = json.loads(path.read_text(encoding="utf-8"))
    persons = doc["persons"]
    assert len(persons) == 789
    assert doc["meta"]["with_cbdb_id"] == 546

    hu = persons["胡濙"]
    assert hu["cbdb_id"] == 222777
    assert hu["native_place"] == "寧國府"
    assert hu["death"] == 1522

    # 顧佐#1（宣德左都御史，1429–1436）曾误抄同名者 1443 生年；span 校验后应为 None
    gu1 = persons["顧佐#1"]
    assert gu1["cbdb_id"] == 66992
    assert gu1["birth"] is None and gu1["death"] == 1446
    gu2 = persons["顧佐#2"]
    assert gu2["birth"] == 1443 and gu2["death"] == 1516

    site = ROOT / "site" / "src" / "data" / "person_profiles_buyuan.json"
    if site.is_file():
        assert json.loads(site.read_text(encoding="utf-8"))["meta"]["persons"] == len(persons)
