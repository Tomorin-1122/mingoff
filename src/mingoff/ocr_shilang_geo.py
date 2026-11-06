# -*- coding: utf-8 -*-
"""部院侍郎年表（京師）· 几何解析器（基于 PaddleOCR 行级 bbox）。

输入：_scratch/shilang/fixed/shilang_lines_canon.jsonl（renumber.py 产物，
      book=正文页码 681–980，phys=物理 PDF 页）
输出：src/mingoff/data/vol1_shilang_geo.json          条目
      src/mingoff/data/vol1_shilang_geo_pages.json   逐页摘要（年份/页型/标签/制度文）
      src/mingoff/data/vol1_shilang_geo_alarms.json  报警清单（人工回原书核）

版式规则（实测依据 docs/侍郎年表版式测绘.md + 2026-10-29 试点核对）：
  1. 页型 A（左页带标签列，约四成）/ B（对页无标签，借相邻 A 页格边界，相邻年格差 ≤3%）；
  2. 格边界 = 相邻标签中心的中点，y ≥ 边界归下一格；格高随年代变，不取全书定值；
  3. 每格 1–2 行人名（行 = 全页 y 带），行内 1–4 栏（栏距 ≥77px，栏内 ≤10px），
     同栏可并排两人（同年先后同职，如 1376 王鏞/周斌）；
  4. 人名 2–5 字 + 可带 (左)(右)(文)(試) 标记或 （…） 注；字高 ~29px，
     注文小字 ~20px，以字高 + 纯汉字判别；注文归「上方最近行带 + x 缩进最近人名」；
  5. 年份从「年号+序数（含廿/卅）」推算，与括号阿拉伯年交叉校验；
     正文页码 682–980 连续，年份必须单调不减，违者报警。
  6. B 页衙署序列借自格数相同的最近 A 页（B 与其对页 A 同属一个印刷拼版）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "_scratch/shilang/fixed/shilang_lines_canon.jsonl"
OUT_ENTRIES = ROOT / "src/mingoff/data/vol1_shilang_geo.json"
OUT_PAGES = ROOT / "src/mingoff/data/vol1_shilang_geo_pages.json"
OUT_ALARMS = ROOT / "src/mingoff/data/vol1_shilang_geo_alarms.json"

# ── 版式常量（实测，单位：OCR 坐标 px，页宽约 1068）──
HEADER_Y = 236        # 年份头区（y0 < HEADER_Y，x0 > 250）
LABEL_X1 = 200        # 标签区：x1 < 200
TOP_Y = 208           # 正文区上缘
FOOT_Y = 1258         # 页脚区上缘
NAME_H = 23.5         # 人名行最小字高
BAND_GAP = 25         # 行带切分（y0 间距）
COL_GAP = 50          # 栏切分（x0 - 前一名 x1）
NOTE_INDENT = 8       # 注文缩进下限（相对人名 x0）
INSTITUTION_LEN = 25  # 制度说明长文
MIN_LABELS_A = 5      # A 型页最少标签组

DEPTC = set("吏戶户禮體兵刑工都御史總糧倉場察院臺府中丞京儲易山廠提督部州")
SPINE = {"年", "官", "代", "職", "明代職官年表"}
OFFICE_TEXTS = {"吏部", "戶部", "户部", "禮部", "兵部", "刑部", "工部", "都察院",
                "御史臺", "御史府", "御史中丞", "御史臺御史中丞", "御史中丞御史臺",
                "易州山廠提督", "總糧儲", "總督倉場", "總倉場", "總督京儲"}
RE_TAG = re.compile(r"[（(]([左右文試])[）)]\s*$")
RE_PAREN = re.compile(r"[（(]([^（()）]{1,30})[）)]\s*$")
RE_CORE = re.compile(r"^[\u4e00-\u9fff]+$")
RE_ARABIC = re.compile(r"[（(](\d{3,4})[）)]")
RE_NOTE_START = re.compile(
    r"^(?:[（(][甲乙丙丁戊己庚辛壬癸]"
    r"|[正閏臘一二三四五六七八九十]{1,3}[、，]"
    r"|(?![\u4e00-\u9fff]{0,2}年)[一二三四五六七八九十廿卅]{1,3}年[正一二三四五六七八九十]{1,3}[月、，]"
    r"|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]年"
    r"|是年|是歲|本年|兼|後無考|無考|尋|未幾|卒|免|任[、，。]|贈|賜|復|起|降|謫|逮|下獄|丁內|丁外|丁憂"
    r"|服闋|服闕|服滿|乞|致仕|憂|奔喪|坐|謚|諡|殉|被執|被|死|革[職任為退民]|罷|削|奪|繫|論死|棄市)"
)
RE_FOOT = re.compile(r"^[·•・.]?\s*(\d{3})\s*[·•・.]?\s*$")

# ── 印刷横线检测（渲染页图 → 页眉/页脚文本块仿射标定 → OCR 坐标）──
# OCR 框坐标系与渲染图之间差一个仿射；横线是比标签中点准得多的格边界。
RULES_CACHE = ROOT / "_scratch/shilang/fixed/rules_cache.json"
PDF_PATH = Path(r"D:\北山研史\明代职官\明代职官年表_第1册_(张德信著)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf")
HDR_OCR_Y = 186.0        # 页头年份文本块中心（canon 实测 152–221）
FOOT_OCR_Y = 1340.0      # 页脚页码文本块中心（canon 实测 1329–1352）


def _rules_from_image(img, band_spans: list[tuple[int, int]]) -> tuple[list[float] | None, str]:
    """单页灰度图 + canon 行带跨度 → (OCR 坐标横线列表 | None, 失败原因)。

    配准：PaddleOCR 每页裁边不同，(sc, off) 必须逐页拟合——把 canon 行带
    投影到渲染图暗度剖面，网格搜索最大化带内墨量；再取「细而暗」的行块为横线。"""
    import numpy as np
    H = img.shape[0]
    prof = (img < 210).mean(axis=1).astype(np.float64)
    P = np.concatenate([[0.0], np.cumsum(prof)])

    def rmean(a: int, b: int) -> float:
        a = max(0, min(H - 1, int(a))); b = max(1, min(H, int(b)))
        return (P[b] - P[a]) / max(1, b - a)

    if len(band_spans) < 6:
        return None, "行带不足"
    bands = np.array(band_spans[:50], dtype=np.float64)
    best = (-1.0, 0.0, 0.0)
    for sc in np.arange(1.32, 1.62, 0.005):
        y0s = sc * bands[:, 0]
        hh = sc * (bands[:, 1] - bands[:, 0])
        for off in range(-160, 110, 3):
            a = y0s + off
            s = 0.0
            for k in range(len(bands)):
                s += rmean(a[k], a[k] + hh[k])
            if s > best[0]:
                best = (s, float(sc), float(off))
    _s, sc, off = best
    if sc <= 0:
        return None, "配准失败"

    # 细而暗的行块 = 横线
    frac = (img < 170).mean(axis=1)
    dark = np.where(frac > 0.02)[0]
    blocks: list[list[int]] = []
    for y in dark:
        if blocks and y - blocks[-1][-1] <= 5:
            blocks[-1].append(y)
        else:
            blocks.append([y])
    rules_img = [(b[0] + b[-1]) / 2 for b in blocks
                 if b[-1] - b[0] + 1 <= 9 and frac[b].max() >= 0.18]
    rules_ocr = sorted((r - off) / sc for r in rules_img)
    out: list[float] = []
    for r in rules_ocr:
        if out and r - out[-1] <= 6:
            continue
        if 130 <= r <= 1400:
            out.append(round(r, 1))
    if len(out) < 5:
        return None, f"横线过少（{len(out)}）"
    return out, ""


def lattice_bounds(rules: list[float], n_only: int | None = None) -> tuple[list[float] | None, int]:
    """格点重建：淡线漏检时按「格高近似均匀」补齐，但只容许补 1 条（格随内容增高，
    长缺口外推不可靠）。d = 单格间距中位数（gap ∈ [100,200]）；首条格线 a 在 180–300
    扫描寻优；n ∈ {7,8}（n_only 给定时只试该值）。检到的吸附（±12px），缺的合成。"""
    if len(rules) < 4 or rules[-1] < 1250:
        return None, 0
    gaps = [rules[i + 1] - rules[i] for i in range(len(rules) - 1)]
    inr = sorted(g for g in gaps if 100 <= g <= 200)
    if len(inr) < 2:
        return None, 0
    d = inr[len(inr) // 2]
    ns = (n_only,) if n_only in (7, 8) else (7, 8)
    best = None
    for n in ns:
        ba = None
        for a10 in range(1800, 3050, 5):
            a = a10 / 10
            # 格顶不可能落在底框区（>1250）；否则底框会冒充第 n 条格线
            score = sum(1 for j in range(n)
                        if a + j * d <= 1250
                        and min(abs(r - (a + j * d)) for r in rules) <= 12)
            if ba is None or score > ba[0]:
                ba = (score, a)
        if best is None or ba[0] > best[0]:
            best = (ba[0], n, ba[1])
    score, n, a = best
    if score < 3:
        return None, 0
    out, synth = [], 0
    for j in range(n):
        p_ = min(a + j * d, 1249.0)          # 末格格顶不允许越过底框区
        hit = min(rules, key=lambda r: abs(r - p_))
        if abs(hit - p_) <= 12:
            out.append(round(hit, 1))
        else:
            out.append(round(p_, 1))
            synth += 1
    if synth > 1:
        return None, 0
    return out, synth


def precompute_rules(books: list[int], band_spans: dict[int, list[tuple[int, int]]]
                     ) -> dict[int, list[float] | None]:
    """全量检测印刷横线（逐页配准），带磁盘缓存。"""
    cache: dict[str, list[float] | None] = {}
    if RULES_CACHE.exists():
        cache = json.loads(RULES_CACHE.read_text(encoding="utf-8"))
    todo = [b for b in books if str(b) not in cache and band_spans.get(b)]
    if todo:
        import fitz
        import numpy as np
        doc = fitz.open(PDF_PATH)
        for i, b in enumerate(todo):
            pix = doc.load_page(b + 15 - 1)          # 物理 PDF 页 = 正文 + 15
            z = 1600 / pix.rect.width
            pm = pix.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False, colorspace=fitz.csGRAY)
            img = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
            rules, _why = _rules_from_image(img, band_spans[b])
            cache[str(b)] = rules
            if (i + 1) % 50 == 0:
                print(f"  横线检测 {i + 1}/{len(todo)}…", flush=True)
        doc.close()
        RULES_CACHE.parent.mkdir(parents=True, exist_ok=True)
        RULES_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {int(k): v for k, v in cache.items()}


# 常见简体字（OCR 漏订正残留；命中即在 flags 记 simp:，回原书核）。
# 只收「简体独有形」，简繁同形字（盛/震/猛/黄/狧等）一律不收，防假阳性。
SIMP_CHARS = set(
    "万与门东两严为举义乐书买乱产仅从众优会伟传伤伪余俭债倾偿儿兰关兴养写"
    "军农冲决况冻净减凤凭凯击刘则刚创删剑剧劝办务动励劳势勋区医华协单卖卢"
    "卫厅历厉压厌县参双发变叙叠号员园围国图圆圣场坏块坚坛垦墙壮声壳处备复"
    "头夸夹夺奋奖妇妈婴孙学宁宝实宠审宪宽宾寻导寿将尔尘尝层属岁岛岭峡巩帘"
    "帜带帮并广庄庆庐库应庙庞废开异弃张弥弯弹强归当录彻忆忧怀态怜总恋恺恻"
    "恼悦悬悯惊惧惨惩惫惬惭惮惯愤愿慑懒戏战执扩扫扬扰抚护报担拟拢拣拥拦拧"
    "拨择挂挛挠挡挣挤挥捞损捡换掷揽摄摆摇摊攒敌敛数斋斗断无旧时旷昼显晋晕"
    "暂术朴机杀杂权条来杨极构枢枣柜栅标栈栋树档桥桦桩梦检榄榈槛横樱橱橹欢"
    "欧残殓殡毁毕毙饷粮仓厂贷铸铁锁键针钉钟钢钥链锋锐错锤锦锯镰门问闲间闷"
    "闻闸闹闺阔队阶阴陆陈阵险随隐难静顶项顺须顽顾顿预领颈频颓颜额风飘饭饮"
    "饲饰饱饶饼馆馒马驱驰驯驳驾骂骄验体点党齐齿龄龙龚龟还进远违连迟适选逊"
    "递逻遗邓邮邻郑释狱阕莱寻吴赈内饬许谢萧吕蒋赵猪冯钱银铜运边过这让议记"
    "训论设访诏试请诸调谕谨识询该误说谷窃笔笼筑简紧纠红纤约级纪纯纲纳纵纷"
    "纸线练组绅织细终绍经结给络绩统继续维绵编缘缓罚罢习联肃舰艰艺节苏荐荡"
    "荣获虏蛮补装见观规视")

ERAS = [("洪武", 1368), ("建文", 1399), ("永樂", 1403), ("洪熙", 1425),
        ("宣德", 1426), ("正統", 1436), ("景泰", 1450), ("天順", 1457),
        ("成化", 1465), ("弘治", 1488), ("正德", 1506), ("嘉靖", 1522),
        ("隆慶", 1567), ("萬曆", 1573), ("泰昌", 1620), ("天啟", 1621),
        ("崇禎", 1628)]

# 标签组文本 → 规范衙署（其余原样保留并报警）
OFFICE_NORM = {
    "吏部": "吏部", "戶部": "戶部", "户部": "戶部", "禮部": "禮部", "體部": "禮部",
    "兵部": "兵部", "刑部": "刑部", "工部": "工部", "都察院": "都察院",
    "御史臺": "御史臺", "御史府": "御史府", "御史中丞": "御史中丞",
    "御史臺御史中丞": "御史中丞", "御史中丞御史臺": "御史中丞",
    "易州山廠提督": "易州山廠提督", "提督": "易州山廠提督",
    "提督易州山廠": "易州山廠提督", "易州山廠": "易州山廠提督",
    "總糧儲": "總糧儲", "總督倉場": "總督倉場",
    "總倉場": "總倉場", "總督京儲": "總督京儲",
    "御史中丞御史府": "御史中丞", "御史府御史中丞": "御史中丞",
    "御史府中丞": "御史中丞",
}


def cnum(s: str) -> int:
    """中文序数 → 整数（支持 廿/卅）。"""
    s = s.replace("廿", "二十").replace("卅", "三十")
    if s == "元":
        return 1
    if "十" in s:
        a, _, b = s.partition("十")
        return (cnum(a) if a else 1) * 10 + (cnum(b) if b else 0)
    return "一二三四五六七八九".index(s) + 1


def load_canon() -> dict[int, list[dict]]:
    pages: dict[int, list[dict]] = {}
    for line in CANON.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["noise"] or not r["text_fix"].strip():
            continue
        pages.setdefault(r["book"], []).append(r)
    # 合并补丁行（patch_missing.py 产物：OCR 漏识别人名），
    # 且压制被补丁覆盖的残片行（补丁文本更长、或包含/包含于原行文本）
    patch = CANON.parent / "patch_lines.jsonl"
    n_patch = 0
    plines: list[dict] = []
    if patch.exists():
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.strip():
                plines.append(json.loads(line))
    if plines:
        for p in plines:
            pages.setdefault(p["book"], []).append({
                "book": p["book"], "phys": p["book"] + 15, "ocr": p["book"] + 14,
                "text": p["text"], "text_fix": p["text"], "box": p["box"],
                "score": p.get("score", 0.9), "noise": False,
            })
            n_patch += 1
        for b in {p["book"] for p in plines}:
            kept, dropped = [], 0
            for r in pages[b]:
                if r.get("noise") or not r["text_fix"].strip():
                    kept.append(r)
                    continue
                x0, y0 = r["box"][0], r["box"][1]
                hit = None
                for p in plines:
                    if p["book"] != b:
                        continue
                    if abs(p["box"][0] - x0) <= 40 and abs(p["box"][1] - y0) <= 18:
                        if len(p["text"]) > len(r["text_fix"].strip()) or r["text_fix"].strip() in p["text"]:
                            hit = p
                            break
                if hit is not None and len(r["text_fix"].strip()) < len(hit["text"]):
                    dropped += 1
                    continue
                kept.append(r)
            if dropped:
                pages[b] = kept
    if n_patch:
        print(f"合并补丁行 {n_patch} 条（patch_lines.jsonl）")
    return pages


def detect_year(page: list[dict]) -> tuple[int | None, str, str | None, list[str]]:
    """→ (year, 纪年显示, 年事件注, 问题列表)。只看页头区。"""
    heads = sorted((r for r in page if r["box"][1] < HEADER_Y and r["box"][0] > 250),
                   key=lambda r: r["box"][1])
    problems: list[str] = []
    year = era_year = arabic = None
    era_txt = ""
    for r in heads:
        t = r["text_fix"]
        m = RE_ARABIC.search(t)
        if m and arabic is None:
            arabic = int(m.group(1))
        for name, base in ERAS:
            mm = re.search(name + r"([元一二三四五六七八九十廿卅]{1,4})年", t)
            if mm:
                era_year = base + cnum(mm.group(1)) - 1
                era_txt = name + mm.group(1) + "年"
                break
        if era_year is not None:
            break
    if era_year is not None and arabic is not None and era_year != arabic:
        problems.append(f"年份冲突：纪年推 {era_year} vs 括号 {arabic}")
    year = era_year if era_year is not None else arabic
    if year is None and heads:
        problems.append("页头无纪年：" + " / ".join(r["text_fix"][:20] for r in heads))
    note = None
    if len(heads) > 1:                       # 年份头下的年事件注（如 1644 福王監國）
        note = " / ".join(r["text_fix"] for r in heads[1:] if len(r["text_fix"]) > 4)
    return year, era_txt, note, problems


def label_groups(page: list[dict]) -> list[dict]:
    """左栏标签 → 组（text, center）。竖排单字按 y 相接/重叠聚类。"""
    labs = [r for r in page
            if r["box"][2] < LABEL_X1 and r["box"][1] > 205
            and all(c in DEPTC for c in r["text_fix"])
            and r["text_fix"] not in SPINE
            and len(r["text_fix"]) <= 7]
    labs.sort(key=lambda r: (r["box"][1], r["box"][0]))
    groups: list[list[dict]] = []
    for r in labs:
        if groups:
            last = groups[-1][-1]
            if r["box"][1] - last["box"][3] <= 12 or (
                    r["box"][1] < last["box"][3] and r["box"][0] > last["box"][0] - 60):
                groups[-1].append(r)
                continue
        groups.append([r])
    out = []
    for g in groups:
        g.sort(key=lambda r: (r["box"][1], r["box"][0]))
        text = "".join(r["text_fix"] for r in g)
        center = sum((r["box"][1] + r["box"][3]) / 2 for r in g) / len(g)
        out.append({"text": text, "center": center})
    # 碎片标签（单字「部/院/臺/府」）并入前一組（相邻格标签中心距 ≥130，碎片距 <60）
    merged: list[dict] = []
    for grp in out:
        if (merged and grp["text"] in ("部", "院", "臺", "府", "中丞", "山廠")
                and grp["center"] - merged[-1]["center"] < 60):
            merged[-1]["text"] += grp["text"]
            continue
        merged.append(grp)
    return merged


def split_name_core(core: str, name_dict: set[str]) -> tuple[list[str], list[str]]:
    """连写人名切分：全部片段须在词典中。→ (parts, flags)"""
    if len(core) <= 3:
        return [core], []
    if len(core) == 4 and core[:2] in name_dict and core[2:] in name_dict:
        return [core[:2], core[2:]], ["split:" + core[:2] + "+" + core[2:]]
    if len(core) == 5:
        for a, b in ((2, 3), (3, 2)):
            if core[:a] in name_dict and core[a:] in name_dict:
                return [core[:a], core[a:]], ["split:" + core[:a] + "+" + core[a:]]
    if len(core) == 6 and core[:3] in name_dict and core[3:] in name_dict:
        return [core[:3], core[3:]], ["split:" + core[:3] + "+" + core[3:]]
    return [core], [f"long_name:{core}"]


def parse_page(page: list[dict]) -> dict:
    """标签检测与标签格顶边界（后备用）。格边界优先用印刷横线（rules）。

    口径统一：bounds = 各格「顶边 y」列表（len = 格数）。
    标签版：cell0 顶 = 205（表内容上缘），其余 = 相邻标签中心的中点。"""
    problems: list[str] = []
    groups = label_groups(page)
    if len(groups) in (7, 8):
        ptype = "A"
        mids = [(a["center"] + b["center"]) / 2 for a, b in zip(groups, groups[1:])]
        label_bounds = [205.0] + mids
    elif len(groups) >= 2:
        ptype = "W"
        label_bounds = None
        problems.append(f"标签组 {len(groups)}（应 7–8），借边界/衙署"
                        f"（{[g['text'] for g in groups]}）")
    else:
        ptype = "B"
        label_bounds = None
    return {"groups": groups, "ptype": ptype, "label_bounds": label_bounds,
            "problems": problems}


def classify(line: dict) -> str:
    """内容行分类：name / note / inst / office_stray。兜底归 note（靠 orphan 报警纠错）。
    人名测试须先排除 note-start（如「是年致仕」4 字纯汉字易误判为人名）。"""
    t = line["text_fix"].strip()
    h = line["box"][3] - line["box"][1]
    if len(t) > INSTITUTION_LEN:
        return "inst"
    core = RE_PAREN.sub("", RE_TAG.sub("", t))
    if core in OFFICE_TEXTS:
        return "office_stray"
    if (RE_CORE.fullmatch(core) and 2 <= len(core) <= 6 and h >= NAME_H
            and not RE_NOTE_START.match(t)):
        return "name"
    return "note"


def content_of(page: list[dict], ptype: str, name_dict: set[str]) -> tuple[list[dict], list[dict], list[str], list[str]]:
    """→ (name行, note行, 制度文, 疑行描述)。

    人名双通道：h≥23.5 直接入；h∈[21.5,23.5) 的纯汉字短行须
    在人名词典中、或 x0 与本页其他人名行对齐（列首）才认人名
    （如 1437 陳子琳 h=23）。"""
    x_min = LABEL_X1 if ptype in ("A", "W") else 92
    names, notes, others, insts = [], [], [], []
    pool = []
    for r in page:
        if r["box"][1] < TOP_Y or r["box"][0] < x_min:
            continue
        t = r["text_fix"].strip()
        if not t or (r["box"][1] > FOOT_Y and RE_FOOT.match(t)):
            continue
        k = classify(r)
        if k == "name":
            names.append(r)
        elif k == "note":
            pool.append(r)
        elif k == "inst":
            insts.append(t)
        else:
            others.append(f"游离衙署名 x{r['box'][0]} y{r['box'][1]} {t!r}")
    xs = [r["box"][0] for r in names]
    for r in pool:
        t = r["text_fix"].strip()
        h = r["box"][3] - r["box"][1]
        core = RE_PAREN.sub("", RE_TAG.sub("", t))
        if (21.5 <= h < NAME_H and RE_CORE.fullmatch(core) and 2 <= len(core) <= 5
                and not RE_NOTE_START.match(t)
                and (core in name_dict or any(abs(r["box"][0] - x) <= 8 for x in xs))):
            names.append(r)
        else:
            notes.append(r)
    return names, notes, insts, others


def name_bands(names: list[dict]) -> list[list[dict]]:
    names.sort(key=lambda r: r["box"][1])
    bands: list[list[dict]] = []
    for r in names:
        if bands and r["box"][1] - bands[-1][-1]["box"][1] <= BAND_GAP:
            bands[-1].append(r)
        else:
            bands.append([r])
    return bands


ROW1_OFF = 12        # 行带顶相对格顶的典型偏移
SLACK = 28           # 格归属允许越过边界的松弛
GAP_LO, GAP_HI = 30, 102  # 同格两行带顶间距可行域（实测 31–95）
ROW2_OFF = 68        # 同格两行典型间距
ROW2_COST = 6        # 第 2+ 行归属的固定代价（让位给恰在格顶的新格首行）
MAX_ROWS = 4         # 每格行数上限（洪武年都察院格实测有 4 行）


def assign_bands(bands: list[list[dict]], bounds: list[float]):
    """行带 → 格 的动态规划（软约束）。bounds = 各格顶边 y（len = 格数）。

    代价：
      - 新格首行：min(60, |带顶 − (格顶+ROW1_OFF)|)，越出 [格顶−SLACK, 格底+SLACK] 再罚 3/px；
      - 同格第 2..MAX_ROWS 行：ROW2_COST + |间距 − ROW2_OFF|，间距越出 [GAP_LO, GAP_HI] 再罚 3/px。
    返回 (每带格号, 每带行号, 告警列表)。"""
    n = len(bounds)
    rules = list(bounds)                         # rules[k] = 格 k 顶；末格底 = INF
    INF = float("inf")

    def bot(k: int) -> float:
        return rules[k + 1] if k + 1 < n else INF

    m = len(bands)
    ys = [min(r["box"][1] for r in b) for b in bands]
    # 状态 (k, r)：最后一带在格 k、该格已用 r 行；None = 尚未放带
    cur: dict[tuple[int, int] | None, tuple[float, int]] = {None: (0.0, -1)}
    parents: list[dict[tuple[int, int] | None, tuple[tuple[int, int] | None, int]]] = []
    for i, y in enumerate(ys):
        nxt: dict[tuple[int, int] | None, tuple[float, int]] = {}
        par: dict[tuple[int, int] | None, tuple[tuple[int, int] | None, int]] = {}
        for st, (c, _) in cur.items():
            # 同格第 2..MAX_ROWS 行
            if st is not None and 1 <= st[1] < MAX_ROWS:
                k2 = st[0]
                g = y - ys[i - 1]
                pen = 3 * max(0, GAP_LO - g) + 3 * max(0, g - GAP_HI)
                win = 3 * (max(0, rules[k2] - SLACK - y) + max(0, y - bot(k2) - SLACK))
                s2 = (k2, st[1] + 1)
                cost2 = c + ROW2_COST + abs(g - ROW2_OFF) + pen + win
                if s2 not in nxt or cost2 < nxt[s2][0]:
                    nxt[s2] = (cost2, i)
                    par[s2] = (st, i)
            # 新格首行（可跳过中间空格）
            kmin = 0 if st is None else st[0] + 1
            for k2 in range(kmin, n):
                cost = c + min(60.0, abs(y - (rules[k2] + ROW1_OFF)))
                cost += 3 * (max(0, rules[k2] - SLACK - y) + max(0, y - bot(k2) - SLACK))
                s2 = (k2, 1)
                if s2 not in nxt or cost < nxt[s2][0]:
                    nxt[s2] = (cost, i)
                    par[s2] = (st, i)
        if not nxt:                              # 状态空间枯竭（罕见）→ 强制并入末格
            best_st = min(cur, key=lambda s: cur[s][0])
            best_c = cur[best_st][0]
            nxt = {(n - 1, 1): (best_c + 200, i)}
            par = {(n - 1, 1): (best_st, i)}
        cur = nxt
        parents.append(par)
    end = min(cur, key=lambda s: cur[s][0])
    total = cur[end][0]
    assign, rowof = [0] * m, [1] * m
    st = end
    for i in range(m - 1, -1, -1):
        prev, _bi = parents[i][st]
        if st is not None:
            assign[i] = st[0]
            rowof[i] = st[1]
        st = prev
    alarms = []
    for i, y in enumerate(ys):
        k = assign[i]
        over = max(0, rules[k] - SLACK - y) + max(0, y - bot(k) - SLACK)
        if over > 10:
            alarms.append(f"行带 y{y} 距格{k} 边界越出 {int(over)}px")
    return assign, rowof, alarms, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", help="逗号分隔正文页码（试点）；缺省全量")
    ap.add_argument("--dump", action="store_true", help="打印逐页人读摘要")
    args = ap.parse_args()

    pages = load_canon()
    all_books = sorted(pages)
    if args.books:
        want = {int(x) for x in args.books.split(",")}
        books = [b for b in all_books if b in want]
    else:
        books = all_books
    # 表名页 681 不产出条目（仅年份/词典统计参与全量）
    books = [b for b in books if b >= 682]

    # ── 年份（全量做，保证单调校验与 B 页邻域完整）──
    year_of: dict[int, int | None] = {}
    era_of: dict[int, str] = {}
    ynote_of: dict[int, str] = {}
    year_problems: dict[int, list[str]] = {b: [] for b in all_books}
    for b in all_books:
        y, era, yn, probs = detect_year(pages[b])
        year_of[b], era_of[b], ynote_of[b] = y, era, yn
        year_problems[b] = probs
    for i, b in enumerate(all_books):
        if year_of[b] is None:
            prev = next((year_of[c] for c in all_books[i - 1::-1] if year_of[c] is not None), None)
            nxt = next((year_of[c] for c in all_books[i + 1:] if year_of[c] is not None), None)
            if prev is not None and nxt is not None and prev <= nxt:
                year_of[b] = prev
                year_problems[b].append(f"年份缺失，按邻页推断为 {prev}")
    for i in range(1, len(all_books)):
        a, b = all_books[i - 1], all_books[i]
        if year_of[a] is not None and year_of[b] is not None and year_of[b] < year_of[a]:
            year_problems[b].append(f"年份倒序：book{a}={year_of[a]} → book{b}={year_of[b]}")

    # ── 人名词典（连写切分用，全量统计）──
    freq: Counter = Counter()
    for page in pages.values():
        for r in page:
            if r["box"][2] < 205:                 # 标签列不入词典
                continue
            t = r["text_fix"].strip()
            core = RE_PAREN.sub("", RE_TAG.sub("", t))
            if (RE_CORE.fullmatch(core) and 2 <= len(core) <= 3
                    and r["box"][3] - r["box"][1] >= NAME_H and r["box"][1] >= TOP_Y):
                freq[core] += 1
    name_dict = {k for k, v in freq.items() if v >= 2}
    print(f"人名词典：{len(name_dict)} 名（出现≥2 次）")

    # ── 第一遍：逐页几何 ──
    geo: dict[int, dict] = {}
    for b in all_books:
        geo[b] = parse_page(pages[b])

    # ── 格边界：印刷横线 > 标签中点 > 借邻页 ──
    alarms: list[dict] = []
    # 行带跨度（供横线配准）：人名行带 + 页眉/页脚伪带
    band_spans: dict[int, list[tuple[int, int]]] = {}
    page_bands: dict[int, list[list[dict]]] = {}
    for b in all_books:
        g0 = geo[b]
        names0, _n0, _i0, _o0 = content_of(pages[b], g0["ptype"], name_dict)
        bds = name_bands(names0)
        page_bands[b] = bds
        g0["bands"] = bds
        g0["notes0"] = _n0
        g0["insts0"] = _i0
        g0["others0"] = _o0
        spans = [(min(m["box"][1] for m in bd), max(m["box"][3] for m in bd))
                 for bd in bds]
        spans += [(172, 198), (1329, 1352)]
        if spans:
            first = min(s[0] for s in spans)
            # 吏部首行上方的格顶粗线（强锚）置首并加权，防半周期错位
            spans = [(first - 16, first - 3)] * 5 + spans
        band_spans[b] = spans
    rules_of = precompute_rules(all_books, band_spans)

    def set_bounds(b: int) -> None:
        """自有源：标签中点优先（铅印实物、格格俱在、误差有界），
        无标签页才用横线格点（配准误差无界）。"""
        g = geo[b]
        if g["label_bounds"]:
            g["bounds"], g["bounds_src"] = g["label_bounds"], "labels"
            return
        rules = rules_of.get(b)
        if rules:
            if 1429 <= (year_of.get(b) or 0) <= 1529:
                n_hint = 8                     # 山厂期无标签页强制 8 格
            else:
                n_hint = None
            lat, synth = lattice_bounds(rules, n_hint)
            if lat:
                g["bounds"] = lat
                g["bounds_src"] = "rules" + (f"(+{synth}合成)" if synth else "")
                return

    def set_bounds_borrow(b: int) -> None:
        """第二遍：借邻页（插值 > 回退单侧 ≤3 页）。"""
        g = geo[b]
        if g.get("bounds") is not None:
            return
        lo = [c for c in all_books if c < b and geo[c].get("bounds") is not None]
        hi = [c for c in all_books if c > b and geo[c].get("bounds") is not None]
        pl, ph = (max(lo), min(hi)) if lo and hi else (None, None)
        detail = ""
        if pl is not None and ph is not None:
            la, lb = geo[pl]["bounds"], geo[ph]["bounds"]
            if la and lb and len(la) == len(lb):
                w = (b - pl) / (ph - pl)
                g["bounds"] = [x + (y - x) * w for x, y in zip(la, lb)]
                g["bounds_src"] = f"插值 book{pl}/book{ph}"
                return
            detail = f"插值失败（边界数不同 {len(la)}/{len(lb)}）；"
        for src in (pl, ph):
            if src is not None and abs(src - b) <= 3 and geo[src].get("bounds"):
                g["bounds"] = list(geo[src]["bounds"])
                g["bounds_src"] = (detail + f"回退借 book{src}").lstrip("；")
                return
        alarms.append({"book": b, "kind": "bounds",
                       "detail": (detail or "无可借边界") +
                                 (f"（自身标签 {[x['text'] for x in g['groups']]}）" if g["groups"] else "")})
        g["bounds"] = None

    for b in books:
        set_bounds(b)
    for b in books:
        set_bounds_borrow(b)

    # ── 第二遍：格（DP）、行带、栏、人名条目 ──
    results: dict[int, dict] = {}
    for b in books:
        g = geo[b]
        bounds = g["bounds"]
        page = pages[b]
        problems = list(g["problems"])
        if bounds is None:
            results[b] = None
            continue
        n_cells = len(bounds)
        offices: list[dict] | None = None
        if g["ptype"] == "A" and len(g["groups"]) == n_cells:
            offices = []
            for grp in g["groups"]:
                norm = OFFICE_NORM.get(grp["text"], grp["text"])
                if grp["text"] not in OFFICE_NORM:
                    problems.append(f"未知衙署标签「{grp['text']}」")
                offices.append({"office": norm, "raw": grp["text"]})
        elif len(g["groups"]) in (7, 8):
            problems.append(f"标签组 {len(g['groups'])} 与格数 {n_cells} 不符，衙署改借邻页")
        notes, insts = g["notes0"], g["insts0"]
        for o in g["others0"]:
            problems.append(f"未分类行 {o}")
        bands = g["bands"]
        band_cell, rowof, dp_alarms, _cost = assign_bands(bands, bounds)
        problems.extend(dp_alarms)
        per_cell: dict[int, list[int]] = {}
        for bi, ci in enumerate(band_cell):
            per_cell.setdefault(ci, []).append(bi)

        entries: list[dict] = []
        for ci in sorted(per_cell):
            for bi in per_cell[ci]:
                row = rowof[bi]
                band = sorted(bands[bi], key=lambda r: r["box"][0])
                slots: list[list[dict]] = []
                for r in band:
                    if slots and r["box"][0] - slots[-1][-1]["box"][2] <= COL_GAP:
                        slots[-1].append(r)
                    else:
                        slots.append([r])
                for col, slot in enumerate(slots, 1):
                    for r in slot:
                        t = r["text_fix"].strip()
                        tag = None
                        m = RE_TAG.search(t)
                        if m:
                            tag = m.group(1)
                            t = t[:m.start()].strip()
                        inline = None
                        m = RE_PAREN.search(t)
                        if m and len(m.group(1)) > 1:
                            inline = m.group(1)
                            t = t[:m.start()].strip()
                        parts, flags = split_name_core(RE_PAREN.sub("", t), name_dict)
                        if len(parts) == 1 and len(RE_PAREN.sub("", t)) > 5:
                            problems.append(f"超长人名行 x{r['box'][0]} y{r['box'][1]}：{t!r}")
                        if len(slot) > 1:
                            flags.append("pair_slot")
                        simp = sorted({ch for ch in t if ch in SIMP_CHARS})
                        if simp:
                            flags.append("simp:" + "".join(simp))
                        for p in parts:
                            entries.append({
                                "book": b, "year": year_of[b], "era": era_of.get(b),
                                "office": None, "office_raw": None, "cell": ci,
                                "row": row, "col": col, "person": p, "tag": tag,
                                "inline_note": inline, "notes": [],
                                "x": r["box"][0], "y": r["box"][1], "flags": flags,
                            })
        results[b] = {
            "book": b, "year": year_of[b], "ptype": g["ptype"], "bounds": bounds,
            "bounds_src": g.get("bounds_src"),
            "groups": g["groups"], "offices": offices, "n_cells": n_cells,
            "bands": bands, "band_cell": band_cell, "rowof": rowof, "notes": notes,
            "institutions": insts, "entries": entries, "problems": problems,
        }

    # ── B/W 页衙署：借格数相同的最近 A 页序列；W 页自有标签交叉核对 ──
    a_offices = {b: results[b]["offices"] for b in results
                 if results[b] and results[b]["offices"]}
    for b in books:
        res = results[b]
        if res is None or res["offices"] is not None:
            continue
        cand = [c for c in a_offices if len(a_offices[c]) == res["n_cells"]]
        if cand:
            src = min(cand, key=lambda c: abs(c - b))
            res["offices"] = [dict(o) for o in a_offices[src]]
            res["offices_src"] = src
            # 年代校验：8 格（易州山廠提督）仅许 1429–1529；7 格反之
            yr = res["year"]
            has_sl = any(o["office"] == "易州山廠提督" for o in res["offices"])
            if has_sl and not (1429 <= (yr or 0) <= 1529):
                alarms.append({"book": b, "kind": "office_seq_suspect",
                               "detail": f"年{yr} 借得 8 格序列（含山廠），越出 1429–1529"})
            if not has_sl and yr is not None and 1429 <= yr <= 1529:
                alarms.append({"book": b, "kind": "office_seq_suspect",
                               "detail": f"年{yr}（山厂期）借得 7 格序列"})
            # W 页：自有标签组应落进借来序列的对应格
            if res["ptype"] == "W" and res["groups"]:
                for grp in res["groups"]:
                    k = sum(1 for x in res["bounds"][1:] if grp["center"] >= x)
                    if k < len(res["offices"]):
                        got = res["offices"][k]["office"]
                        if grp["text"] not in got and got not in grp["text"] \
                           and OFFICE_NORM.get(grp["text"], grp["text"]) != got:
                            alarms.append({"book": b, "kind": "label_mismatch",
                                           "detail": f"标签「{grp['text']}」落格{k}，借得「{got}」"})
        else:
            alarms.append({"book": b, "kind": "office_seq",
                           "detail": f"无格数相同（{res['n_cells']}）的 A 页可借衙署序列"})

    # ── 注文归属：上方最近行带 + 带内 x 缩进最近人名 ──
    for b in books:
        res = results[b]
        if res is None:
            continue
        for r in sorted(res["notes"], key=lambda r: r["box"][1]):
            t = r["text_fix"].strip()
            y, x = r["box"][1], r["box"][0]
            # 向上找第一个含可行宿主（x 缩进匹配）的行带；跳带须打标
            host = None
            host_bi = None
            skipped = 0
            cand_bands = [(bi, band) for bi, band in enumerate(res["bands"])
                          if min(m["box"][1] for m in band) <= y]
            for bi, band in reversed(cand_bands):
                h2 = None
                for m in band:
                    if m["box"][1] <= y and x >= m["box"][0] + NOTE_INDENT:
                        if h2 is None or m["box"][0] > h2["box"][0]:
                            h2 = m
                if h2 is not None:
                    host, host_bi = h2, bi
                    break
                skipped += 1
            if host is None:
                alarms.append({"book": b, "kind": "orphan_note",
                               "detail": f"y{y} x{x} 无宿主 {t[:24]!r}"})
                continue
            if skipped:
                hits0 = [e for e in res["entries"]
                         if e["x"] == host["box"][0] and e["y"] == host["box"][1]]
                for e in hits0:
                    e["flags"].append(f"note_skip_band:{skipped}")
            hits = [e for e in res["entries"]
                    if e["x"] == host["box"][0] and e["y"] == host["box"][1]]
            if not hits:
                alarms.append({"book": b, "kind": "note_no_host",
                               "detail": f"y{y} x{x} {t[:24]!r}"})
                continue
            for e in hits:
                e["notes"].append(t)
                simp = "".join(sorted({ch for ch in t if ch in SIMP_CHARS}))
                if simp and f"simp:{simp}" not in e["flags"]:
                    e["flags"].append(f"simp:{simp}")
            if len(hits) > 1:
                for e in hits:
                    e["flags"].append("note_shared")
            ind = x - host["box"][0]
            if ind > 60:
                hits[0]["flags"].append(f"deep_indent:{ind}")

    # ── 深行疑似报警：行带排到 r≥3 且紧贴下一格顶（如 954 兵r1 被吞进禮r3）──
    for b in books:
        res = results[b]
        if res is None:
            continue
        bounds = res["bounds"]
        for bi, ci in enumerate(res["band_cell"]):
            if res["rowof"][bi] < 3 or ci + 1 >= len(bounds):
                continue
            band_y = min(m["box"][1] for m in res["bands"][bi])
            if band_y >= bounds[ci + 1] - 40:
                who = "、".join(sorted({e["person"] for e in res["entries"]
                                        if e["x"] in {m["box"][0] for m in res["bands"][bi]}
                                        and e["y"] in {m["box"][1] for m in res["bands"][bi]}}))
                alarms.append({"book": b, "kind": "deep_row_suspect",
                               "detail": f"{res['offices'][ci]['office'] if res['offices'] and ci < len(res['offices']) else ci}"
                                         f" r{res['rowof'][bi]} y{band_y} 距下格顶 {int(bounds[ci+1]-band_y)}px（{who[:30]}）"})

    # ── 输出装配 ──
    all_entries, page_sum = [], []
    for b in books:
        res = results[b]
        if res is None:
            alarms.append({"book": b, "kind": "page_failed", "detail": "边界不可得"})
            continue
        offices = res["offices"] or []
        for e in res["entries"]:
            o = offices[e["cell"]] if e["cell"] < len(offices) else None
            e["office"] = o["office"] if o else None
            e["office_raw"] = o["raw"] if o else None
            e.pop("cell", None)
        all_entries.extend(res["entries"])
        for p in res["problems"]:
            alarms.append({"book": b, "kind": "page", "detail": p})
        for p in year_problems.get(b, []):
            alarms.append({"book": b, "kind": "year", "detail": p})
        page_sum.append({
            "book": b, "phys": b + 15 if b >= 683 else (696 if b == 682 else 697),
            "year": res["year"], "era": era_of.get(b), "year_note": ynote_of.get(b),
            "ptype": res["ptype"],
            "labels": [{"text": g["text"], "norm": OFFICE_NORM.get(g["text"], g["text"]),
                        "center": round(g["center"])} for g in res["groups"]],
            "offices": [o["office"] for o in res["offices"] or []],
            "bounds_src": res.get("bounds_src"), "offices_src": res.get("offices_src"),
            "institutions": res["institutions"],
            "n_entries": len(res["entries"]), "n_problems": len(res["problems"]),
        })

    years = sorted({e["year"] for e in all_entries if e["year"] is not None})
    payload = {
        "meta": {
            "dataset": "部院侍郎年表（京師）· 几何解析",
            "source": "PaddleOCR PP-OCRv5 行级 bbox（正文页码坐标 681–980）",
            "note": "OCR页号=正文+14；物理PDF页=正文+15（正文682与表名页681例外）",
            "stats": {
                "pages": len(page_sum), "entries": len(all_entries),
                "years": len(years), "year_range": [years[0], years[-1]] if years else None,
                "persons": len({e["person"] for e in all_entries}),
                "with_note": sum(1 for e in all_entries if e["notes"] or e["inline_note"]),
                "alarms": len(alarms),
            },
        },
        "entries": all_entries,
    }
    OUT_ENTRIES.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_PAGES.write_text(json.dumps({"pages": page_sum}, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_ALARMS.write_text(json.dumps({"alarms": alarms}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload["meta"]["stats"], ensure_ascii=False))
    print(f"→ {OUT_ENTRIES}")

    if args.dump:
        for b in books:
            res = results.get(b)
            if res is None:
                print(f"\n===== book {b}: 解析失败（见 alarms）")
                continue
            ps = next((p for p in page_sum if p["book"] == b), None)
            print(f"\n===== book {b}  {ps['era'] or '?'}（{ps['year']}）  页型{res['ptype']}"
                  f"  标签{[l['text'] for l in res['groups']]}")
            if ps and ps["year_note"]:
                print(f"  年注: {ps['year_note']}")
            for inst in res["institutions"]:
                print(f"  [制度文] {inst[:50]}")
            for e in res["entries"]:
                tag = f"({e['tag']})" if e["tag"] else ""
                nl = "；".join(e["notes"]) if e["notes"] else ""
                il = f"〔{e['inline_note']}〕" if e["inline_note"] else ""
                fl = " ".join(e["flags"])
                print(f"  {e['office'] or '?':<7} r{e['row']}c{e['col']}  {e['person']}{tag}{il}"
                      f"{'  注:'+nl if nl else ''}{'  ⚠' + fl if fl else ''}")
            for p in res["problems"]:
                print(f"  ⚠ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
