# -*- coding: utf-8 -*-
"""把《明人傳記資料索引》切成单页 PDF，供 MinerU 逐页识别。

为什么单页：实测 MinerU 会把连续多页并成一张 <table> 块，
table_body 全挂在第一页的 page_idx 上，页码归属全塌；
单页一文件后 page_idx 恒定 0，印刷页码由 page_number 块给出，1:1 可对。

用法: python mrzj_slice.py [起始PDF页] [结束PDF页]
默认切正文 PDF 26–989（正文 p1–964）+ 卷首 1–25 + 字号索引 990–1066。
"""
import sys
from pathlib import Path

import fitz as pymupdf

sys.stdout.reconfigure(encoding="utf-8")

SRC = Path(r"D:\大一學年\大一下课程\历史文献学\历史文献学作业\明人传记资料索引.pdf")
OUT = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj\pages")


def main():
    p0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    p1 = int(sys.argv[2]) if len(sys.argv) > 2 else 1066
    OUT.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(SRC)
    made = 0
    for p in range(p0, p1 + 1):
        dst = OUT / f"p{p:04d}.pdf"
        if dst.exists() and dst.stat().st_size > 1000:
            continue
        nd = pymupdf.open()
        nd.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
        nd.save(dst)
        nd.close()
        made += 1
    print(f"切片完成：新增 {made}，目录 {OUT}")


if __name__ == "__main__":
    main()
