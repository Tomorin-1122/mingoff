# -*- coding: utf-8 -*-
"""《明人傳記資料索引》逐页 OCR 调度（可续跑、带配额错误识别）。

用法:
  python mrzj_batch.py 41 50          # 处理 PDF 页 41–50
  python mrzj_batch.py 41 50 --dry    # 只列计划
  python mrzj_batch.py --status       # 看已完成页

产物:
  _scratch/mineru_mrzj/out/p0042.md / p0042.content_list.json
  _scratch/mineru_mrzj/ocr_state.json   （已完成页 / 失败页 / batch_id，续跑依据）

纪律:
  - 单批 ≤200 页（MinerU 单任务上限），默认 50 页一批，便于观察配额；
  - 已完成的页直接跳过，失败页重试一次后进 failed 列表，不阻塞其余页；
  - 配额类错误（code 非 0 / 403 / 429）立刻停批并落盘，等次日或充值再续。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from mineru import MinerU

BASE = Path(r"C:\Users\31698\projects\guji-pipeline\_scratch\mineru_mrzj")
PAGES = BASE / "pages"
OUT = BASE / "out"
STATE = BASE / "ocr_state.json"
BATCH = 50

QUOTA_HINTS = ("quota", "limit", "exceed", "balance", "insufficient", "余额", "配额", "上限")


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": [], "failed": [], "batches": []}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def token() -> str:
    txt = (Path.home() / "AppData/Local/Programs/mineru-local/mineru-local.py").read_text(
        encoding="utf-8"
    )
    return re.search(r'SK_KEY\s*=\s*"([^"]+)"', txt).group(1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    st = load_state()
    if "--status" in sys.argv:
        print(f"完成 {len(st['done'])} 页；失败 {len(st['failed'])} 页；批次 {len(st['batches'])}")
        return

    p0, p1 = int(args[0]), int(args[1])
    todo = [
        PAGES / f"p{p:04d}.pdf"
        for p in range(p0, p1 + 1)
        if (PAGES / f"p{p:04d}.pdf").exists() and p not in st["done"]
    ]
    print(f"区间 {p0}-{p1}：待做 {len(todo)} 页（已跳过 {p1-p0+1-len(todo)} 页）")
    if "--dry" in sys.argv or not todo:
        return

    OUT.mkdir(parents=True, exist_ok=True)
    client = MinerU(token=token())
    t0 = time.time()
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        names = [str(p) for p in chunk]
        print(f"\n== 批次 {i//BATCH+1}：{len(chunk)} 页 ({chunk[0].stem}–{chunk[-1].stem})", flush=True)
        bid = None
        delay = 30
        for attempt in range(1, 7):
            try:
                bid = client.submit_batch(names, model="vlm", ocr=True, table=True, language="ch")
                break
            except Exception as e:
                msg = str(e)
                if "429" in msg and attempt < 6:
                    print(f"   429 限流，{delay}s 后重试（第 {attempt} 次）", flush=True)
                    time.sleep(delay)
                    delay = min(delay * 2, 300)
                    continue
                print("   提交失败:", f"{type(e).__name__}: {msg[:200]}", flush=True)
                break
        if not bid:
            save_state(st)
            break
        try:
            print("   batch_id:", bid, flush=True)
            st["batches"].append({"batch_id": bid, "pages": [p.stem for p in chunk]})
            save_state(st)
            results = client.get_batch(bid)
            # 轮询
            waited = 0
            while any(r.state not in ("done", "failed") for r in results):
                if waited > 1800:
                    print("   轮询超时，保留 batch_id 下次续", flush=True)
                    break
                time.sleep(10)
                waited += 10
                results = client.get_batch(bid)
            by_name = {r.filename: r for r in results if r.filename}
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print("   轮询失败:", msg[:300], flush=True)
            if any(h in msg.lower() for h in QUOTA_HINTS):
                print("   >>> 疑似配额/限额问题，停止批处理。", flush=True)
                save_state(st)
                break
            continue

        for path in chunk:
            stem = path.stem
            r = by_name.get(path.name)
            if r is not None and r.state == "done" and r.markdown:
                (OUT / f"{stem}.md").write_text(r.markdown, encoding="utf-8")
                (OUT / f"{stem}.content_list.json").write_text(
                    json.dumps(r.content_list or [], ensure_ascii=False, indent=1), encoding="utf-8"
                )
                st["done"].append(int(stem[1:]))
            else:
                state_txt = r.state if r else "missing"
                print(f"   失败 {stem}: {state_txt} {getattr(r,'err_code','')} {getattr(r,'error','')}",
                      flush=True)
                st["failed"].append({"page": stem, "state": state_txt})
        st["done"] = sorted(set(st["done"]))
        save_state(st)
        print(f"   累计完成 {len(st['done'])} 页，耗时 {time.time()-t0:.0f}s", flush=True)
        if i + BATCH < len(todo):
            time.sleep(20)  # 批次冷却，避开提交频率限制

    client.close()
    print(f"\n结束：完成 {len(st['done'])}，失败 {len(st['failed'])}")


if __name__ == "__main__":
    main()
