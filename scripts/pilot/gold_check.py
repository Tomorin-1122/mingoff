"""金标准校验：用 100% 可判的样本量模型打标准确率。

抽样设计（各 100 条，种子固定可复现）：
  GL_pos  正类：句首任免动词 + 官职（"陞某人為某職"/"陞+官职"）→ 必然是任职史料
  GL_neg  负类：无句首任免动词，且含「言/議/奏/疏/請」→ 必然是议政史料
  GL_edge 边界：非 R1，但含「加/兼/贈/賜/蔭/廕」→ 加衔/褒赠，属于哪类本身有争议，
               只统计不判对错
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.pilot.pilot_tag import Q, cred, rules  # noqa: E402

OUT = ROOT / "src/mingoff/data/pilot_gold_out.json"
N = 100


def tag(key, base, text):
    body = json.dumps({"model": "decision-model-preview", "state": text, "questions": Q},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/systemone", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))
            if not r.get("answers"):
                raise ValueError("empty answers")
            return r
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    key, base = cred()
    pool = json.load(open(ROOT / "src/mingoff/data/sinica_all.json", encoding="utf-8"))
    flat = [(n, r["content"], r["year"]) for n, v in pool.items() for r in v]
    pos, neg, edge = [], [], []
    for item in flat:
        ru = rules(item[1])
        if ru["R1_head_appoint"]:
            pos.append(item)
        elif any(k in item[1] for k in ("言", "議", "奏", "疏", "請")):
            neg.append(item)
        elif any(k in item[1] for k in ("加", "兼", "贈", "賜", "蔭", "廕", "晉", "進")):
            edge.append(item)
    random.seed(20261019)
    groups = {"GL_pos": random.sample(pos, N), "GL_neg": random.sample(neg, N),
              "GL_edge": random.sample(edge, N)}
    print(f"pool sizes: pos={len(pos)} neg={len(neg)} edge={len(edge)}")

    out = {"meta": {"n_per_group": N, "seed": 20261019}, "rows": []}
    tokens = 0
    t0 = time.time()
    for group, items in groups.items():
        for name, text, year in items:
            r = tag(key, base, text[:900])
            a = r["answers"]
            tokens += r["usage"]["input_tokens"]
            out["rows"].append({
                "group": group, "person": name, "year": year, "text": text[:200],
                "kind": a["kind"]["choice"], "kind_conf": a["kind"]["confidence"],
                "is_tenure": a["is_tenure"]["choice"], "leave": a["leave"]["choice"],
                "clarity": a["clarity"]["score"],
            })
        print(f"{group} done  tokens={tokens}  {time.time()-t0:.0f}s", flush=True)
    out["meta"]["tokens"] = tokens
    out["meta"]["seconds"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", OUT)


if __name__ == "__main__":
    main()
