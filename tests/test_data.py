# -*- coding: utf-8 -*-
"""数据层测试：schema 约束、NULL 语义、任职/来源/异文、核心查询场景。

这些测试守的是本项目最容易出错的地方 —— **历史数据的 NULL 语义**。
史料未载写成 0 会让统计静默出错，所以每个相关行为都有显式断言。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mingoff import db as D
from mingoff import repo as R
from mingoff import seed as S


@pytest.fixture
def conn(tmp_path: Path):
    path = D.init_db(tmp_path / "m.sqlite")
    c = D.connect(path)
    yield c
    c.close()


def make_person(c, name="測試", **kw) -> int:
    return R.add_person(c, R.Person(name_chn=name, **kw))


def make_office(c, name="兵部尚書") -> int:
    return R.add_office(c, R.Office(office_chn=name, department="兵部"))


# ---------------------------------------------------------------- 建库


def test_init_creates_all_tables(tmp_path: Path):
    path = D.init_db(tmp_path / "m.sqlite")
    conn = D.connect(path, readonly=True)
    try:
        tables = set(D.table_names(conn))
    finally:
        conn.close()
    assert {"person", "office", "tenure", "source", "tenure_source", "discrepancy"} <= tables
    assert "meta" in tables


def test_init_is_idempotent(tmp_path: Path):
    path = D.init_db(tmp_path / "m.sqlite")
    D.init_db(path)  # 再跑一次不该报错
    conn = D.connect(path, readonly=True)
    try:
        assert D.get_meta(conn, "schema_version") == str(D.SCHEMA_VERSION)
    finally:
        conn.close()


def test_is_initialized(tmp_path: Path):
    assert D.is_initialized(tmp_path / "nope.sqlite") is False
    path = D.init_db(tmp_path / "m.sqlite")
    assert D.is_initialized(path) is True


def test_readonly_connection_rejects_writes(tmp_path: Path):
    """只读连接必须真的拒绝写入 —— 报表/查询不该有机会改坏数据。"""
    import sqlite3

    path = D.init_db(tmp_path / "m.sqlite")
    ro = D.connect(path, readonly=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO person(name_chn) VALUES('x')")
    finally:
        ro.close()


def test_connect_readonly_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        D.connect(tmp_path / "nope.sqlite", readonly=True)


# ---------------------------------------------------------------- 人物


def test_add_and_get_person(conn):
    pid = make_person(conn, "楊嗣昌", native_addr="武陵", birth_year=1588)
    p = R.get_person(conn, pid)
    assert p is not None
    assert p.name_chn == "楊嗣昌"
    assert p.native_addr == "武陵"
    assert p.birth_year == 1588


def test_person_unknown_years_are_none_not_zero(conn):
    """生卒年未载必须是 NULL —— 0 会被误读成"生于公元 0 年"。"""
    pid = make_person(conn, "無名氏")
    p = R.get_person(conn, pid)
    assert p.birth_year is None
    assert p.death_year is None


def test_add_person_dedupes_by_cbdb_id(conn):
    """反复导入 CBDB 快照不该造出重复人物。"""
    a = make_person(conn, "張三", cbdb_id=12345)
    b = make_person(conn, "張三", cbdb_id=12345)
    assert a == b
    assert D.count_rows(conn)["person"] == 1


def test_person_without_cbdb_id_dedupes_on_name_and_address(conn):
    """无 cbdb_id 时按 (姓名, 籍贯) 去重 —— 反复导入年表不该把人翻倍。

    注意这条**不是**"只按姓名"：明代同名者众，仅凭姓名合并有误合并风险，
    所以保留籍贯作为区分维度（见 test_add_person_dedupes_by_name_and_address）。
    """
    a = make_person(conn, "張三", native_addr="武陵")
    b = make_person(conn, "張三", native_addr="武陵")
    c = make_person(conn, "張三", native_addr="江陵")
    assert a == b
    assert a != c


def test_find_person_by_name(conn):
    make_person(conn, "張三")
    make_person(conn, "李四")
    assert len(R.find_person_by_name(conn, "張三")) == 1
    assert R.find_person_by_name(conn, "王五") == []


# ---------------------------------------------------------------- 官职


def test_add_office_dedupes_same_name_and_department(conn):
    a = make_office(conn, "兵部尚書")
    b = make_office(conn, "兵部尚書")
    assert a == b


def test_office_tree_nests_child_under_parent(conn):
    parent = R.add_office(conn, R.Office(office_chn="兵部", department="兵部"))
    child = R.add_office(
        conn,
        R.Office(office_chn="兵部尚書", department="兵部", parent_office_id=parent),
    )
    tree = R.office_tree(conn)
    depths = {o.office_id: d for o, d in tree}
    assert depths[parent] == 0
    assert depths[child] == 1


# ---------------------------------------------------------------- 任职


def test_tenure_roundtrip_with_sources(conn):
    pid = make_person(conn)
    oid = make_office(conn)
    sid = R.add_source(conn, R.Source(source_name="张德信年表", citation="兵部尚书年表"))
    tid = R.add_tenure(
        conn,
        R.Tenure(
            person_id=pid, office_id=oid, start_year=1636, end_year=1641,
            tenure_type="实授", confidence=0.8,
        ),
        source_ids=[sid],
    )
    t = R.get_tenure(conn, tid)
    assert t is not None
    assert (t.start_year, t.end_year) == (1636, 1641)
    assert t.source_ids == [sid]


def test_tenure_type_is_constrained(conn):
    """任职类型受 CHECK 约束 —— 打错字不该静默入库。"""
    import sqlite3

    pid, oid = make_person(conn), make_office(conn)
    with pytest.raises(sqlite3.IntegrityError):
        R.add_tenure(
            conn, R.Tenure(person_id=pid, office_id=oid, tenure_type="随便写的")
        )


def test_tenure_rejects_reversed_years(conn):
    """起止年颠倒属录入错误。"""
    import sqlite3

    pid, oid = make_person(conn), make_office(conn)
    with pytest.raises(sqlite3.IntegrityError):
        R.add_tenure(
            conn, R.Tenure(person_id=pid, office_id=oid, start_year=1640, end_year=1630)
        )


def test_tenure_allows_open_ended_range(conn):
    """单边为 NULL 是合法的（在位中离任、或未载起始年）。"""
    pid, oid = make_person(conn), make_office(conn)
    a = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid, start_year=1640))
    b = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid, end_year=1640))
    assert R.get_tenure(conn, a).end_year is None
    assert R.get_tenure(conn, b).start_year is None


def test_confidence_is_constrained(conn):
    import sqlite3

    pid, oid = make_person(conn), make_office(conn)
    with pytest.raises(sqlite3.IntegrityError):
        R.add_tenure(
            conn, R.Tenure(person_id=pid, office_id=oid, confidence=1.5)
        )


def test_year_span_renders_unknown_as_question_mark(conn):
    """未载年份显示 `?`，不显示 0。"""
    assert R.Tenure(start_year=1636, end_year=1641).year_span == "1636–1641"
    assert R.Tenure(start_year=None, end_year=1641).year_span == "?–1641"
    assert R.Tenure().year_span == "?–?"


def test_tenure_requires_existing_person(conn):
    """外键必须生效 —— 悬空 person_id 会让查询悄悄少数据。"""
    import sqlite3

    oid = make_office(conn)
    with pytest.raises(sqlite3.IntegrityError):
        R.add_tenure(conn, R.Tenure(person_id=99999, office_id=oid))


# ---------------------------------------------------------------- 查询


def test_tenures_of_office_puts_unknown_years_last(conn):
    """起始年未载的记录排最后，不要冒到历任第一位把顺序打乱。"""
    oid = make_office(conn)
    known = R.add_tenure(
        conn, R.Tenure(person_id=make_person(conn, "甲"), office_id=oid, start_year=1630)
    )
    unknown = R.add_tenure(
        conn, R.Tenure(person_id=make_person(conn, "乙"), office_id=oid, start_year=None)
    )
    ids = [t.tenure_id for t in R.tenures_of_office(conn, oid)]
    assert ids == [known, unknown]


def test_tenures_of_office_rejects_bad_order(conn):
    with pytest.raises(ValueError):
        R.tenures_of_office(conn, 1, order="'; DROP TABLE tenure; --")


def test_snapshot_includes_open_ended_tenures(conn):
    """快照对 NULL 采取"宁可多列"策略：未载起始/离任年都视为可能在任。

    历史数据缺载是常态，漏掉一条比多列一条更难发现。
    """
    oid = make_office(conn)
    R.add_tenure(conn, R.Tenure(person_id=make_person(conn, "甲"), office_id=oid,
                                start_year=1630, end_year=1640))
    # 两头都未载 —— 应出现在任何年份的快照里
    R.add_tenure(conn, R.Tenure(person_id=make_person(conn, "乙"), office_id=oid))
    assert len(R.snapshot_at_year(conn, 1635)) == 2
    assert len(R.snapshot_at_year(conn, 1900)) == 1  # 只有那条未知的


def test_snapshot_excludes_out_of_range(conn):
    oid = make_office(conn)
    R.add_tenure(conn, R.Tenure(person_id=make_person(conn), office_id=oid,
                                start_year=1630, end_year=1640))
    assert R.snapshot_at_year(conn, 1629) == []
    assert R.snapshot_at_year(conn, 1641) == []
    assert len(R.snapshot_at_year(conn, 1630)) == 1   # 边界含
    assert len(R.snapshot_at_year(conn, 1640)) == 1


def test_tenures_of_person(conn):
    pid = make_person(conn)
    o1, o2 = make_office(conn, "兵部尚書"), make_office(conn, "禮部尚書")
    R.add_tenure(conn, R.Tenure(person_id=pid, office_id=o1, start_year=1640))
    R.add_tenure(conn, R.Tenure(person_id=pid, office_id=o2, start_year=1630))
    spans = [t.year_span for t in R.tenures_of_person(conn, pid)]
    assert spans[0].startswith("1630")   # 按起始年排序


# ---------------------------------------------------------------- 来源与异文


def test_add_source_dedupes(conn):
    a = R.add_source(conn, R.Source(source_name="明实录", citation="卷三百十四"))
    b = R.add_source(conn, R.Source(source_name="明实录", citation="卷三百十四"))
    assert a == b


def test_same_source_different_citation_not_deduped(conn):
    a = R.add_source(conn, R.Source(source_name="明实录", citation="卷三百十四"))
    b = R.add_source(conn, R.Source(source_name="明实录", citation="卷三百十五"))
    assert a != b


def test_link_source_is_idempotent(conn):
    tid = R.add_tenure(
        conn, R.Tenure(person_id=make_person(conn), office_id=make_office(conn))
    )
    sid = R.add_source(conn, R.Source(source_name="CBDB"))
    R.link_source(conn, tid, sid)
    R.link_source(conn, tid, sid)
    assert R.get_tenure(conn, tid).source_ids == [sid]


def test_tenure_can_have_multiple_sources(conn):
    """一条任职同时被多个来源记载 —— 本项目的核心数据形态。"""
    tid = R.add_tenure(
        conn, R.Tenure(person_id=make_person(conn), office_id=make_office(conn))
    )
    a = R.add_source(conn, R.Source(source_name="CBDB"))
    b = R.add_source(conn, R.Source(source_name="明实录"))
    R.link_source(conn, tid, a)
    R.link_source(conn, tid, b)
    assert sorted(R.get_tenure(conn, tid).source_ids) == sorted([a, b])


def test_discrepancy_lifecycle(conn):
    tid = R.add_tenure(
        conn, R.Tenure(person_id=make_person(conn), office_id=make_office(conn))
    )
    sa = R.add_source(conn, R.Source(source_name="CBDB"))
    sb = R.add_source(conn, R.Source(source_name="张德信年表"))
    did = R.add_discrepancy(
        conn,
        R.Discrepancy(
            tenure_id=tid, source_a=sa, source_b=sb, field="start_year",
            value_a="1636", value_b="1637",
        ),
    )
    assert len(R.list_discrepancies(conn, status="待校")) == 1
    R.resolve_discrepancy(conn, did, status="已校", note="以年表为准")
    assert R.list_discrepancies(conn, status="待校") == []
    assert len(R.list_discrepancies(conn, status="已校")) == 1


def test_discrepancy_status_is_constrained(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        R.add_discrepancy(conn, R.Discrepancy(field="start_year", status="瞎写"))


def test_discrepancy_requires_field(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        R.add_discrepancy(conn, R.Discrepancy(field=""))


# ---------------------------------------------------------------- 种子数据


@pytest.fixture
def seeded(tmp_path: Path):
    """跑一遍 CLI 的 seed 逻辑，得到可直接查询的库。"""
    path = D.init_db(tmp_path / "seeded.sqlite")
    c = D.connect(path)
    bingbu = R.add_office(c, S.office_bingbu())
    ss = S.office_bingbu_shangshu()
    ss.parent_office_id = bingbu
    ss_id = R.add_office(c, ss)
    src = R.add_source(c, S.SOURCE_ZHANGDEXIN)
    pids = [R.add_person(c, p) for p in S.persons()]
    for t in S.tenures(pids, ss_id):
        R.add_tenure(c, t, source_ids=[src])
    yield c
    c.close()


def test_seed_imports_all_minsters(seeded):
    assert D.count_rows(seeded)["tenure"] == len(S.CHONGZHEN_MINISTERS) == 14


def test_seed_marks_shen_yongmao_as_proxy(seeded):
    """申用懋是「署理」不是实授 —— PRD 明确要求区分，混同会让统计出错。"""
    office = seeded.execute(
        "SELECT office_id FROM office WHERE office_chn='兵部尚書'"
    ).fetchone()[0]
    rows = R.tenures_of_office(seeded, office)
    by_person = {}
    for t in rows:
        p = R.get_person(seeded, t.person_id)
        by_person[p.name_chn] = t
    assert by_person["申用懋"].tenure_type == "署理"
    assert by_person["楊嗣昌"].tenure_type == "实授"


def test_seed_confidence_is_not_certainty(seeded):
    """置信度不该是 1.0 —— 这批数据尚未与明实录逐条校勘。"""
    office = seeded.execute(
        "SELECT office_id FROM office WHERE office_chn='兵部尚書'"
    ).fetchone()[0]
    for t in R.tenures_of_office(seeded, office):
        assert t.confidence is not None
        assert 0.0 < t.confidence < 1.0


def test_seed_excludes_title_only_holders(seeded):
    """袁崇焕/孙传庭/卢象升是「兵部尚书衔」，不是京中兵部尚书。"""
    office = seeded.execute(
        "SELECT office_id FROM office WHERE office_chn='兵部尚書'"
    ).fetchone()[0]
    names = {
        R.get_person(seeded, t.person_id).name_chn
        for t in R.tenures_of_office(seeded, office)
    }
    for excluded in S.HOLDERS_OF_TITLE_ONLY:
        assert excluded not in names


def test_seed_every_tenure_has_a_source(seeded):
    """"可溯源"是本项目的卖点，种子数据必须先做到。"""
    office = seeded.execute(
        "SELECT office_id FROM office WHERE office_chn='兵部尚書'"
    ).fetchone()[0]
    for t in R.tenures_of_office(seeded, office):
        assert t.source_ids, f"{t.tenure_id} 没有来源"


def test_seed_chronological_order(seeded):
    """历任顺序应与 PRD 12.2 的清单一致。"""
    office = seeded.execute(
        "SELECT office_id FROM office WHERE office_chn='兵部尚書'"
    ).fetchone()[0]
    got = [
        R.get_person(seeded, t.person_id).name_chn
        for t in R.tenures_of_office(seeded, office)
    ]
    expected = [name for name, *_ in S.CHONGZHEN_MINISTERS]
    assert got == expected


def test_seed_snapshot_1629_shows_overlap(seeded):
    """1629 年是交接年：王洽、申用懋(署)、梁廷棟 都在任。"""
    assert len(R.snapshot_at_year(seeded, 1629)) == 3


def test_seed_is_additive_not_duplicating(tmp_path: Path):
    """重复 seed 完全幂等：人物/官职/来源/任职都不该翻倍。

    这条测试的由来：早期 `add_person` 只在给了 cbdb_id 时去重，而种子数据没有
    cbdb_id，于是重复 seed 把 14 人变 28 人、任职翻倍。现已按
    (姓名+籍贯) 与 (人+职+起止年+类型) 两处去重。
    """
    path = D.init_db(tmp_path / "s.sqlite")
    c = D.connect(path)
    try:
        def run_seed() -> None:
            bingbu = R.add_office(c, S.office_bingbu())
            ss = S.office_bingbu_shangshu()
            ss.parent_office_id = bingbu
            ss_id = R.add_office(c, ss)
            src = R.add_source(c, S.SOURCE_ZHANGDEXIN)
            pids = [R.add_person(c, p) for p in S.persons()]
            for t in S.tenures(pids, ss_id):
                R.add_tenure(c, t, source_ids=[src])

        run_seed()
        first = D.count_rows(c)
        run_seed()
        second = D.count_rows(c)
    finally:
        c.close()

    assert first["person"] == 14
    assert first["tenure"] == 14
    assert second == first, f"重复导入改变了计数: {first} → {second}"


def test_different_end_year_is_not_a_duplicate(conn):
    """期限不同的两任不是同一条 —— 去重不能粗到把连任抹平。"""
    pid, oid = make_person(conn), make_office(conn)
    a = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid,
                                    start_year=1630, end_year=1632))
    b = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid,
                                    start_year=1630, end_year=1635))
    assert a != b


def test_different_tenure_type_is_not_a_duplicate(conn):
    """同一人同一职的实授与加衔是两回事，不能合并。"""
    pid, oid = make_person(conn), make_office(conn)
    a = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid,
                                    start_year=1630, tenure_type="实授"))
    b = R.add_tenure(conn, R.Tenure(person_id=pid, office_id=oid,
                                    start_year=1630, tenure_type="加衔"))
    assert a != b


def test_add_person_dedupes_by_name_and_address(conn):
    """无 cbdb_id 时按姓名+籍贯去重；同名不同籍贯视为两人。"""
    a = make_person(conn, "張三", native_addr="武陵")
    b = make_person(conn, "張三", native_addr="武陵")
    c = make_person(conn, "張三", native_addr="江陵")
    assert a == b
    assert a != c


def test_tenures_rejects_mismatched_person_ids():
    with pytest.raises(ValueError, match="不匹配"):
        S.tenures([1, 2], 1)


def test_bingbu_aliases_include_core_terms():
    """雅称清单用于扩展明实录检索词，缺了会漏大量记载。"""
    for term in ("樞部", "本兵", "大司馬"):
        assert term in S.BINGBU_ALIASES
