# -*- coding: utf-8 -*-
"""人工校记回填：_proofread/notes（校对台导出）→ vol1_buyuan_entries_v3.json。

校记来源：老板 2026-10-22 → 11-04 人工校对部院大臣年表（京師）276/277 年
（缺 1418 未核），导出于 notes (4).json（export_at 2026-11-04T12:55Z）：
  patch 1,033（注文重抄 + 名/衙实质改 35）、add 257（補行）、remove 161（该衙该年无此人）、
  empty_offices 5（原书该衙该年整带无内容）、yearnotes 22（年度备注）。

匹配键 = (year, person, office)，同键多条按出现序消费（校对台行键
`year|office|person|n` 与 v2 条目序一致，实测 patch/remove 匹配率 100%）。

纪律：
  * 不改 raw_person/raw_office（OCR 原文保留）；patch 的 note 是老板重抄的原文，
    直接替换 note（校对台显示的即原 note，改动即有据）；
  * add 一律 src='book-patch' + book_page（page 字段 book-pXXX）；
  * 人名简体/异体（如 邓愈）保留校记原字，进 review 别名待归一清单，不擅改；
  * add 的 衙署=總倉場 等缩写形态：office 保留校记原字 + office_raw，规范 3.6-8
    衙署不合并，归一层（official_buyuan 的 office 字段直传）后续处理。

用法：PYTHONPATH=src python scripts/apply_proofread_notes.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
SRC_V2 = DATA / "vol1_buyuan_entries_v2.json"
OUT_V3 = DATA / "vol1_buyuan_entries_v3.json"
OUT_REVIEW = DATA / "vol1_buyuan_proofread_review.json"


def norm_note(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


NOTES_CANDIDATES = [
    ROOT / "_proofread" / "notes.json",
    Path(r"D:\浏览器下载\notes (4).json"),
]


def load_notes() -> dict:
    """候选文件按 meta.export_at 取最新（仓内旧快照 vs 浏览器下载新导出）。"""
    best = None
    for p in NOTES_CANDIDATES:
        if not p.is_file():
            continue
        obj = json.loads(p.read_text(encoding="utf-8"))
        at = str(obj.get("meta", {}).get("export_at", ""))
        if best is None or at > best[0]:
            best = (at, obj, p)
    if best is None:
        raise SystemExit(f"找不到校记文件：{NOTES_CANDIDATES}")
    print(f"校记文件：{best[2]}（export_at {best[0]}）")
    return best[1]


def main() -> int:
    notes = load_notes()
    ents = json.loads(SRC_V2.read_text(encoding="utf-8"))
    meta = notes["meta"]
    print(f"校记 {meta['export_at']}：{meta['years_done']}/{meta['years_total']} 年，"
          f"patch {len(notes['patch'])} / add {len(notes['add'])} / remove {len(notes['remove'])}")

    idx: dict[tuple, list[int]] = defaultdict(list)
    for i, e in enumerate(ents):
        idx[(e["year"], e["person"], e["office"])].append(i)
    consumed: set[int] = set()   # 被 patch 消费的条目（原地修改，保留在输出）
    removed_ids: set[int] = set()  # 被删除的条目
    log = {"patch_applied": 0, "patch_missed": [], "add": 0, "remove": 0,
           "remove_missed": [], "empty_dropped": [], "alias_todos": []}

    # ── patch ──
    for p in notes["patch"]:
        k = (p["year"], p["old_person"], p["old_office"])
        cand = [i for i in idx.get(k, []) if i not in consumed]
        if not cand:
            log["patch_missed"].append(k)
            continue
        i = cand[0]
        consumed.add(i)
        e = ents[i]
        e["person"] = p["person"]
        e["office"] = p["office"]
        # D-01 实体拆分后缀（王佐#1 等）必须保留，否则跨代同名被合并成单实体
        suffix = ""
        old_pid = e.get("person_id") or ""
        if "#" in old_pid:
            suffix = "#" + old_pid.split("#", 1)[1]
        e["person_id"] = p["person"] + suffix
        e["person_label"] = p["person"]
        e["note"] = p["note"]
        e["pf"] = "patch"
        log["patch_applied"] += 1

    # ── remove ──
    for r in notes["remove"]:
        k = (r["year"], r["person"], r["office"])
        cand = [i for i in idx.get(k, []) if i not in consumed and i not in removed_ids]
        if not cand:
            log["remove_missed"].append(k)
            continue
        removed_ids.add(cand[0])
        log["remove"] += 1

    # ── empty_offices：该年该衙整带剔除 ──
    for eo in notes["empty_offices"]:
        for i, e in enumerate(ents):
            if e["year"] == eo["year"] and e["office"] == eo["office"] \
                    and i not in consumed and i not in removed_ids:
                removed_ids.add(i)
                log["empty_dropped"].append((eo["year"], eo["office"], e["person"]))

    # ── add：補行 ──
    # 同名已有实体（D-01 拆分的 王#1/#2）：按年份归组，避免补行再造出第三个实体
    ent_span: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for e in ents:
        if i := e.get("year"):
            pid = e.get("person_id") or e["person"]
            lo, hi = ent_span[e["person"]].get(pid, (9999, 0))
            ent_span[e["person"]][pid] = (min(lo, i), max(hi, i))

    def pid_for_add(name: str, year: int) -> str:
        cands = ent_span.get(name) or {}
        if not cands or len(cands) == 1 and name in cands:
            return name
        if len(cands) == 1:
            return next(iter(cands))
        for pid, (lo, hi) in cands.items():
            if lo <= year <= hi:
                return pid
        # 年份不相交 → 取起点最近的
        return min(cands, key=lambda pid: abs(cands[pid][0] - year))

    adds = []
    for a in notes["add"]:
        m = re.search(r"book-p(\d+)", a.get("page") or "")
        adds.append({
            "year": a["year"],
            "office": a["office"],
            "person": a["person"],
            "note": a.get("note", ""),
            "raw_person": a["person"],
            "raw_office": a["office"],
            "src": "book-patch",
            "flag": None,
            "person_id": pid_for_add(a["person"], a["year"]),
            "person_label": a["person"],
            "book_page": int(m.group(1)) if m else None,
            "pf": "add",
        })
        log["add"] += 1
        # 别名待归一：简体/异体提示（仅记录，不改字）
        if re.search(r"[邓刘冲赵凯万户]", a["person"]):
            log["alias_todos"].append({"year": a["year"], "person": a["person"],
                                       "office": a["office"]})

    out = [e for i, e in enumerate(ents) if i not in removed_ids] + adds
    out.sort(key=lambda e: (e["year"], 0 if e.get("src") != "book-patch" else 1))
    OUT_V3.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # yearnotes 原样并入 review（年度备注供下游 G5/校勘参考）
    review = {
        "meta": {"source": str(NOTES_CANDIDATES), "export_at": meta["export_at"],
                 "years_done": meta["years_done"], "missing_years":
                     [y for y in range(1368, 1645) if y not in set(meta["done_years"])]},
        "stats": {k: v for k, v in log.items() if k != "alias_todos"} |
                 {"alias_todos": log["alias_todos"]},
        "yearnotes": notes.get("yearnotes", {}),
    }
    OUT_REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"回填 → {OUT_V3.name}：条目 {len(ents)} → {len(out)}")
    print(f"patch 应用 {log['patch_applied']}（未匹配 {len(log['patch_missed'])}）；"
          f"add {log['add']}；remove {log['remove']}（未匹配 {len(log['remove_missed'])}）；"
          f"empty 整带剔除 {len(log['empty_dropped'])}")
    for k in log["patch_missed"][:5]:
        print("  ⚠ patch 未匹配:", k)
    for k in log["remove_missed"][:5]:
        print("  ⚠ remove 未匹配:", k)
    for k in log["empty_dropped"]:
        print("  ⚠ empty 剔除:", k)
    for a in log["alias_todos"][:8]:
        print("  ℎ 别名待归一:", a)
    print(f"→ {OUT_REVIEW.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
