# -*- coding: utf-8 -*-
"""镇守总兵官年表任职段（official_zongbing）校验。"""
import json
from pathlib import Path

import pytest

from mingoff import official_zongbing as ozb

DATA = Path(ozb.DATA)
has_asset = (DATA / "vol3_zongbing_entries.json").is_file() and \
            (DATA / "official_zongbing.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="总兵数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_zongbing.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 200
    span = (min(t["start_year"] for t in tenures),
            max(t["end_year"] for t in tenures))
    assert span[0] <= 1400 and span[1] == 1644, span


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t


def test_month_rules(tenures):
    for t in tenures:
        for k in ("start_month", "end_month"):
            assert t[k] is None or 1 <= t[k] <= 12, t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["start_year"] == 1644:
            assert (t["start_month"] or 1) <= 3, t


def test_page_traceable(tenures):
    for t in tenures:
        assert t["start_book_page"] and t["end_book_page"], t
        assert 2924 <= t["start_book_page"] <= t["end_book_page"] <= 3182, t


def test_audit_clean():
    r = ozb.audit()
    assert not r["blockers"], r["blockers"]
