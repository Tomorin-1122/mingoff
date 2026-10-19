"""全库打标：对《明实录》27,544 条逐条打 9 个标签，产出可筛选的 shilu_tags.json。

标签（一次请求 1 段文本 + 9 问，实测 16 问内成本几乎不变）：
  kind        choice 授官 / 离任 / 议政 / 行政 / 礼仪 / 其他
  is_tenure   choice 是 / 否 —— 可直接用于判断某人某年在任某职
  leave       choice 是 / 否 —— 记载离职（致仕/罢/削籍/降级/卒于任）
  ceremony    choice 是 / 否 —— 礼仪祭祀
  reward      choice 是 / 否 —— 加衔/褒赠/赐予/荫叙
  military    choice 是 / 否 —— 军事调度、战事、边备
  finance     choice 是 / 否 —— 钱粮、赋役、盐政、灾伤
  clarity     score 0-3 —— 任职信息明确度
  confidence  取 kind 的 confidence

用法：
  python scripts/pilot/tag_all.py                # 全库
  python scripts/pilot/tag_all.py --limit 200    # 小样试跑
  python scripts/pilot/tag_all.py --resume       # 断点续跑（跳过已有结果）
产出：src/mingoff/data/shilu_tags.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = Path.home() / ".qwen-mm-plugins" / "config"
OUT = ROOT / "src/mingoff/data/shilu_tags.json"
CKPT = ROOT / "src/mingoff/data/shilu_tags.ckpt.jsonl"

YN = {"是": "有此类记载", "否": "没有此类记载"}


def q_yn(ins):
    return {"type": "choice", "instructions": ins, "criteria": YN}


QUESTIONS = {
    "kind": {"type": "choice",
             "instructions": "这段《明实录》文字的主要内容属于哪一类？",
             "criteria": {
                 "授官": "出现「授/陞/改/擢/遷/除/補某人為某職」等直接任命表述",
                 "离任": "记载某人致仕、乞休、被罢、被削籍、被降级或卒于任",
                 "议政": "臣僚就政事上疏、议论、举荐或请求，不直接给出任命",
                 "行政": "钱粮、赋役、盐政、灾伤等政务记载",
                 "礼仪": "祭祀、典礼、册封、朝贡、赏赉等仪制事务",
                 "其他": "以上都不属于的杂项（军事调度、刑狱、工程、外交等）",
             }},
    "is_tenure": {"type": "choice",
                  "instructions": "这段文字是否可直接用于判断某人某年在任某职？",
                  "criteria": {"是": "直接给出某人获得某个具体官职",
                               "否": "没有直接给出某人获得具体官职"}},
    "leave": q_yn("原文是否记载某人离职（致仕、罢免、削籍、降级、卒于任）？"),
    "ceremony": q_yn("原文主要内容是否为礼仪祭祀（祭天、祭孔、册封、朝贡、典礼）？"),
    "reward": q_yn("原文是否记载加衔、褒赠、赐予、荫叙（加太子少保、贈謚、賜鈔、廕子等）？"),
    "military": q_yn("原文是否涉及军事（调兵、作战、边备、武职任命、粮饷调拨）？"),
    "finance": q_yn("原文是否涉及钱粮财政（赋役、盐政、税课、灾伤蠲免、仓廪）？"),
    "clarity": {"type": "score",
                "instructions": "如果涉及任职，任职信息有多明确？",
                "criteria": ["完全没有任职信息", "只能间接推断", "较为明确", "非常明确（有名有官）"]},
}


def cred():
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    base = os.environ.get("DASHSCOPE_BASE_URL", "")
    if key and base:
        return key, base.rstrip("/")
    for line in CONF.read_text(encoding="utf-8").splitlines():
        if line.startswith("DASHSCOPE_API_KEY=") and not key:
            key = line.split("=", 1)[1].strip()
        if line.startswith("DASHSCOPE_BASE_URL=") and not base:
            base = line.split("=", 1)[1].strip().rstrip("/")
    return key, base


def tag(key, base, text):
    body = json.dumps({"model": "decision-model-preview", "state": text, "questions": QUESTIONS},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/systemone", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))
            if len(r.get("answers") or {}) < 8:
                raise ValueError(f"answers 不全: {len(r.get('answers') or {})}")
            return r
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    key, base = cred()
    pool = json.load(open(ROOT / "src/mingoff/data/sinica_all.json", encoding="utf-8"))
    flat = [(n, i, r) for n, v in pool.items() for i, r in enumerate(v)]
    if args.limit:
        flat = flat[: args.limit]

    done = set()
    if args.resume and CKPT.exists():
        for line in CKPT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done.add((rec["person"], rec["idx"]))
        print(f"resume: {len(done)} 已存在")

    fh = CKPT.open("a", encoding="utf-8")
    tokens = 0
    t0 = time.time()
    n = 0
    for name, idx, rec in flat:
        if (name, idx) in done:
            continue
        r = tag(key, base, rec["content"][:900])
        a = r["answers"]
        tokens += r["usage"]["input_tokens"]
        row = {
            "person": name, "idx": idx, "year": rec.get("year"),
            "source": rec.get("source", ""), "text": rec["content"][:300],
            "kind": a["kind"]["choice"], "conf": round(a["kind"]["confidence"], 3),
            "is_tenure": a["is_tenure"]["choice"],
            "leave": a["leave"]["choice"],
            "ceremony": a["ceremony"]["choice"],
            "reward": a["reward"]["choice"],
            "military": a["military"]["choice"],
            "finance": a["finance"]["choice"],
            "clarity": round(a["clarity"]["score"], 2),
        }
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
        if n % 1000 == 0:
            fh.flush()
            el = time.time() - t0
            print(f"{n} 条  tokens={tokens}  {el:.0f}s  ~{n/el:.1f} 条/秒", flush=True)
    fh.close()

    rows = [json.loads(l) for l in CKPT.read_text(encoding="utf-8").splitlines() if l.strip()]
    OUT.write_text(json.dumps({"meta": {"n": len(rows), "model": "decision-model-preview",
                                        "questions": 9, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                               "rows": rows}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"done: {len(rows)} 条 -> {OUT}")


if __name__ == "__main__":
    main()
