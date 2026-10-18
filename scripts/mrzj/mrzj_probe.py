# -*- coding: utf-8 -*-
"""MinerU 429 探针：单文件提交一次，打印状态码与响应体（不打印密钥）。

用来区分「瞬时限流」与「日配额耗尽」——前者等几十秒可恢复，
后者响应体里通常带 quota / limit / 余额 字样。
"""
import json
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
BASE = "https://mineru.net/api/v4"
PDF = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj\pages\p0026.pdf")

payload = {
    "files": [{"name": PDF.name}],
    "model_version": "vlm",
    "enable_table": True,
    "language": "ch",
    "is_ocr": True,
}
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

wait = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if wait:
    print(f"等待 {wait}s 让限流窗口过去 …", flush=True)
    time.sleep(wait)

for attempt in range(1, 4):
    t0 = time.time()
    try:
        r = httpx.post(f"{BASE}/file-urls/batch", json=payload, headers=headers, timeout=40)
        print(f"[{attempt}] {r.status_code}  {time.time()-t0:.1f}s  {r.text[:400]}", flush=True)
        if r.status_code == 200:
            print("-> 可提交", flush=True)
            break
    except Exception as e:
        print(f"[{attempt}] EXC {type(e).__name__}: {str(e)[:200]}", flush=True)
    if attempt < 3:
        time.sleep(60)
