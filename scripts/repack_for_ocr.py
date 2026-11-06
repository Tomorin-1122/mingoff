# -*- coding: utf-8 -*-
"""把 PDF 页面重渲染成标准灰度 JPEG 并重新打包，供 MinerU 使用。

背景：册4 原扫描件是 Indexed 调色板 + 4bit 色深（FlateDecode），MinerU 报
"unsupported file type"；册1 是 CCITTFax 黑白，正常。重渲染后色彩空间变为
标准 DeviceGray，服务端即可识别。

用法：python scripts/repack_for_ocr.py <源PDF> <起页> <止页> <输出PDF> [dpi]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import fitz


def repack(src: Path, p0: int, p1: int, dst: Path, dpi: int = 200) -> None:
    doc = fitz.open(src)
    out = fitz.open()
    zoom = dpi / 72.0
    for i in range(p0 - 1, min(p1, doc.page_count)):
        page = doc[i]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False)
        jpg = pix.tobytes("jpeg", jpg_quality=78)
        np = out.new_page(width=page.rect.width, height=page.rect.height)
        np.insert_image(np.rect, stream=jpg)
    out.save(dst, garbage=4, deflate=True)
    out.close()
    doc.close()
    print(f"{dst.name}  {p0}-{p1}  {dst.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    repack(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]),
           int(sys.argv[5]) if len(sys.argv) > 5 else 200)
