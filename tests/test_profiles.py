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


# ============ 京卿/六科/侍郎小传（2026-11-08 接入，按 person_id，只收有 CBDB id 者） ============

EXT_TABLES = [
    ("jingqing", "person_profiles_jingqing.json"),
    ("kejishizhong", "person_profiles_kejishizhong.json"),
    ("shilang", "person_profiles_shilang.json"),
]


def load_ext(doc_name: str) -> dict:
    path = DATA / doc_name
    assert path.is_file(), f"{doc_name} 未入仓（运行 python -m mingoff.build_person_profiles）"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("dataset,doc_name", EXT_TABLES)
def test_ext_profile_coverage(dataset, doc_name):
    doc = load_ext(doc_name)
    meta, persons = doc["meta"], doc["persons"]
    assert meta["dataset"] == dataset
    # 构建口径：只收对齐 CBDB 的实体，全部带 id；历任上限 30 条（超出截断）
    assert persons and meta["with_cbdb_id"] == len(persons)
    for key, p in persons.items():
        assert p["cbdb_id"] is not None, f"{dataset} {key} 混入未对齐实体"
        if p["office_total"] > 30:
            assert len(p["offices"]) == 30


@pytest.mark.parametrize("dataset,doc_name,sur", [
    ("jingqing", "person_profiles_jingqing.json", "丁啟濬"),
    ("kejishizhong", "person_profiles_kejishizhong.json", "凌義渠"),
    ("shilang", "person_profiles_shilang.json", "郭允厚"),
])
def test_ext_profile_anchors(dataset, doc_name, sur):
    """锚点实体（姓前缀匹配，兼容 #1/#2 分代键）：CBDB 非空壳。"""
    persons = load_ext(doc_name)["persons"]
    hit = [k for k in persons if k.split("#")[0] == sur]
    assert hit, f"{dataset} 缺锚点 {sur}（现有键样例: {list(persons)[:5]}）"
    for k in hit:
        p = persons[k]
        filled = p["birth"] or p["death"] or p["native_place"] or p["offices"]
        assert filled, f"{dataset} {k} CBDB 空壳（cbdb_id={p['cbdb_id']}）"
