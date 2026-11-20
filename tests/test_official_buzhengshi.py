# -*- coding: utf-8 -*-
"""承宣布政使年表任职段（official_buzhengshi）校验。"""
import json
from pathlib import Path

import pytest

from mingoff import official_buzhengshi as obz

DATA = Path(obz.DATA)
has_asset = (DATA / "vol4_buzhengshi_entries.json").is_file() and \
            (DATA / "official_buzhengshi.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="布政使数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_buzhengshi.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 800
    span = (min(t["start_year"] for t in tenures),
            max(t["end_year"] for t in tenures))
    assert span[0] <= 1380 and span[1] == 1644, span


def test_region_offices(tenures):
    offices = {t["office"] for t in tenures}
    for r in ("北平", "山東", "山西", "河南", "陕西", "四川", "江西", "湖廣",
              "浙江", "福建", "廣東", "廣西", "雲南", "貴州"):
        assert r in offices, r


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["start_year"] == 1644:
            assert (t["start_month"] or 1) <= 3, t


def test_page_traceable(tenures):
    for t in tenures:
        assert t["start_book_page"] and t["end_book_page"], t
        assert 3184 <= t["start_book_page"] <= t["end_book_page"] <= 3570, t


def test_audit_clean():
    r = obz.audit()
    assert not r["blockers"], r["blockers"]
