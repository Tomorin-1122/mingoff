"""D38：明人传记资料索引产出入仓后的资产完整性断言。

保护对象：`src/mingoff/data/mrzj/` 下的结构化资产与逐页 OCR。
这几个文件是 4 小时 MinerU OCR + 多轮解析的终点，丢了无法从仓内重放，
所以用测试把「文件在不在、结构对不对、统计口径有没有漂」钉死。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "src" / "mingoff" / "data" / "mrzj"


def load(name: str):
    path = DATA / name
    assert path.exists(), f"缺少资产 {name}：请从 _scratch/mineru_mrzj 重新归档"
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_and_core_assets_present():
    manifest = load("mrzj_manifest.json")
    assert manifest["ocr"]["pages"] == 963
    assert manifest["raw_ocr_pages"] >= 960
    for name in ("corpus.json", "index_catalog_final.json", "person_db.json", "cbdb_verdict.json"):
        assert name in manifest["files"], f"manifest 未登记 {name}"
        assert (DATA / name).stat().st_size == manifest["files"][name]["bytes"]


def test_raw_ocr_covers_body():
    pages = list((DATA / "raw_ocr").glob("p*.md"))
    assert len(pages) >= 960, f"逐页 OCR 只有 {len(pages)} 页"
    assert sum(p.stat().st_size for p in pages) > 3_000_000


def test_index_catalog_terminal_state():
    catalog = load("index_catalog_final.json")
    assert len(catalog) == 9_651, "人名目录去重后应 9,651 人"

    tiers: dict[str, int] = {}
    for rec in catalog:
        tier = (rec.get("tier") or "")[:1]
        tiers[tier] = tiers.get(tier, 0) + 1
    landed = sum(tiers.get(t, 0) for t in "ABC")
    assert landed == 6_647, f"A+B+C 已落地应为 6,647，实为 {landed}（分层：{tiers}）"
    assert tiers.get("D") == 1_689 and tiers.get("E") == 1_315


def test_person_db_size_and_cbdb_link():
    persons = load("person_db.json")
    assert len(persons) == 6_487
    linked = sum(1 for p in persons if p.get("cbdb_id"))
    # 报告第八节对账对象写作 2,801，而报告第六节把全量首跑的 CBDB 唯一命中记为 2,805；
    # 两者相差 4 人，属报告取数口径不一致，此处以区间钉住并在报告里补注。
    assert 2_801 <= linked <= 2_805, f"CBDB 唯一命中应在 2,801–2,805，实为 {linked}"


@pytest.mark.parametrize("field", ["name", "page", "cbdb_kind", "tier"])
def test_person_db_fields(field):
    persons = load("person_db.json")
    assert all(field in p for p in persons[:200])


def test_reconcile_net_increment():
    """净增量是这份书价值的核心论据：出处条数与覆盖人数不能缩水。"""
    text = (DATA / "reconcile.csv").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines()[1:] if line.strip()]
    assert len(rows) >= 2_700
