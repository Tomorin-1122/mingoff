# -*- coding: utf-8 -*-
"""实拍轮裁切：按 shipai_cases.json 的 box 渲染人名特写（zoom 4，含上下文带）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_scratch" / "shipai"
VOLS = {
    "总兵": Path(r"D:\北山研史\明代职官\明代职官年表_第3册_(张德信)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
    "布政使": Path(r"D:\北山研史\明代职官\明代职官年表_(第4册)_(张德信)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
}
CASES = [
    ("总兵", "顏彪", "石彪", 771), ("总兵", "阮興", "董興", 801),
    ("总兵", "緱謙", "朱謙", 793), ("总兵", "宗勝", "趙勝", 754),
    ("总兵", "薛永壽", "王永壽", 927), ("总兵", "殷體仁", "劉體仁", 941),
    ("总兵", "孫朝", "林朝", 860), ("总兵", "張萬邦", "王萬邦", 920),
    ("总兵", "胡承勛", "李承勛", 915), ("总兵", "高勛", "江勛", 939),
    ("布政使", "茹瑞", "王瑞", 27), ("布政使", "靳奎", "王奎", 10),
    ("布政使", "顏鈍", "王鈍", 22), ("布政使", "華昶", "陸昶", 179),
    ("布政使", "沈脩", "沈林", 322), ("布政使", "莊國楨", "楊國楨", 301),
]

def main():
    d = json.load(open("_scratch/shipai_cases.json", encoding="utf-8"))
    byname = {(c["tbl"], c["name"], c["pdf"]): c for c in d}
    OUT.mkdir(exist_ok=True)
    for tbl, name, fix, pdf in CASES:
        c = byname.get((tbl, name, pdf))
        if not c or not c.get("box"):
            print(f"skip {tbl} {name}")
            continue
        x0, y0, x1, y1 = (v / 3.0 for v in c["box"])   # paddle zoom3 → PDF 点坐标
        doc = fitz.open(VOLS[tbl])
        page = doc[pdf - 1]
        mat = fitz.Matrix(4, 4)
        clip = fitz.Rect(max(0, x0 - 15), max(0, y0 - 20),
                         min(page.rect.width, x1 + 60), min(page.rect.height, y1 + 25))
        pix = page.get_pixmap(matrix=mat, clip=clip)
        fp = OUT / f"{tbl}_{name}_{pdf}.png"
        pix.save(fp)
        print(fp.name, pix.width, pix.height)
        doc.close()

if __name__ == "__main__":
    main()
