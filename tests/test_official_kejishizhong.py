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


def test_cbdb_aligned(doc):
    """CBDB 对齐 v1（match_official_cbdb.py）：段级对齐量 + 已核实锚点 id。"""
    s = doc["meta"]["stats"]
    assert s["cbdb_aligned"] >= 400, s["cbdb_aligned"]

    def ids(who):
        return {t["cbdb_id"] for t in doc["tenures"]
                if t["person"] == who and t.get("cbdb_id")}

    # 顏繼祖 63703：CBDB 任职链 工科給→工科右→戶科右→戶科左→吏科都 與本表互证；卒 1639
    assert ids("顏繼祖") == {63703}
    # 凌義渠 34757：生卒 1593–1644 与史实吻合（manual，京卿表同证）
    assert ids("凌義渠") == {34757}
    # 吴亮嗣 351474：exact-unique 唯一同名候选
    assert ids("吴亮嗣") == {351474}


def test_audit_clean():
    r = ok.audit()
    assert not r["blockers"], r["blockers"]
    assert not r["warnings"], r["warnings"]


def test_nested_successor_split(tenures):
    """N1 嵌套继任者拆分（2026-11-08）：注文流内「。人名+月干支锚」拆出。

    1625 刑科格「…遷太常少。陸文獻九、癸酉、廿八,兵左給遷。」——陸文獻
    九月自兵科左給事中遷入，天启七年八月遷太常少；此前整段吞进周之綱 note，
    陸文獻 任职段起点/终点全错（1626–1627）。
    """
    lu = [t for t in tenures if t["person"] == "陸文獻" and t["office"] == "刑科"]
    assert len(lu) == 1, lu
    t = lu[0]
    assert (t["start_year"], t["end_year"]) == (1625, 1627)
    assert (t["start_month"], t["end_month"]) == (9, 8)
    assert t["leave"] == "遷除"
    assert t["cbdb_id"] == 370694
    # 前任 note 截断于界标：周之綱只留自己的两条注
    zhou = [t for t in tenures if t["person"] == "周之綱" and t["office"] == "刑科"]
    assert zhou and all("陸文獻" not in (t["note"] or "") for t in zhou)


def test_multi_cell_ordered_binding(tenures):
    """N2 多名按序绑定：天启七年刑科格「陸文獻 薛國觀八遷/十任」——
    迁出注归前任、任注归继任；薛國觀 起 1627/10。"""
    xue = [t for t in tenures if t["person"] == "薛國觀" and t["office"] == "刑科"]
    assert len(xue) == 1 and xue[0]["start_year"] == 1627
    assert xue[0]["start_month"] == 10
    assert xue[0]["cbdb_id"] == 362351


def test_nested_new_persons_present(tenures):
    """嵌套拆出的新实体在表中且带 review 留痕（entry 层）。"""
    ents = json.loads(
        (ok.DATA / "vol2_kejishizhong_entries.json").read_text(encoding="utf-8")
    )["entries"]
    nested = [e for e in ents if e.get("review") and "嵌套继任者拆分" in e["review"]]
    assert {e["person"] for e in nested} >= {"陸文獻", "趙興邦", "陳熙昌", "魏照乘"}
    # 阮大鍼/阮大鈞：OCR 异体（同一人），CBDB 双双无记录，均标待核
    ruan = [e for e in nested if e["person"] in ("阮大鍼", "阮大鈞")]
    assert len(ruan) == 2 and all(e["conf"] == 0.5 for e in ruan)


def test_split_nested_successors_unit():
    """N1 纯函数：真例 + 假阳性防线。"""
    from mingoff.ocr_jingqing import split_nested_successors

    # 真例：嵌套拆出
    h, segs = split_nested_successors(
        "三、甲戌、廿六,奏;八、乙巳、廿九,遷太常少。陸文獻九、癸酉、廿八,兵左給遷。")
    assert h.endswith("遷太常少。") and len(segs) == 1
    assert segs[0]["person"] == "陸文獻"
    assert segs[0]["note"] == "九、癸酉、廿八,兵左給遷。"

    # 纪年不拆（天故=天啟 OCR 误；锚带年前缀）
    h2, segs2 = split_nested_successors(
        "…六月卒。天故二年六、甲申、廿,贈光祿少。")
    assert segs2 == [] and h2.endswith("贈光祿少。")

    # 年号前缀不拆（；嘉靖 = band 并入残留 + 嘉靖二年…）
    h3, segs3 = split_nested_successors(
        "…遷浙江右政。；嘉靖三年八、己未、廿七,遷大理右丞。")
    assert segs3 == [] and h3.endswith("遷大理右丞。")

    # 「某某十一、」归 某某+十一月，不拆出「某某十」
    h4, segs4 = split_nested_successors("…卒。趙貞十一、甲子、三,任。")
    assert h4.endswith("卒。") and len(segs4) == 1 and segs4[0]["person"] == "趙貞"


def test_yield_inferred(doc):
    """同衙同年继任到任推定前任迄月（2026-11-09）：原书无离任注的段不再
    以年截尾与继任重叠；推定段标 yield_inferred。"""
    hit = [t for t in doc["tenures"]
           if t["person"] == "陳壽" and t["office"] == "戶科"
           and t["start_year"] == 1488]
    assert hit and hit[0].get("yield_inferred") is True
    assert hit[0]["end_month"] == 10   # 继任 張九功 1488/10 到任
    # 推定不误伤有离任注的段
    keep = [t for t in doc["tenures"] if t.get("yield_inferred")]
    assert all(t["leave"] == "未載" for t in keep)
