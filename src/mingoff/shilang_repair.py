# -*- coding: utf-8 -*-
"""侍郎年表 book-patch：原书核验修正（2026-11-08，正字/核验轮）。

背景：几何解析对 103 个「行带警报页」存在三类已证实的错挂——
  A. 兵部带首行被吸进前一衙的 r3（954/800 两例同构，相距百余年）；
  B. 易州山廠带被吸进前一衙的 r3（760 陳恭 / 800 萬祺·談倫）；
  C. 整页部界级联错移（760：自戶部以下逐衙错一格）。
每处均以原书页图（D:\\北山研史\\明代职官\\第1册，物理页=正文+15）逐行核对后定案；
渲染件 _scratch/shilang/verify/bookNNN.png，报告 docs/侍郎表接入报告.md。

格式：BOOK_FIX[book页] = [(old_office, old_row, col, person) → (new_office, new_row), ...]
col 为 None 时匹配该 (office,row) 全部条目。未列出的警报页保持 pending（待校对台），
数据不删，站点灰显。
"""

BOOK_FIX: dict[int, list[dict]] = {
    # ── 954（天啟六年 1626）：兵部两行带整体错位——真 r1 被吸进禮部 r3，
    #    geo 的兵部 r1 实为书页第二行。注文明示：郭允厚「兵右侍遷添設」、
    #    劉遵憲「遷兵尚仍管左侍事」、袁可立「右侍遷」皆兵部职语。
    954: [
        {"from": ("禮部", 3), "col": None, "to": ("兵部", 1)},
        {"from": ("兵部", 1), "col": None, "to": ("兵部", 2)},
        # 朱一桂：书页刑部带第二行右列（閏六…太常卿遷）——geo 拆到 r3，归回 r2
        {"from": ("刑部", 3), "col": None, "to": ("刑部", 2)},
    ],
    # ── 800（成化二十年 1484）：同 A 型——geo 禮部 r3（俞欽卒/阮勤右侍遷）= 书页
    #    兵部第一行；geo 兵部 r1（阮勤遷左/萬翼/侯瓚）= 书页兵部第二行；
    #    geo 工部 r3（萬祺卒/談倫順天尹遷工右侍）= 书页易州山廠带。
    800: [
        {"from": ("禮部", 3), "col": None, "to": ("兵部", 1)},
        {"from": ("兵部", 1), "col": None, "to": ("兵部", 2)},
        {"from": ("工部", 3), "col": None, "to": ("易州山廠提督", 1)},
    ],
    # ── 760（正統十年 1445）：C 型整页级联错移——自戶部以下逐衙错一格。
    #    书页：吏部 李教/趙新·曹義｜戶部 李暹·姜濤/焦宏·張睿·儲懋｜禮部 王英·侯璉/錢習禮｜
    #    兵部 鄺埜/虞祥·李蕡｜刑部 薛希璉·馬昂·丁鉉｜工部 黎澄/李蕡·王永和·王佑｜山廠 陳恭。
    #    geo 把 戶部r1↔吏部r3、禮部r1/r2 错位、兵部r1↔禮部r2/r3、刑部r1↔兵部r1、
    #    工部r1↔刑部r1、工部r2↔刑部r2 全部下移一格；山廠带（陳恭）被吸进刑部 r3，
    #    而山廠键下挂的是前页 759 的 丁璿/程富（跨页残留，删）。
    760: [
        {"from": ("吏部", 3), "col": None, "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": None, "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": None, "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": None, "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": None, "to": ("兵部", 1)},
        {"from": ("禮部", 3), "col": None, "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": None, "to": ("刑部", 1)},
        {"from": ("刑部", 1), "col": None, "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": None, "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": None, "to": ("易州山廠提督", 1)},
    ],
}

# 跨页残留：geo 把前页山廠带复制到了后页（760 的 丁璿/程富 属 759/1444）
SPURIOUS: set[tuple[int, str, str]] = {
    (760, "易州山廠提督", "丁璿"),
    (760, "易州山廠提督", "程富"),
}

# 强制同名分代（D-01 阈值 80 年没触发的真两人）：王暹 1387–88 兵部右侍郎（試，原书 p701）
# 与 1449 左副都御史（原书 p764）相距 62 年，绝非一人。切点=≥10 年缺口，不受 MAX_SPAN 限。
IDENTITY_FORCE: set[str] = {"王暹"}

# band 类警报页（deep_row/label_mismatch/页级/借衙署）：行带归属未经原书核验
# （由 official_shilang 从 alarms 文件计算，此处不放常量）


def apply_book_fix(entries: list[dict], report: dict | None = None) -> list[dict]:
    """应用原书核验修正：按 (office,row)→(office,row) 重挂，返回新列表。

    两阶段：先按**原始** (office,row) 全量打标记（规则链不互相污染），再统一落位；
    SPURIOUS 跨页残留删除（重挂过的条目不删）。
    """
    import copy

    rep = report if report is not None else {}
    out = [copy.deepcopy(e) for e in entries]
    moved = 0
    for book, rules in BOOK_FIX.items():
        for e in out:
            if e["book"] != book:
                continue
            for rule in rules:
                fo, fr = rule["from"]
                if e["office"] != fo or e["row"] != fr:
                    continue
                if rule["col"] is not None and e["col"] != rule["col"]:
                    continue
                e["_to_office"] = rule["to"]
                e["_to_row"] = rule["to_row"] if "to_row" in rule else rule["to"][1]
                break
        for e in out:
            if "_to_office" in e:
                e["office_fix"] = {"from_office": e["office"], "from_row": e["row"],
                                   "to_office": e["_to_office"], "to_row": e["_to_row"],
                                   "source": f"原书核验 p{book}"}
                e["office"] = e.pop("_to_office")[0]
                e["row"] = e.pop("_to_row")
                moved += 1

    before = len(out)
    out = [e for e in out
           if (e["book"], e["office"], e["person"]) not in SPURIOUS
           or e.get("office_fix")]
    rep["book_fix"] = {"moved": moved, "removed": before - len(out),
                       "pages": sorted(BOOK_FIX)}
    return out
