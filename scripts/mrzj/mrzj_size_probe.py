# -*- coding: utf-8 -*-
"""MinerU 批大小探针：只做 /file-urls/batch 元数据请求，不上传文件。

用途：确认免费档一次批任务能放多少个文件。返回 200 即视为可放。
不打印密钥；若返回 200 也不上传，该任务会因缺文件自行失败，不消耗页数。
"""
import re
import sys
import time
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

txt = (Path.home() / "AppData/Local/Programs/mineru-local/mineru-local.py").read_text(
    encoding="utf-8"
)
TOKEN = re.search(r'SK_KEY\s*=\s*"([^"]+)"', txt).group(1)
PAGES = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj\pages")

for n in [int(x) for x in sys.argv[1:]] or [10]:
    files = sorted(PAGES.glob("p*.pdf"))[:n]
    payload = {
        "files": [{"name": f.name} for f in files],
        "model_version": "vlm",
        "enable_table": True,
        "language": "ch",
        "is_ocr": True,
    }
    r = httpx.post(
        "https://mineru.net/api/v4/file-urls/batch",
        json=payload,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        timeout=40,
    )
    print(f"n={n:>3}  {r.status_code}  {r.text[:160]}", flush=True)
    time.sleep(8)
