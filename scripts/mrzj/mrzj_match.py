# -*- coding: utf-8 -*-
"""用《明人傳記資料索引》全文库核验 MingOff 的 CBDB 空档人物。

输入:
  _scratch/mineru_mrzj/corpus.json
  mingoff/src/mingoff/data/official_buyuan.json + official_cabinet.json
输出:
  _scratch/mineru_mrzj/mrzj_match_report.json
  _scratch/mineru_mrzj/mrzj_match_summary.md

判定:
  entry  —— 命中处形如「姓名（生卒）/字/號/，X人」，即条目开头（强）
  cited  —— 只在别人的出处行里出现（弱，不算本人条目）
  none   —— 全文无此名
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
MING = Path(r"C:\Users\31698\projects\guji-pipeline\mingoff\src\mingoff\data")
CJK = r"\u4e00-\u9fff"

HEAD_FOLLOW = re.compile(rf"^(?:[（(]\d{{3}}|字|號|初名|以字行|，[{CJK}]{{1,10}}人)")


def load_targets() -> list[dict]:
    out = []
    for fn, label in [("official_buyuan.json", "部院"), ("official_cabinet.json", "内阁")]:
        d = json.loads((MING / fn).read_text(encoding="utf-8"))
        by: dict[str, list] = {}
        for t in d["tenures"]:
            by.setdefault(t["person"], []).append(t)
        for name, ts in by.items():
            if any(t.get("cbdb_id") for t in ts):
                continue
            out.append(
                {
                    "name": name,
                    "source": label,
                    "offices": sorted({t.get("office", "") for t in ts if t.get("office")}),
                    "years": sorted({y for t in ts for y in (t.get("years") or [])}),
                }
            )
    return out


def scan(pages: list[dict], name: str) -> dict:
    """在全文中找 name，区分条目开头与出处引用。"""
    entries, cited = [], []
    for p in pages:
        t = p["text"]
        start = 0
        while True:
            i = t.find(name, start)
            if i < 0:
                break
            after = t[i + len(name) : i + len(name) + 12]
            before = t[max(0, i - 3) : i]
            if HEAD_FOLLOW.match(after):
                entries.append(
                    {"page": p["printed_page"], "snippet": t[max(0, i - 4) : i + 160]}
                )
            else:
                cited.append({"page": p["printed_page"], "before": before})
            start = i + len(name)
    return {"entries": entries, "cited_pages": sorted({c["page"] for c in cited})}


def main():
    pages = json.loads((BASE / "corpus.json").read_text(encoding="utf-8"))
    targets = load_targets()
    rows = []
    for tg in targets:
        r = scan(pages, tg["name"])
        status = "entry" if r["entries"] else ("cited" if r["cited_pages"] else "none")
        rows.append({**tg, "status": status, **r})
    (BASE / "mrzj_match_report.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    from collections import Counter

    c = Counter(r["status"] for r in rows)
    lines = [
        "# 《明人傳記資料索引》核验结果",
        "",
        f"目标：{len(rows)} 名 CBDB 空档人物（部院 + 内阁）",
        f"- 有条目（强证据）：**{c['entry']}**",
        f"- 仅被他人引用（弱）：{c['cited']}",
        f"- 全文未见：{c['none']}",
        "",
        "| 人物 | 来源 | 状态 | 索引页 | 摘要 |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["status"] != "entry", x["name"])):
        pg = r["entries"][0]["page"] if r["entries"] else (r["cited_pages"][0] if r["cited_pages"] else "")
        snip = (r["entries"][0]["snippet"] if r["entries"] else "").replace("|", "／")[:70]
        lines.append(f"| {r['name']} | {r['source']} | {r['status']} | {pg} | {snip} |")
    (BASE / "mrzj_match_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"目标 {len(rows)} 人：entry {c['entry']} / cited {c['cited']} / none {c['none']}")
    print("命中率（entry）：%.1f%%" % (c["entry"] / len(rows) * 100))
    for r in [x for x in rows if x["status"] == "entry"][:8]:
        print(f"  {r['name']} p{r['entries'][0]['page']} {r['entries'][0]['snippet'][:60]}")


if __name__ == "__main__":
    main()
