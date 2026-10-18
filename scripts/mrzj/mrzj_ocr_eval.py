# -*- coding: utf-8 -*-
"""OCR 结果质量评估：用年号/官名/科举等"已知正确写法"做错字率代理指标。

用法: python mrzj_ocr_eval.py a.md b.md ...
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 规范词 → 常见误识变体（人工从三份输出里收集 + 预判）
TERMS = {
    "萬曆": ["萬層", "萬樑", "萬腾", "萬雁", "萬唇", "萬歷", "万曆"],
    "嘉靖": ["嘉请", "斑靖", "嘉蜻"],
    "崇禎": ["崇赬", "崇楨", "崇頎"],
    "進士": ["進上", "邁士", "通士", "進土"],
    "尚書": ["尚耆", "尚晝"],
    "致仕": ["致汁", "致让", "致任"],
    "都御史": ["都御吏"],
    "巡撫": ["巡橅"],
    "布政使": ["布政史"],
    "知縣": ["知具"],
}


def eval_file(path):
    t = Path(path).read_text(encoding="utf-8")
    canon_total = bad_total = 0
    rows = []
    for good, bads in TERMS.items():
        g = t.count(good)
        b = sum(t.count(x) for x in bads)
        canon_total += g
        bad_total += b
        rows.append((good, g, b))
    # 结构指标
    n_table = t.count("<table>")
    n_td = t.count("<td>")
    # 中文标点保留度：逗号/顿号是否被半角化
    cn_comma = t.count("，")
    hw_comma = t.count(",")
    dun = t.count("、")
    return {
        "file": Path(path).name,
        "chars": len(t),
        "tables": n_table,
        "td": n_td,
        "canon": canon_total,
        "bad": bad_total,
        "acc": canon_total / max(1, canon_total + bad_total),
        "cn_comma": cn_comma,
        "hw_comma": hw_comma,
        "dun": dun,
        "rows": rows,
    }


res = [eval_file(p) for p in sys.argv[1:]]
print(f"{'文件':<28}{'字符':>7}{'表':>4}{'格':>5}{'正确词':>7}{'错词':>6}{'准度':>8}{'，':>5}{',':>6}{'、':>5}")
for r in res:
    print(f"{r['file']:<28}{r['chars']:>7}{r['tables']:>4}{r['td']:>5}"
          f"{r['canon']:>7}{r['bad']:>6}{r['acc']*100:>7.1f}%"
          f"{r['cn_comma']:>5}{r['hw_comma']:>6}{r['dun']:>5}")

print()
for r in res:
    detail = " ".join(f"{g}={a}/错{b}" for g, a, b in r["rows"] if b)
    print(f"[{r['file']}] {detail}")
