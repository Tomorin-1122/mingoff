# -*- coding: utf-8 -*-
"""年表 OCR 调度：切片 → 提交 MinerU → 轮询落盘。

按表种切，不跨表种；单片 ≤200 页（MinerU 单任务上限）。
原始 md 只落 _scratch/mineru_nianbiao/，不入仓（规范 §3.3）。

用法：
  python scripts/mineru_nianbiao.py slice  zhongshu
  python scripts/mineru_nianbiao.py submit zhongshu
  python scripts/mineru_nianbiao.py poll   zhongshu
  python scripts/mineru_nianbiao.py status

依赖（本机系统 Python 3.14 已装）：PyMuPDF、mineru SDK。
token 从 mineru-local 配置读取，不打印、不落盘、不进仓。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import fitz

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "_scratch" / "mineru_nianbiao"
OUT = BASE / "out"
STATE = BASE / "state.json"

PDFS = {
    1: Path(r"D:\北山研史\明代职官\明代职官年表_第1册_(张德信著)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
    2: Path(r"D:\北山研史\明代职官\明代职官年表_第2册_(张德信著)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
    3: Path(r"D:\北山研史\明代职官\明代职官年表_第3册_(张德信)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
    4: Path(r"D:\北山研史\明代职官\明代职官年表_(第4册)_(张德信)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"),
}

# book = 正文起止页（原书页脚数字）；offset 为实测值，未实测的表种拒绝切片
TABLES = {
    "zhongshu":          dict(vol=1, name="中書省大臣年表",      book=(1, 14),    offset=15, calib="10-21 实测 p16扉页/p17=·2·/p29=·14·"),
    "shilang_jingshi":   dict(vol=1, name="部院侍郎年表(京師)",  book=(681, 980), offset=15, calib="册1 统一偏移（规范§2）"),
    "jingqing_jingshi":  dict(vol=1, name="京卿年表(京師)",      book=(981, 1266), offset=15, calib="册1 统一偏移（规范§2）"),
    # 册2-4：偏移仅据目录页起页推算，首次提交前须按规范§2 渲染页脚校准
    "kejishizhong":      dict(vol=2, name="六科都給事中年表",    book=(1267, 1520), offset=-1262, calib="11-04 实测 PDF5=六科扉页/PDF6=·1268·洪武廿六年/PDF259=部院南京扉页·1521"),
    "buyuan_nanjing":    dict(vol=2, name="部院大臣年表(南京)",  book=(1521, 1744), offset=-1262, calib=None),
    "shilang_nanjing":   dict(vol=2, name="部院侍郎年表(南京)",  book=(1745, 1970), offset=-1262, calib=None),
    "jingqing_nanjing":  dict(vol=2, name="京卿年表(南京)",      book=(1971, 2220), offset=-1262, calib=None),
    "dufu_jingying":     dict(vol=3, name="總督京營戎政大臣年表", book=(2221, 2318), offset=-2215, calib=None),
    "zongdu":            dict(vol=3, name="總督年表",            book=(2319, 2524), offset=-2215, calib=None),
    "xunfu":             dict(vol=3, name="巡撫年表",            book=(2525, 2922), offset=-2215, calib=None),
    "zongbing":          dict(vol=3, name="鎮守總兵官年表",      book=(2923, 3182), offset=-2215, calib=None),
    "buzheng":           dict(vol=4, name="承宣布政使年表",      book=(3183, 3570), offset=-3177, calib=None),
    "anchashi":          dict(vol=4, name="提刑按察使年表",      book=(3571, 3812), offset=-3177, calib=None),
    "tixue":             dict(vol=4, name="提學官年表",          book=(3813, 4008), offset=-3177, calib=None),
    "huishi":            dict(vol=4, name="會試考官年表",        book=(4009, 4098), offset=-3177, calib=None),
    "xiangshi":          dict(vol=4, name="鄉試考官年表",        book=(4099, 4139), offset=-3177, calib=None),
    # 附錄人物小傳：册4 PDF 962–1177（扉页+216页），正文页码 4139–4354
    "fulu_zhuan":        dict(vol=4, name="附錄·人物小傳",      book=(4139, 4354), offset=-3177,
                              calib="10-22 实测 PDF962=「附錄」扉页 / PDF1000=·4177· / PDF1100=·4277·"),
}

SLICE_MAX = 200


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"batches": [], "done": [], "failed": []}


def save_state(st: dict) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def meta_of(key: str) -> dict:
    if key not in TABLES:
        raise SystemExit(f"未知表种 {key}；可选：{', '.join(TABLES)}")
    return TABLES[key]


def pdf_range(m: dict) -> tuple[int, int]:
    """正文页区间 → PDF 页区间（1-based，含端点）。"""
    b0, b1 = m["book"]
    return b0 + m["offset"], b1 + m["offset"]


def token() -> str:
    p = Path.home() / "AppData/Local/Programs/mineru-local/mineru-local.py"
    return re.search(r'SK_KEY\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8")).group(1)


# ── slice ──
_KEY_RE = re.compile(r"[a-z_]{1,40}")


def cmd_slice(key: str) -> list[Path]:
    if not _KEY_RE.fullmatch(key):
        raise SystemExit(f"非法表种参数: {key!r}")
    m = meta_of(key)
    if not m["calib"]:
        raise SystemExit(f"{key} 偏移未实测（仅据目录推算），先按规范§2 校准页脚再切片。")
    src = PDFS[m["vol"]]
    if not src.exists():
        raise SystemExit(f"找不到原书 PDF：{src}")
    p0, p1 = pdf_range(m)
    doc = fitz.open(src)
    if p1 > doc.page_count:
        raise SystemExit(f"页码范围越界：{p1} > {doc.page_count}")
    BASE.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    # 按 200 页上限切，不跨表种
    for i, start in enumerate(range(p0, p1 + 1, SLICE_MAX)):
        end = min(start + SLICE_MAX - 1, p1)
        suffix = f"{chr(97 + i)}" if (p1 - p0 + 1) > SLICE_MAX else ""
        dst = BASE / f"vol{m['vol']}_{key}{('_' + suffix) if suffix else ''}.pdf"
        new = fitz.open()
        new.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
        new.save(dst, garbage=4, deflate=True)
        new.close()
        out.append(dst)
        print(f"切片 {dst.name}  PDF {start}-{end}（{end - start + 1} 页）{dst.stat().st_size / 1024 / 1024:.2f} MB")
    doc.close()
    return out


# ── submit ──
def cmd_submit(key: str) -> str | None:
    if not _KEY_RE.fullmatch(key):
        raise SystemExit(f"非法表种参数: {key!r}")
    st = load_state()
    for b in st["batches"]:
        if b.get("table") == key and b.get("batch_id"):
            print(f"{key} 已有 batch_id {b['batch_id']}（{b.get('submitted_at')}），跳过提交。")
            return b["batch_id"]
    slices = sorted(BASE.glob(f"vol{TABLES[key]['vol']}_{key}*.pdf"))
    if not slices:
        slices = cmd_slice(key)
    from mineru import MinerU

    client = MinerU(token=token())
    bid = client.submit_batch([str(p) for p in slices],
                              model="vlm", ocr=True, table=True, language="ch")
    st["batches"].append({
        "table": key, "batch_id": bid,
        "files": [p.name for p in slices],
        "pages": list(pdf_range(TABLES[key])),
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_state(st)
    print(f"已提交 {key}：batch_id = {bid}；文件 {[p.name for p in slices]}")
    return bid


# ── poll ──
def cmd_poll(key: str) -> None:
    st = load_state()
    item = next((b for b in st["batches"] if b.get("table") == key), None)
    if not item:
        raise SystemExit(f"{key} 尚无提交记录")
    from mineru import MinerU

    client = MinerU(token=token())
    OUT.mkdir(parents=True, exist_ok=True)
    for round_i in range(1, 121):  # 10s × 120 ≈ 20 分钟单次轮询上限
        res = client.get_batch(item["batch_id"])
        states = {r.filename: r.state for r in res}
        print(f"[{time.strftime('%H:%M:%S')}] {states}")
        if all(s in ("done", "failed") for s in states.values()):
            break
        time.sleep(10)
    ok = 0
    for r in res:
        if r.state == "done" and r.markdown:
            name = Path(r.filename).stem if r.filename else f"{key}_part{ok}"
            (OUT / f"{name}.md").write_text(r.markdown, encoding="utf-8")
            if r.content_list is not None:
                (OUT / f"{name}.content_list.json").write_text(
                    json.dumps(r.content_list, ensure_ascii=False, indent=1), encoding="utf-8")
            ok += 1
        elif r.state == "failed":
            st["failed"].append({"table": key, "file": r.filename})
    if ok and key not in st["done"]:
        st["done"].append(key)
    save_state(st)
    print(f"落盘 {ok} 个 md → {OUT}")


def cmd_status() -> None:
    st = load_state()
    print(f"已完成表种：{st['done'] or '无'}")
    print(f"失败：{st['failed'] or '无'}")
    for b in st["batches"]:
        print(f"  {b['table']:20s} {b['batch_id']}  {b.get('submitted_at','?')}  页 {b.get('pages')}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
        return 0
    if len(sys.argv) < 3:
        raise SystemExit("缺少表种参数")
    key = sys.argv[2]
    # key 是文件名组成部分：仅允许小写字母/下划线（TABLES 白名单二次校验在 meta_of）
    if not re.fullmatch(r"[a-z_]{1,40}", key):
        raise SystemExit(f"非法表种参数: {key!r}")
    key = sys.argv[2]
    if cmd == "slice":
        cmd_slice(key)
    elif cmd == "submit":
        cmd_submit(key)
    elif cmd == "poll":
        cmd_poll(key)
    else:
        raise SystemExit(f"未知命令 {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
