# -*- coding: utf-8 -*-
"""六科任职段（official_kejishizhong）校验：G2/G3/G6-六科版 + 锚点 + book-patch。"""
import json
from pathlib import Path

import pytest

from mingoff import official_kejishizhong as ok

DATA = Path(ok.DATA)
has_asset = (DATA / "vol2_kejishizhong_entries.json").is_file() and \
            (DATA / "official_kejishizhong.json").is_file()
pytestmark = pytest.mark.skipif(not has_asset, reason="六科数据资产未生成")


@pytest.fixture(scope="module")
def doc():
    return json.loads((DATA / "official_kejishizhong.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenures(doc):
    return doc["tenures"]


def test_scale(tenures):
    assert len(tenures) >= 700
    assert sum(len(t["years"]) for t in tenures) >= 1800
    span = (min(t["start_year"] for t in tenures), max(t["end_year"] for t in tenures))
    assert span == (1393, 1644)


def test_years_contiguous(tenures):
    for t in tenures:
        ys = t["years"]
        assert ys == list(range(ys[0], ys[-1] + 1)), t
        assert t["start_year"] == ys[0] and t["end_year"] == ys[-1]


def test_office_set(tenures):
    offices = {t["office"] for t in tenures}
    assert offices == {"吏科", "戶科", "禮科", "兵科", "刑科", "工科"}


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
    """页级溯源：全部段有起止正文页码（content_list 页脚实测；1618 由 book-patch 补入）。"""
    missing = [t for t in tenures
               if t.get("start_book_page") is None or t.get("end_book_page") is None]
    assert not missing, f"无页码段 {len(missing)}"
    for t in tenures:
        assert 1268 <= t["start_book_page"] <= 1520, t


def test_missing_years_attributed(tenures):
    """缺年白名单：未覆盖年 ⊆ 白名单（11 空框年 + 1637 原书缺页）；
    空框年必须保持未覆盖（gap 合并只允许吸收 1637 这类 1–2 年缺口）。"""
    covered: set[int] = set()
    for t in tenures:
        covered |= set(t["years"])
    missing = {y for y in range(1393, 1645) if y not in covered}
    assert missing <= ok.ALLOWED_MISSING_YEARS, \
        f"未归因缺年 {sorted(missing - ok.ALLOWED_MISSING_YEARS)}"
    assert ok.EMPTY_FRAME_YEARS <= missing, \
        f"空框年被段覆盖 {sorted(ok.EMPTY_FRAME_YEARS - missing)}"


def test_identity_span(tenures):
    """D-01：同一 person_id 跨度 ≤80 年；同名分代实体带 person_label。"""
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


def test_book_patch_applied():
    """book-patch：1618 补 3 条（src=book-patch）+ 1638 补配 4 注。"""
    entries = ok.load_keji_repaired()
    added = [e for e in entries if e.get("src") == "book-patch"
             and e["year"] == 1618 and e.get("book_page") == "book-p1493"]
    assert {(e["office"], e["person"]) for e in added} == \
        {("吏科", "趙興邦"), ("戶科", "吴亮嗣"), ("兵科", "趙興邦")}
    patched = {e["person"]: e["note"] for e in entries
               if e["year"] == 1638 and e.get("src") == "book-patch"}
    assert patched == {
        "凌義渠": "是年,遷福建參政。",
        "姚思孝": "是年任;四、戊申、十五,奏。",
        "何楷": "五、丁丑、十五,奏;七、戊寅、十七,降二級調用。",
        "范淑泰": "十一、丙寅、八,奏。",
    }


def test_anchors(tenures):
    def segs(who, off):
        return [t for t in tenures if t["person"] == who and t["office"] == off]

    # 1393 首年（解析锚点 冀凱 工科）
    assert any(t["person"] == "冀凱" and t["office"] == "工科"
               and t["start_year"] == 1393 and t["start_book_page"] == 1268
               for t in tenures)
    # 1618 book-patch：趙興邦 兵科(署)→遷吏都；吏科 1618.11 入（页 1493）
    zhao_bing = segs("趙興邦", "兵科")
    assert any(t["start_year"] == 1617 and t["end_year"] == 1618
               and t["leave"] == "遷除" for t in zhao_bing)
    zhao_li = segs("趙興邦", "吏科")
    assert any(t["start_year"] == 1618 and t["start_month"] == 11
               and t["start_book_page"] == 1493 for t in zhao_li)
    assert segs("吴亮嗣", "戶科") and \
        any(t["start_year"] == 1618 and t["start_book_page"] == 1493
            for t in segs("吴亮嗣", "戶科"))
    # 1637 原书缺页：凌義渠 兵科 1636.9 任 → 1638 遷除，gap_years=[1637] 显式记录
    ling = segs("凌義渠", "兵科")
    assert any(t["start_year"] == 1636 and t["start_month"] == 9
               and t["end_year"] == 1638 and t.get("gap_years") == [1637]
               and t["leave"] == "遷除" for t in ling)
    # 1638 补注生效
    assert any(t["start_month"] == 4 for t in segs("姚思孝", "兵科"))
    assert any(t["start_year"] == 1638 and t["end_year"] == 1638
               and t["leave"] == "降職" for t in segs("何楷", "工科"))
    # 1644 甲申殉难
    assert any(t["start_year"] == 1643 and t["end_year"] == 1644
               and t["leave"] == "殉難" for t in segs("吴甘來", "戶科"))


def test_page_map_anchors():
    """页映射实测：锚点全中、表块游标闭合、公式偏差仅 1638–1643 的 −1。"""
    page_map, ver = ok.build_page_map_keji()
    assert ver["status"] == "ok"
    assert ver["anchors_ok"], ver["anchors"]
    assert ver["blocks_consumed"] == ver["table_blocks_content_list"] == 246
    devs = {y: fo - pr for y, pr, fo in ver["formula_deviations"]}
    assert set(devs.values()) == {1} and set(devs) == set(range(1638, 1645)), devs
    assert page_map[1618] == 1493 and 1637 not in page_map


def test_audit_clean():
    r = ok.audit()
    assert not r["blockers"], r["blockers"]
    assert not r["warnings"], r["warnings"]
