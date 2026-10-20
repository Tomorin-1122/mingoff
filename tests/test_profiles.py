# -*- coding: utf-8 -*-
"""人物小传数据测试（site 抽屉用）。

不依赖 CBDB 快照：只读已入仓的 person_profiles.json，
保证站点抽屉的人物信息完整、链接字段可用。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mingoff.official import DATA, build_cabinet_tenures  # noqa: E402

PROFILES = DATA / "person_profiles.json"

# 依赖重建输入 vol1_entries.json：精简/公开仓无此文件时跳过（见 MAINTAINERS.md）
NEED_ENTRIES = pytest.mark.skipif(
    not (DATA / "vol1_entries.json").is_file(),
    reason="缺少重建输入 vol1_entries.json（公开仓只发导出数据）",
)


def load_profiles() -> dict:
    assert PROFILES.is_file(), "person_profiles.json 未入仓（运行 python -m mingoff.build_person_profiles）"
    return json.loads(PROFILES.read_text(encoding="utf-8"))


@NEED_ENTRIES
def test_every_tenure_person_has_profile():
    doc = load_profiles()
    persons = doc["persons"]
    for t in build_cabinet_tenures():
        assert t["person"] in persons, f"缺人物小传: {t['person']}"


def test_known_profile_fields():
    persons = load_profiles()["persons"]
    yang = persons["楊士奇"]
    assert yang["cbdb_id"] == 66729
    assert yang["cbdb_name"] == "楊寓"
    assert yang["birth"] == 1364 and yang["death"] == 1444
    assert yang["native_place"] == "泰和"
    assert any(a["type"] == "字" for a in yang["alt_names"])
    assert yang["office_total"] > 0 and len(yang["offices"]) > 0
    zhang = persons["張居正"]
    assert zhang["native_place"] == "江陵"
    assert zhang["office_total"] > 0


def test_unresolved_person_profile_is_explicitly_null():
    persons = load_profiles()["persons"]
    jiang = persons["蔣德璟"]
    assert jiang["cbdb_id"] is None
    assert jiang["birth"] is None and jiang["death"] is None
    assert jiang["offices"] == []


def test_profile_meta_has_links():
    doc = load_profiles()
    meta = doc["meta"]
    assert meta["cbdb_person_url"].startswith("https://cbdb.fas.harvard.edu/")
    assert "{id}" in meta["cbdb_person_url"]
    assert meta["sinica_url"].startswith("https://dh.rchss.sinica.edu.tw/")
