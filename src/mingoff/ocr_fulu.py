# -*- coding: utf-8 -*-
"""册4 附錄解析（2026-10-22）。

附錄两部分（PDF 962–1177，正文 4139–4354）：
  一、收錄職官相關衙門沿革概述 —— 19 个机构章节（中书省…鄉試會試考官）
  二、人物小傳 —— 按拼音 A–Z 排列，一条一段

输入：_scratch/mineru_nianbiao/out/vol4_fulu_zhuan_a/b.md
输出：src/mingoff/data/vol4_fulu_zhuan.json（人物小传，含结构化字段）
      src/mingoff/data/vol4_fulu_yange.json（机构沿革，按章节）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_scratch" / "mineru_nianbiao" / "out"
OUT_Z = ROOT / "src" / "mingoff" / "data" / "vol4_fulu_zhuan.json"
OUT_Y = ROOT / "src" / "mingoff" / "data" / "vol4_fulu_yange.json"

ERA = "洪武|建文|永樂|洪熙|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|隆慶|萬曆|泰昌|天啟|崇禎"
RE_LIFE = re.compile(r"[（(]\s*(\d{3,4})\s*[—\-–一~至]\s*(\d{3,4})\s*[）)]")
RE_ZI = re.compile(r"字([\u4e00-\u9fff]{1,4})")
RE_HAO = re.compile(r"號([\u4e00-\u9fff]{1,8}?)(?:[，。；]|晚號)")
RE_JINSHI = re.compile(rf"({ERA})([元一二三四五六七八九十卅]+)年進士")
RE_NATIVE = re.compile(r"[，。]([\u4e00-\u9fff]{2,12}?)(?:人)[，。]")
RE_HEAD = re.compile(r"^([\u4e00-\u9fff]{2,4})")


def clean(p: str) -> str:
    return re.sub(r"\s*\n\s*", "", p).strip()


def parse_person(para: str, letter: str) -> dict | None:
    m = RE_HEAD.match(para)
    if not m:
        return None
    name = m.group(1)
    # 姓名后必须紧跟 （ 或 ，
    rest = para[m.end():m.end() + 1]
    if rest not in ("（", "(", "，"):
        return None
    life = RE_LIFE.search(para[:30])
    birth = death = None
    if life:
        birth, death = int(life.group(1)), int(life.group(2))
    else:
        # 只记卒年：「韓策（—1631）」
        m1 = re.search(r"[（(]\s*[—\-–]\s*(\d{3,4})\s*[）)]", para[:30])
        if m1:
            death = int(m1.group(1))
    zi = RE_ZI.search(para)
    hao = RE_HAO.search(para)
    js = RE_JINSHI.search(para)
    nat = RE_NATIVE.search(para)
    return {
        "name": name,
        "birth": birth,
        "death": death,
        "zi": zi.group(1) if zi else None,
        "hao": hao.group(1) if hao else None,
        "native": nat.group(1) if nat else ("不詳" if "不詳" in para[:40] else None),
        "jinshi": (js.group(1) + js.group(2) + "年") if js else None,
        "letter": letter,
        "text": para,
    }


def main() -> int:
    ta = (SRC / "vol4_fulu_zhuan_a.md").read_text(encoding="utf-8")
    tb = (SRC / "vol4_fulu_zhuan_b.md").read_text(encoding="utf-8")

    # ── 附錄一：衙门沿革 ──
    y0 = ta.find("# 收錄職官相關衙門沿革概述")
    y1 = ta.find("# 人物小傳")
    ytxt = ta[y0:y1]
    sections = []
    for m in re.finditer(r"^## (.+)$", ytxt, re.M):
        start = m.end()
        nxt = re.search(r"^## ", ytxt[start:], re.M)
        end = start + nxt.start() if nxt else len(ytxt)
        body = clean(ytxt[start:end])
        if body:
            sections.append({"office": m.group(1).strip(), "chars": len(body), "text": body})

    # ── 附錄二：人物小傳 ──
    pa = ta[y1:]
    # a 片末尾 + b 片开头拼接（b 片是跨页续排，首段没有姓名）
    joined = ta[y1:].rstrip() + "\n\n" + tb.lstrip()
    # 若 a 末段未以句号收尾，与 b 首段合并
    blocks = re.split(r"\n\s*\n", joined)
    blocks = [b for b in blocks if b.strip()]
    merged: list[str] = []
    for b in blocks:
        s = b.strip()
        if s.startswith("#") or s.startswith("!"):
            continue
        if merged and not re.search(r"[。」）]$", merged[-1]) and RE_HEAD.match(s) is None:
            merged[-1] = merged[-1].rstrip() + s
        else:
            merged.append(s)

    # 按字母标题标 record 所属首字母
    letters = [(m.start(), m.group(1)) for m in re.finditer(r"^## ?([A-Z0])$", joined, re.M)]
    def letter_at(pos: int) -> str:
        cur = ""
        for p, L in letters:
            if p <= pos:
                cur = "O" if L == "0" else L
            else:
                break
        return cur

    persons = []
    pos = 0
    for b in merged:
        idx = joined.find(b[:20], pos)
        pos = idx + 1 if idx >= 0 else pos
        rec = parse_person(clean(b), letter_at(idx if idx >= 0 else 0))
        if rec:
            persons.append(rec)

    letters_found = sorted({p["letter"] for p in persons if p["letter"]})
    payload = {
        "meta": {
            "dataset": "明代職官年表 册4 附錄",
            "source": "张德信《明代職官年表》册4 PDF 962–1177（正文 4139–4354）；MinerU OCR",
            "stats": {
                "persons": len(persons),
                "with_birth_death": sum(1 for p in persons if p["birth"] or p["death"]),
                "with_zi": sum(1 for p in persons if p["zi"]),
                "with_hao": sum(1 for p in persons if p["hao"]),
                "with_native": sum(1 for p in persons if p["native"]),
                "with_jinshi": sum(1 for p in persons if p["jinshi"]),
                "letters": "".join(letters_found),
                "yange_sections": len(sections),
            },
        },
        "persons": persons,
    }
    OUT_Z.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_Y.write_text(json.dumps({"sections": sections}, ensure_ascii=False, indent=1), encoding="utf-8")

    st = payload["meta"]["stats"]
    print(f"人物小传 {st['persons']} 条｜生卒 {st['with_birth_death']}｜字 {st['with_zi']}"
          f"｜号 {st['with_hao']}｜籍贯 {st['with_native']}｜进士 {st['with_jinshi']}")
    print(f"首字母覆盖 {st['letters']}")
    print(f"衙门沿革 {st['yange_sections']} 章：" + "、".join(s["office"] for s in sections[:8]) + " …")
    print(f"→ {OUT_Z}")
    print(f"→ {OUT_Y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
