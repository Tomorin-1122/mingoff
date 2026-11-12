# -*- coding: utf-8 -*-
"""侍郎任职段（official_shilang）校验：G2/G3/G6-侍郎版 + 原书核验锚点。"""
import json
from pathlib import Path

import pytest

from mingoff import official_shilang as osl

DATA = Path(osl.DATA)
has_asset = (DATA / "vol1_shilang_geo.json").is_file() and \
            (DATA / "official_shilang.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="侍郎数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_shilang.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 3300
    assert sum(len(t["years"]) for t in tenures) >= 6400
    span = (min(t["start_year"] for t in tenures), max(t["end_year"] for t in tenures))
    assert span == (1368, 1644)


def test_leave_lexicon_round2026_11_12(tenures):
    """2026-11-12 原书验证轮（侍郎侧）：简体「调」、下狱宥释、還鄉离任。"""
    def seg(p, o, sy):
        return next(t for t in tenures if t["person"] == p and t["office"] == o
                    and t["start_year"] == sy)
    # 馬森 1558「十、十五，坐调大理卿」（OCR 简体调）——曾被推成迄 11
    t = seg("馬森", "戶部右侍郎", 1558)
    assert t["leave"] == "調除" and t["end_month"] == 10 and "yield_inferred" not in t
    # 何文淵 1438「十二…下狱」——三月下狱寻宥复职不误标，十二月下狱为离任
    t = seg("何文淵", "兵部右侍郎", 1438)
    assert t["leave"] == "下狱" and t["end_month"] == 12
    # 程富 1446 三月下狱寻釋（跳过）、九月還鄉治疾（還除）——曾被推成迄 9 无据
    t = seg("程富", "右副都御史", 1446)
    assert t["leave"] == "還除" and t["end_month"] == 9


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t
        assert t["start_year"] == ys[0] and t["end_year"] == ys[-1]


def test_office_set(tenures):
    assert {t["office"] for t in tenures} <= set(osl.CANON_OFFICES)
    # 六部左/右侍郎齐全
    for m in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部"):
        assert {t["office"] for t in tenures if t["office"].startswith(m)} >= \
            {f"{m}左侍郎", f"{m}右侍郎"}


def test_month_rules(tenures):
    for t in tenures:
        for k in ("start_month", "end_month"):
            assert t[k] is None or 1 <= t[k] <= 12, t
        if t["start_year"] == t["end_year"] and t["start_month"] and t["end_month"]:
            assert t["start_month"] <= t["end_month"] or t["month_conflict"], t


def test_d15_cutoff(tenures):
    for t in tenures:
        assert t["end_year"] <= 1644
        if t["start_year"] == 1644:
            assert (t["start_month"] or 1) <= 3, t
        if t["end_year"] == 1644 and t["end_month"] is not None:
            assert t["end_month"] <= 3 or t["leave"] == "殉難", t


def test_page_traceable(tenures):
    """页级溯源：全部段有起止书页（条目自带 book 页实测，侍郎表 682–980）。"""
    missing = [t for t in tenures
               if t.get("start_book_page") is None or t.get("end_book_page") is None]
    assert not missing, f"无页码段 {len(missing)}"
    for t in tenures:
        assert 682 <= t["start_book_page"] <= 980, t


def test_missing_years_none(tenures):
    covered: set[int] = set()
    for t in tenures:
        covered |= set(t["years"])
    missing = {y for y in range(1368, 1645) if y not in covered}
    assert not missing, sorted(missing)[:10]


def test_identity_span(tenures):
    span = {}
    for t in tenures:
        lo, hi = span.get(t["person_id"], (9999, 0))
        span[t["person_id"]] = (min(lo, t["start_year"]), max(hi, t["end_year"]))
    too_long = {p for p, (lo, hi) in span.items() if hi - lo > 80}
    assert not too_long, too_long
    for t in tenures:
        if "#" in t["person_id"]:
            assert t.get("same_name_risk") and t["person_label"] != t["person"]


def test_no_overlap_same_office(tenures):
    seen = {}
    for t in tenures:
        key = (t["person_id"], t["office"])
        assert key not in seen or t["start_year"] > seen[key], t
        seen[key] = t["end_year"]


def test_gap_merge_marked(tenures):
    for t in tenures:
        if t.get("gap_years"):
            assert t.get("merged_segments", 1) >= 2
            assert t["confidence"] <= 0.6


def test_pending_gray(tenures):
    """band 警报页条目 = pending 灰显（不阻断，但必须带标 + 置信封顶）。"""
    for t in tenures:
        if t.get("pending_book_check"):
            cap = 0.5 if t["office_status"] == "pending" else 0.6
            assert t["confidence"] <= cap, t
            assert t["office_status"] in ("pending", "mixed"), t


def test_book_fix_anchors(tenures):
    """原书核验锚点（docs/侍郎表接入报告.md）：954 换带 / 760 级联 / 强制分代。"""
    def segs(who, off):
        return [t for t in tenures if t["person"] == who and t["office"] == off]

    # 954（1626）：郭允厚等四人从禮部 r3 归位兵部左侍郎带（verified，非 pending）
    guo = segs("郭允厚", "兵部左侍郎")
    assert any(t["start_year"] == 1626 and not t.get("pending_book_check")
               for t in guo)
    # 朱一桂：954 刑部带第二行右列 → 刑部右侍郎（verified）
    assert any(t["person"] == "朱一桂" and t["office"] == "刑部右侍郎"
               and t["start_year"] == 1626 and not t.get("pending_book_check")
               for t in tenures)
    # 760（1445）：李暹/姜濤 归位戶部带（李暹 段 1441–1445，卒年 1445 在段内）
    assert any(t["person"] == "李暹" and t["office"].startswith("戶部")
               and t["start_year"] <= 1445 <= t["end_year"] for t in tenures)
    # 王暹强制分代：1387–88 兵右（試）≠ 1449 左副都御史（原书 p701/p764）
    assert any(t["person_id"] == "王暹#1" and t["office"] == "兵部右侍郎"
               and t["cbdb_id"] is None for t in tenures)
    assert any(t["person_id"] == "王暹#2" and t["office"] == "左副都御史"
               and t["cbdb_id"] == 126830 for t in tenures)
    # 葉盛 吏部左侍郎（几何断言 786 页锚）
    assert any(t["person"] == "葉盛" and t["office"] == "吏部左侍郎"
               and t["start_year"] == 1473 for t in tenures)


def test_cbdb_aligned(doc):
    s = doc["meta"]["stats"]
    assert s["cbdb_aligned"] >= 2300, s["cbdb_aligned"]
    # 葉盛（吏部左侍郎，成化间名臣）应已对齐
    assert any(t["person"] == "葉盛" and t["office"] == "吏部左侍郎" and t["cbdb_id"]
               for t in doc["tenures"])


def test_audit_clean():
    r = osl.audit()
    assert not r["blockers"], r["blockers"]
