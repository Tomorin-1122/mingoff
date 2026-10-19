"""决策模型打标试点：用 choice（多选一+选项描述）对《明实录》条目打标。

规则对照（三条，全部是规则友好的）：
  R1 是否句首直接授官（"授/陞/改 + 人名 + 為 + 官职" 或 "陞 + 官职 + 人名"）
  R2 是否含离任动词（致仕/乞休/罷/削籍/奪職/卒/降級）
  R3 是否含议政动词（言/議/奏/言事/乞/請）
用法：
  python -m scripts.pilot_tag              # 抽样 500 条，跑打标
输出：src/mingoff/data/pilot_tag_out.json（不入库，试点产物）
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = Path.home() / ".qwen-mm-plugins" / "config"
OUT = ROOT / "src/mingoff/data/pilot_tag_out.json"
N = 500

# ---------------------------------------------------------------- 规则
# R1：不是"必须出现 為"——实录常见「陞倪元璐南京國子監司業」「陞+官职+人名」两种语序都不带"為"。
#     改为"动词 + 20 字内出现官职词"。
_OFFICE = ("國子監|詹事府|翰林院|春坊|寺|部|司|院|臺|府|衛|科|按察|布政|廵撫|巡撫|總督|給事中|中書|檢討|編修")
HEAD_APPOINT = re.compile(
    r"^[○\s]*(?:[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]日?[○\s]*)?"
    r"(?:授|陞|改|擢|遷|除|復除|起復|起用|補)[^，。；]{0,20}?(?:" + _OFFICE + ")")
LEAVE = re.compile("致仕|乞休|乞歸|請告|罷|削籍|奪職|卒|薨|降級|革職|免官|辭")
POLICY = re.compile("言|議|奏|乞|請|疏")


def rules(text: str) -> dict:
    head = bool(HEAD_APPOINT.match(text))
    return {
        "R1_head_appoint": int(head),
        "R2_leave": int(bool(LEAVE.search(text))),
        "R3_policy": int(bool(POLICY.search(text))),
    }


# ---------------------------------------------------------------- 模型
Q = {
    "kind": {
        "type": "choice",
        "instructions": "这段《明实录》文字的主要内容属于哪一类？",
        "criteria": {
            "授官": "原文出现「授某人某職」「陞某人為某職」「改某人為某職」「擢某人為某職」等直接任命表述",
            "离任": "原文记载某人致仕、乞休、被罢、被削籍、被降级或卒于任",
            "议政": "原文是臣僚就政事上疏、议论、举荐或请求，不直接给出任命",
            "行政": "原文记载钱粮、灾伤、工程、刑狱、礼仪等行政事务",
            "其他": "以上都不属于的杂项（册封、祭祀、军事调度、外交等）",
        },
    },
    "is_tenure": {
        "type": "choice",
        "instructions": "这段文字是否属于任职史料（可直接用于判断某人某年在任某职）？",
        "criteria": {
            "是": "原文直接给出某人获得了某个具体官职",
            "否": "原文没有直接给出某人获得具体官职",
        },
    },
    "leave": {
        "type": "choice",
        "instructions": "原文是否记载某人离职（致仕、罢免、削籍、降级、卒于任）？",
        "criteria": {"是": "有离职记载", "否": "没有离职记载"},
    },
    "clarity": {
        "type": "score",
        "instructions": "如果这是任职史料，任职信息有多明确？",
        "criteria": ["完全没有任职信息", "只能间接推断", "较为明确", "非常明确（有名有官）"],
    },
}


def cred():
    key = base = ""
    env_key = os.environ.get("DASHSCOPE_API_KEY")
    env_base = os.environ.get("DASHSCOPE_BASE_URL")
    if env_key and env_base:
        return env_key, env_base.rstrip("/")
    for line in CONF.read_text(encoding="utf-8").splitlines():
        if line.startswith("DASHSCOPE_API_KEY=") and not key:
            key = line.split("=", 1)[1].strip()
        if line.startswith("DASHSCOPE_BASE_URL=") and not base:
            base = line.split("=", 1)[1].strip().rstrip("/")
    return key, base


def tag(client_key, base_url, text):
    body = json.dumps({"model": "decision-model-preview", "state": text, "questions": Q},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base_url + "/systemone", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {client_key}",
                                          "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))
            if not r.get("answers"):
                raise ValueError("empty answers")
            return r
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    key, base = cred()
    pool = json.load(open(ROOT / "src/mingoff/data/sinica_all.json", encoding="utf-8"))
    flat = [(n, i, r) for n, v in pool.items() for i, r in enumerate(v)]
    random.seed(20261019)
    sample = random.sample(flat, N)

    out = {"meta": {"n": N, "model": "decision-model-preview", "seed": 20261019},
           "rows": []}
    tokens = 0
    t0 = time.time()
    for k, (name, i, rec) in enumerate(sample):
        r = tag(key, base, rec["content"][:900])
        a = r["answers"]
        tokens += r["usage"]["input_tokens"]
        out["rows"].append({
            "person": name, "year": rec["year"], "source": rec.get("source", ""),
            "text": rec["content"][:200],
            "rules": rules(rec["content"]),
            "kind": a["kind"]["choice"], "kind_conf": a["kind"]["confidence"],
            "is_tenure": a["is_tenure"]["choice"],
            "leave": a["leave"]["choice"],
            "clarity": a["clarity"]["score"],
        })
        if (k + 1) % 50 == 0:
            print(f"{k+1}/{N}  tokens={tokens}  elapsed={time.time()-t0:.0f}s", flush=True)
    out["meta"]["tokens"] = tokens
    out["meta"]["seconds"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {OUT}  tokens={tokens}  {out['meta']['seconds']}s")


if __name__ == "__main__":
    main()
