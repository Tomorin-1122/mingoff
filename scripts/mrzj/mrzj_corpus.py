# -*- coding: utf-8 -*-
"""把逐页 MinerU 产物合并成全文库（页码可回溯）。

输入: _scratch/mineru_mrzj/out/pNNNN.content_list.json
输出:
  _scratch/mineru_mrzj/corpus.json      [{pdf_page, printed_page, group, text}]
  _scratch/mineru_mrzj/mrzj_fulltext.txt 带页码标记的纯文本，便于 grep

页码口径：正文页 = PDF 页 − 25（manifest 实测偏移）；页脚 OCR 数字仅作旁证。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj\out")
CORPUS = OUT.parent / "corpus.json"
FULLTXT = OUT.parent / "mrzj_fulltext.txt"
OFFSET = 25

COMMA_FIX = re.compile(r"(?<=[\u4e00-\u9fff0-9）)]),(?=[\u4e00-\u9fff（(0-9])")


def page_text(md: str, blocks: list[dict]) -> tuple[str, str]:
    """正文取自 .md（表格页/纯文本页两种形态都已排好序），块结构只用来取姓目与页码。"""
    group = ""
    for b in blocks:
        if b.get("type") in ("text", "aside_text"):
            s = (b.get("text") or "").strip()
            if "劃" in s or s.startswith("【"):
                group = s
    txt = re.sub(r"<[^>]+>", "", md)
    txt = txt.replace("明人傳記資料索引", "")
    txt = re.sub(r"\n{2,}", "\n", txt).strip()
    # 去掉孤立的页脚数字行
    txt = re.sub(r"(?m)^\s*-?\d{1,3}\s*$", "", txt).strip()
    return COMMA_FIX.sub("，", txt), group


def main():
    pages = []
    for f in sorted(OUT.glob("p*.content_list.json")):
        pdfp = int(f.stem[1:5])
        blocks = json.loads(f.read_text(encoding="utf-8"))
        md_path = OUT / (f.name[:5] + ".md")
        md = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
        txt, group = page_text(md, blocks)
        printed = pdfp - OFFSET
        pages.append(
            {"pdf_page": pdfp, "printed_page": printed, "group": group, "text": txt}
        )
    CORPUS.write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    with FULLTXT.open("w", encoding="utf-8") as fh:
        for p in pages:
            fh.write(f"\n\n===== 正文 p{p['printed_page']} (PDF {p['pdf_page']}) {p['group']} =====\n")
            fh.write(p["text"])
    total = sum(len(p["text"]) for p in pages)
    empty = [p["printed_page"] for p in pages if len(p["text"]) < 50]
    print(f"页 {len(pages)}  字符 {total:,}  平均 {total/len(pages):.0f}/页")
    print(f"近空页（<50 字）: {empty}")
    print("->", CORPUS)
    print("->", FULLTXT)


if __name__ == "__main__":
    main()
