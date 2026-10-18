# -*- coding: utf-8 -*-
"""部院任职段（official_buyuan）校验：G2/G3/G4 部院版。"""
import json
from pathlib import Path

import pytest

from mingoff import official_buyuan as ob

DATA = Path(ob.DATA)
has_asset = (DATA / "vol1_buyuan_entries.json").is_file() and \
            (DATA / "official_buyuan.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="部院数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_buyuan.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    # v2 修复后：1,200+ 段（quarantine 与分段合并后）；覆盖 1368–1644 全期
    assert len(tenures) >= 1100
    assert sum(len(t["years"]) for t in tenures) >= 3400
    span = (min(t["start_year"] for t in tenures), max(t["end_year"] for t in tenures))
    assert span == (1368, 1644)


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t
        assert t["start_year"] == ys[0] and t["end_year"] == ys[-1]


def test_office_set(tenures):
    offices = {t["office"] for t in tenures}
    assert {"吏部", "戶部", "禮部", "兵部", "刑部", "工部", "都察院"} <= offices
    # 无未归部残留（entries 已归零则此断言成立）
    assert "未歸部" not in offices


def test_month_rules(tenures):
    for t in tenures:
        for k in ("start_month", "end_month"):
            m = t[k]
            assert m is None or (1 <= m <= 12), (t["person"], k, m)
    # 同年入离倒挂必须带标记
    for t in tenures:
        if (t["start_year"] == t["end_year"] and t["start_month"] and t["end_month"]
                and t["start_month"] > t["end_month"]):
            assert t["month_conflict"], t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["end_year"] == 1644:
            assert t["end_month"] == 3 and t["end_clamped"], t
        if t["start_year"] == 1644 and t["start_month"]:
            assert t["start_month"] <= 3, t


def test_confidence_scale(tenures):
    for t in tenures:
        assert t["confidence"] in (0.5, 0.6, 0.7, 0.8)
        # 0.8 必须双侧事件齐备
        if t["confidence"] == 0.8:
            assert t["leave"] != "未載"


def test_tenure_type(tenures):
    for t in tenures:
        assert t["tenure_type"] in ("实授", "署理")
        if t["tenure_type"] == "署理":
            assert "署" in (t["note"] or "")


def test_same_name_risk_flagged(tenures):
    # 同名组（張鳳/胡松/李敏/王佐/顧佐/吳山/李本）的段必须带风险标记
    risky = {t["person"] for t in tenures if t.get("same_name_risk")}
    assert {"張鳳", "胡松", "李敏", "王佐", "顧佐", "吳山", "李本"} <= risky


def test_anchor_tenures(tenures):
    def seg(p, o, sy):
        return next(t for t in tenures if t["person"] == p and t["office"] == o
                    and t["start_year"] == sy)
    # 于謙：正统十四年八月由兵右侍遷兵尚
    t = seg("于謙", "兵部", 1449)
    assert t["start_month"] == 8
    # 胡濙：宣德元年四月禮左侍遷
    t = seg("胡濙", "禮部", 1426)
    assert t["start_month"] == 4
    # 李遇知：崇祯十六年五月南吏尚改，截 1644.3
    t = seg("李遇知", "吏部", 1643)
    assert t["start_month"] == 5 and t["end_clamped"]
    # 倪元璐：崇祯十六年五月，截 1644.3
    t = seg("倪元璐", "戶部", 1643)
    assert t["end_clamped"] and t["end_month"] == 3
    # 張璁：嘉靖六年署掌都察院 → 署理
    t = seg("張璁", "都察院", 1527)
    assert t["tenure_type"] == "署理"
    # 寇深：天顺元年任左都御史，五年曹钦之变前在任
    t = seg("寇深", "都察院", 1457)
    assert t["end_year"] == 1461


def test_meta_stats(doc):
    s = doc["meta"]["stats"]
    assert s["tenures"] == len(doc["tenures"])
    assert s["persons"] == len({t["person"] for t in doc["tenures"]})
    assert s["person_years"] == sum(len(t["years"]) for t in doc["tenures"])
    assert doc["meta"]["dataset"] == "mingoff-buyuan"
