# -*- coding: utf-8 -*-
"""京卿/六科人物 CBDB 对齐：official_{jingqing,kejishizhong} 未对齐实体 → person_cbdb_v1.json。

判据同部院 match_buyuan_cbdb.py（规范 3.2 + match_cbdb 8 层思想，宁空勿误挂）：
  1. 候选集 = BIOG_MAIN 精确同名 ∪ ALTNAME_DATA 别名同名（本名+简/繁归一形）；
  2. 生卒与段 span 完全不相斥才入围（卒年早于段起点 40 年+ = 硬冲突，任职再像也不挂）；
  3. 打分 = 时间相容（生卒窗重叠/段长）+ 本衙任职记录（POSTED_TO_OFFICE_DATA 年份相交
     且官名含本表关键词）；
  4. 唯一候选 ≥0.5 或 分差 >0.4 且 ≥1.0 才挂；并列/不足 → unresolved（top-4 留档）；
  5. MANUAL_MAP 人工裁决优先（method=manual / manual-null，带 note 留痕）；
     旧映射文件存在则合并、不覆盖人工结果。

用法：PYTHONPATH=src python scripts/match_official_cbdb.py [--table jingqing|kejishizhong]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "mingoff" / "data"
CBDB = Path(r"C:\Users\31698\projects\guji-pipeline\_cbdb\cbdb_20261010.sqlite3")

# 简体→繁体（同部院：只映射确证字形）
S2T = {"邓": "鄧", "刘": "劉", "冲": "沖", "赵": "趙", "凯": "凱", "万": "萬",
       "吴": "吳", "吕": "呂", "张": "張", "陈": "陳", "杨": "楊", "黄": "黃",
       "马": "馬", "许": "許", "冯": "馮", "蒋": "蔣", "韩": "韓", "孙": "孫",
       "郑": "鄭", "王": "王", "李": "李"}

# 表配置：输入 / 输出 / 本衙任职官名关键词（CBDB OFFICE_CODES 官名子串）/ 人工裁决
# 关键词精度原则：只认本表座主官（如「司通政使」不会命中右通政；「X科都給事中」不命中左右給事中）
TABLES: dict[str, dict] = {
    "jingqing": {
        "title": "京卿年表（京師）",
        "input": "official_jingqing.json",
        "out_map": "vol1_jingqing_person_cbdb_v1.json",
        "out_review": "vol1_jingqing_cbdb_unresolved.json",
        "old_maps": ["vol1_jingqing_person_cbdb_v1.json"],   # 自合并：重跑不覆盖人工/既有结果
        "office_hint": {
            "通政使": ["通政使司通政使"],
            "大理卿": ["大理寺卿", "大理卿"],
            "太常卿": ["太常寺卿", "太常卿"],
            "光祿卿": ["光祿寺卿", "光祿卿"],
            "太僕卿": ["太僕寺卿", "太僕卿"],
            "鴻臚卿": ["鴻臚寺卿", "鴻臚卿"],
            "尚寶卿": ["尚寶司卿", "尚寶卿"],
            "順天府府尹": ["順天府府尹", "府尹"],
        },
        "hint_fallback": ["卿", "府尹"],
        # 仕历链证据：本衙系统内任意职（CBDB 对座主官 recording 稀，但左/右/少卿等
        # 迁转链常见）——候选在本衙系统 ±6 年内有任职记录即 +0.5，唯一命中才随分差挂
        "career_hint": {
            "通政使": ["通政"], "大理卿": ["大理寺"], "太常卿": ["太常寺"],
            "光祿卿": ["光祿寺"], "太僕卿": ["太僕寺"], "鴻臚卿": ["鴻臚寺"],
            "尚寶卿": ["尚寶司"], "順天府府尹": ["順天府"],
        },
        "keep_null": set(),       # 人工既定 NULL（如部院李本 D44），留待 review 后增补
        "manual": {               # person_id → {"id": int|None, "note": str}，人工裁决留痕
            # 曾秉正 66533：CBDB 通政使 1377–1382 任职记录 + 卒 1382，与段 [1382,1382] 吻合
            "曾秉正": {"id": 66533,
                      "note": "CBDB 通政使 1377–1382 任职记录 + 卒 1382，段 [1382,1382] 吻合"},
            # 汪宗尹：CBDB 无此人条目（收作汪宗伊 127510 别名），但书内 1570–71 尚寶卿与
            # 1573–74 光祿卿（汪宗伊）是相邻两任，同一人还是兄弟两人待考 → NULL 留待正字轮
            "汪宗尹": {"id": None,
                      "note": "CBDB 无条目（仅作汪宗伊别名收）；与汪宗伊 1573–74 是相邻两任，"
                              "同一人抑或两人待考，宁空勿误挂"},
        },
    },
    "kejishizhong": {
        "title": "六科都給事中年表",
        "input": "official_kejishizhong.json",
        "out_map": "vol2_kejishizhong_person_cbdb_v1.json",
        "out_review": "vol2_kejishizhong_cbdb_unresolved.json",
        "old_maps": ["vol2_kejishizhong_person_cbdb_v1.json"],   # 自合并
        "office_hint": {
            "吏科": ["吏科都給事中", "都給事中"],
            "戶科": ["戶科都給事中", "都給事中"],
            "禮科": ["禮科都給事中", "都給事中"],
            "兵科": ["兵科都給事中", "都給事中"],
            "刑科": ["刑科都給事中", "都給事中"],
            "工科": ["工科都給事中", "都給事中"],
        },
        "hint_fallback": ["都給事中"],
        "career_hint": {
            "吏科": ["吏科"], "戶科": ["戶科"], "禮科": ["禮科"],
            "兵科": ["兵科"], "刑科": ["刑科"], "工科": ["工科"],
        },
        "keep_null": set(),
        "manual": {
            # 凌義渠 34757：生卒 1593–1644 与史实吻合（甲申殉节），京卿表同名 scored-unique 同证
            "凌義渠": {"id": 34757,
                      "note": "生卒 1593–1644 与史实吻合；京卿表同名候选 scored-unique 同证"},
            # 薛國觀 362351：index 1589 与天啟/崇禎朝仕历相合（另一候选 133302 无任何年代信息）
            "薛國觀": {"id": 362351,
                      "note": "index 1589 与天啟/崇禎朝仕历相合；另一候选 133302 无任何年代信息"},
            # 范淑泰 360850：index 1598 与崇禎初工科給事中仕历相合（另一候选无年代信息）
            "范淑泰": {"id": 360850,
                      "note": "index 1598 与崇禎初工科給事中仕历相合；另一候选无年代信息"},
            # 張孔教 125527：卒 1644 + index 1581，与 吏科 1617 署–1622 遷 仕历相合；
            # 另一候选 345329 无任何年代/任职信息
            "張孔教": {"id": 125527,
                      "note": "卒 1644 + index 1581 与吏科 1617–1622 仕历相合；另一候选无年代信息"},
        },
    },
    "shilang": {
        "title": "部院侍郎年表（京師）",
        "input": "official_shilang.json",
        "out_map": "vol1_shilang_person_cbdb_v1.json",
        "out_review": "vol1_shilang_cbdb_unresolved.json",
        "old_maps": ["vol1_shilang_person_cbdb_v1.json"],   # 自合并
        "office_hint": {
            **{f"{m}侍郎": [f"{m}侍郎"] for m in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部")},
            **{f"{m}左侍郎": [f"{m}左侍郎", f"{m}侍郎"] for m in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部")},
            **{f"{m}右侍郎": [f"{m}右侍郎", f"{m}侍郎"] for m in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部")},
            "副都御史": ["副都御史"],
            "左副都御史": ["左副都御史", "副都御史"],
            "右副都御史": ["右副都御史", "副都御史"],
            "御史中丞": ["御史中丞", "御史"],
            "提督易州山廠": ["山廠"],
            "總糧儲": ["總督倉場", "倉場", "糧儲"],
        },
        "hint_fallback": ["侍郎", "御史"],
        "career_hint": {
            **{f"{m}{s}": [m] for m in ("吏部", "戶部", "禮部", "兵部", "刑部", "工部")
               for s in ("侍郎", "左侍郎", "右侍郎")},
            "副都御史": ["御史"], "左副都御史": ["御史"], "右副都御史": ["御史"],
            "御史中丞": ["御史"],
            "提督易州山廠": ["工部", "山廠"], "總糧儲": ["總督倉場", "戶部"],
        },
        "keep_null": set(),
        "manual": {
            # 王之寀：书页 p964（崇禎四年）兵部带白纸黑字印王之寀（1631 在任），
            # 而 CBDB 65713 卒 1627——书库矛盾待考，宁空勿误挂
            "王之寀": {"id": None,
                      "note": "书 p964 崇禎四年兵部带仍印王之寀，CBDB 65713 卒 1627 矛盾，待考"},
        },
    },
    "jingying": {
        "title": "总督京营戎政大臣年表",
        "input": "official_jingying.json",
        "out_map": "vol3_jingying_person_cbdb_v1.json",
        "out_review": "vol3_jingying_cbdb_unresolved.json",
        "old_maps": ["vol3_jingying_person_cbdb_v1.json"],
        "office_hint": {
            "總督京營戎政": ["总督京营戎政", "提督京营戎政", "总督京营"],
            "協理京營戎政": ["协理京营戎政", "協理京營戎政", "提督京营戎政"],
            "五軍營": ["五军营", "五军"],
            "三千營": ["三千营", "神枢营"],
            "神樞營": ["神枢营", "三千营"],
            "神機營": ["神机营"],
            "京營參將": ["京营参将", "参将"],
        },
        "hint_fallback": ["京营", "营"],
        "career_hint": {
            "總督京營戎政": ["京营"], "協理京營戎政": ["京营"],
            "五軍營": ["京营", "五军"], "三千營": ["京营", "神枢", "三千"],
            "神樞營": ["京营", "神枢"], "神機營": ["京营", "神机"],
            "京營參將": ["京营", "参将"],
        },
        "keep_null": set(),
        "manual": {},
    },
    "zongdu": {
        "title": "总督年表",
        "input": "official_zongdu.json",
        "out_map": "vol3_zongdu_person_cbdb_v1.json",
        "out_review": "vol3_zongdu_cbdb_unresolved.json",
        "old_maps": ["vol3_zongdu_person_cbdb_v1.json"],
        "office_hint": {
            "兩廣": ["总督两广"], "宣大": ["总督宣大", "宣大"],
            "薊遼": ["总督蓟辽", "蓟辽"], "漕運": ["总督漕运", "漕运"],
            "河道": ["总督河道", "总理河道", "河道"],
            "陕西三邊": ["陕西三边", "三边"], "貴州": ["总督贵州"],
            "京師": ["总督京师"], "遼東": ["总督辽东"],
            "遼東經略": ["辽东经略", "经略"], "朝鮮": ["经略朝鲜", "朝鲜"],
            "經略": ["经略"], "河漕": ["总督河漕"],
            "湖廣四川貴州": ["总督四川贵州", "四川贵州"],
            "川貴湖廣": ["总督川贵", "四川贵州湖广"],
            "總督五省軍務": ["总理", "总督"],
            "總督": ["总督"], "保定": ["总督保定", "保定"],
        },
        "hint_fallback": ["总督", "总理", "经略"],
        "career_hint": {
            "兩廣": ["两广", "广东", "广西"], "宣大": ["宣府", "大同"],
            "薊遼": ["蓟州", "辽东"], "漕運": ["漕运", "凤阳"],
            "河道": ["河道"], "陕西三邊": ["固原", "宁夏", "甘肃", "延绥"],
            "貴州": ["贵州"], "遼東": ["辽东"], "遼東經略": ["辽东"],
            "朝鮮": ["朝鲜"], "經略": ["朝鲜", "辽东"],
            "湖廣四川貴州": ["四川", "贵州"], "川貴湖廣": ["四川", "贵州", "湖广"],
        },
        "keep_null": set(),
        "manual": {
            # 商周祚：部院+京卿双证 339168(idx1571)；总督侧误挂 54150(idx1575) 同名重出条
            "商周祚": {"id": 339168,
                      "note": "部院+京卿双证 339168；54150(idx1575) 疑 CBDB 重出条，归一"},
            # 孫應奎：CBDB 68295/68296 同名重出条；部院表已裁 68295(d-1570,idx1507)
            "孫應奎": {"id": 68295,
                      "note": "部院表已裁 68295；68296 为重出条，归一"},
        },
    },
    "xunfu": {
        "title": "巡抚年表",
        "input": "official_xunfu.json",
        "out_map": "vol3_xunfu_person_cbdb_v1.json",
        "out_review": "vol3_xunfu_cbdb_unresolved.json",
        "old_maps": ["vol3_xunfu_person_cbdb_v1.json"],
        "office_hint": {
            "江西": ["巡抚江西"], "浙江": ["巡抚浙江"], "湖廣": ["巡抚湖广"],
            "山東": ["巡抚山东"], "山西": ["巡抚山西"], "陕西": ["巡抚陕西"],
            "河南": ["巡抚河南"], "四川": ["巡抚四川"], "貴州": ["巡抚贵州"],
            "雲南": ["巡抚云南"], "廣西": ["巡抚广西"], "廣東": ["巡抚广东"],
            "福建": ["巡抚福建"], "遼東": ["巡抚辽东"], "宣府": ["巡抚宣府"],
            "大同": ["巡抚大同"], "甘肅": ["巡抚甘肃"], "寧夏": ["巡抚宁夏"],
            "延綏": ["巡抚延绥"], "應天": ["巡抚应天", "应天巡抚"],
            "鳳陽": ["巡抚凤阳"], "鄖陽": ["巡抚郧阳"], "保定": ["巡抚保定"],
            "順天": ["巡抚顺天"], "天津": ["巡抚天津"], "登萊": ["巡抚登莱"],
            "南赣": ["巡抚南赣", "南赣巡抚"], "南直隸蘇松": ["巡抚苏松"],
            "河南山西": ["巡抚河南", "巡抚山西"], "北直隸山東": ["巡抚山东"],
            "大同宣府": ["巡抚大同", "巡抚宣府"],
        },
        "hint_fallback": ["巡抚"],
        "career_hint": {
            **{p: [p] for p in ("江西", "浙江", "湖广", "山东", "山西", "陕西",
                                "河南", "四川", "贵州", "云南", "广西", "广东",
                                "福建", "辽东", "宣府", "大同", "甘肃", "宁夏",
                                "延绥", "郧阳", "保定", "顺天", "天津", "登莱")},
            "南直隸蘇松": ["苏州", "松江"], "應天": ["应天", "苏州"],
            "河南山西": ["河南", "山西"], "北直隸山東": ["山东", "北直隶"],
            "大同宣府": ["大同", "宣府"],
        },
        "keep_null": set(),
        "manual": {
            # 王永壽：巡抚侧误挂 69123（清人 idx1787 卒 1850）；正统景泰间王永壽无确证，宁空
            "王永壽": {"id": None,
                      "note": "69123 卒 1850 与正统段(湖廣1454-56/貴州1455-57)硬冲突，宁空勿误挂"},
            # 張鎣：部院+侍郎双证 347193(idx1418)；130680(1422-1493) 疑 CBDB 重出条
            "張鎣": {"id": 347193,
                    "note": "部院+侍郎双证 347193；130680 疑重出条，归一"},
        },
    },    "zongbing": {
        "title": "镇守总兵官年表",
        "input": "official_zongbing.json",
        "out_map": "vol3_zongbing_person_cbdb_v1.json",
        "out_review": "vol3_zongbing_cbdb_unresolved.json",
        "old_maps": ["vol3_zongbing_person_cbdb_v1.json"],
        "office_hint": {
            **{r: [f"镇守{r}总兵", f"{r}总兵", "总兵官", "总兵"]
               for r in ("薊州", "宣府", "大同", "遼東", "寧夏", "甘肅", "延綏", "陕西",
                         "湖廣", "昌平", "保定", "通州", "山東", "河南", "密雲", "雲南",
                         "貴州", "四川", "廣西", "浙江", "福建", "凉州", "兩廣", "廣東",
                         "臨洮", "松潘", "四川松潘", "京師", "漕運", "南贛")},
            "薊州山海": ["山海关", "总兵官"],
            "昌平易州": ["昌平", "总兵官"],
        },
        "hint_fallback": ["总兵官", "总兵", "副總兵"],
        "career_hint": {
            **{r: [r, "".join(S2T.get(c, c) for c in r)]
               for r in ("薊州", "宣府", "大同", "遼東", "寧夏", "甘肅", "延綏",
                         "湖廣", "昌平", "保定", "通州", "山東", "河南", "密雲",
                         "雲南", "貴州", "四川", "廣西", "浙江", "福建", "凉州",
                         "兩廣", "廣東", "臨洮", "松潘")},
        },
        "keep_null": set(),
        "manual": {},
    },
    "buzhengshi": {
        "title": "承宣布政使年表",
        "input": "official_buzhengshi.json",
        "out_map": "vol4_buzhengshi_person_cbdb_v1.json",
        "out_review": "vol4_buzhengshi_cbdb_unresolved.json",
        "old_maps": ["vol4_buzhengshi_person_cbdb_v1.json"],
        "office_hint": {
            **{pr: [f"{pr}布政", f"{pr}左布政", f"{pr}右布政", "布政使"]
               for pr in ("北平", "山東", "山西", "河南", "四川", "江西", "浙江",
                          "福建", "廣東", "廣西", "湖廣", "雲南", "貴州")},
            "陕西": ["陕西布政", "陝西布政", "陕西左布政", "陝西左布政", "陝西右布政"],
        },
        "hint_fallback": ["布政使", "參政", "參議"],
        "career_hint": {
            **{pr: [pr, "".join(S2T.get(c, c) for c in pr)]
               for pr in ("北平", "山東", "山西", "河南", "陕西", "四川", "江西",
                          "浙江", "福建", "廣東", "廣西", "湖廣", "雲南", "貴州")},
        },
        "keep_null": set(),
        "manual": {
            # 2026-11-21 冲突 triage：CBDB 重出条按老表多表双证值归一（office_raw 留痕见 unresolved）
            "何鰲": {"id": 128463, "note": "段1533-1550嘉靖，128463(1497-1559) 吻合；311991(idx1490) 疑重出"},
            "党馨": {"id": 205616, "note": "段1589湖廣万历，与巡抚表一致"},
            "張本": {"id": 66903,
                      "note": "CBDB 同名两代：66883(1367-1431)=永乐张本(侍郎1406-24)；弘治湖广布政使 1502-03 归 66903(1437-1508)"},
            "張瓚": {"id": 67443,
                      "note": "CBDB 同名两代：67450(1473-1542)=弘治嘉靖张瓚(侍郎1478-1535/京卿1525-31)；成化浙江布政使 1471-74 归 67443(1427-1481)"},
            "徐作": {"id": 204951, "note": "京卿表证；530915 疑重出条"},
            "徐貫": {"id": 198667, "note": "侍郎+巡抚双证(1422-)；479757 疑重出条"},
            "文明": {"id": 126424, "note": "部院证；503111 疑重出条"},
            "李嗣": {"id": 127965, "note": "侍郎+巡抚双证；470109 疑重出条"},
            "李敏": {"id": 67840,
                      "note": "CBDB 同名两代：67848(卒1585,idx1522)=京卿1565-67/六科1553-56李敏；成化四川/山西布政使 1474-77 归 67840(1425-1491)"},
            "李貢": {"id": 127870, "note": "侍郎证；503100 疑重出条"},
            "王敏": {"id": 100799, "note": "部院证；503089 疑重出条"},
            "王詔": {"id": 67938,
                      "note": "CBDB 同名两代：67953(卒1480,idx1417)=侍郎1469-80王詔；成化湖广/云南布政使 1483-88 归 67938(1428-1491)"},
            "畢亨": {"id": 131062, "note": "部院证；198441(idx1420) 与段1502-04 相距太远，待考"},
            "謝存儒": {"id": 133159, "note": "巡抚证；503117 疑重出条"},
            "路璧": {"id": 132032, "note": "六科证；479751 疑重出条"},
            "鄭洛": {"id": 125020, "note": "巡抚证；214361(idx1523) 疑重出条"},
            "高友璣": {"id": 129362, "note": "四表双证(1461-1546)；503087 疑重出条"},
            # 於/于 简繁变体（CBDB 收于形；生卒窗硬含段，形讹反查唯一命中）
            "侯於趙": {"id": 129248, "note": "CBDB 侯于趙(1536-1597)，於/于变体；生卒窗硬含段1580-83"},
            "周於德": {"id": 205516, "note": "CBDB 周于德(1538-)，於/于变体；段1555-1600 相容"},
        },
    },
}


def t2s_norm(name: str) -> str:
    return "".join(S2T.get(ch, ch) for ch in name)


def span_compat(birth, death, iy, lo, hi) -> float:
    """生卒与段 span 的相容分：重叠年数/段长，无生卒给中性分 0.5。

    生卒窗 = birth+15 .. death（含端点，重叠按闭区间年数 +1 计——单年段与窗恰交
    是真重叠，不是 0）。
    无生卒但有 index_year（中举/入仕年代锚，软证据）：窗 iy−30..iy+50 命中给 0.7、
    未命中给 0.0——可拉开并列但不触发硬拒（宁空勿误挂仍由 ambiguous 兜底）。
    """
    if birth is None and death is None:
        if iy:
            wb, we = iy - 30, iy + 50
            return 0.7 if (min(hi, we) - max(lo, wb) + 1) > 0 else 0.0
        return 0.5
    b = birth if birth is not None else -9999
    d = death if death is not None else 9999
    wb, we = b + 15, d
    ov = max(0, min(hi, we) - max(lo, wb) + 1)
    if ov > 0:
        return min(1.0, ov / max(1, hi - lo + 1))
    if we < lo - 40:
        return -1.0
    return 0.0


def match_table(key: str, cfg: dict, con: sqlite3.Connection,
                postings: dict[int, list[tuple[str, int, int]]],
                altnames: dict[str, set[int]],
                biog_by_name: dict[str, list[tuple]],
                biog_by_id: dict[int, tuple]) -> tuple[dict, list[dict]]:
    doc = json.loads((DATA / cfg["input"]).read_text(encoding="utf-8"))
    by_pid: dict[str, dict] = {}
    for t in doc["tenures"]:
        pid = t["person_id"]
        e = by_pid.setdefault(pid, {"person": t["person"],
                                    "span": [t["start_year"], t["end_year"]],
                                    "offices": set(), "aligned": bool(t.get("cbdb_id"))})
        e["span"][0] = min(e["span"][0], t["start_year"])
        e["span"][1] = max(e["span"][1], t["end_year"])
        e["offices"].add(t["office"])

    old_map: dict[str, dict] = {}
    for v in cfg["old_maps"]:
        p = DATA / v
        if p.is_file():
            old_map.update(json.loads(p.read_text(encoding="utf-8")))
            break

    keep_null = cfg["keep_null"]
    manual: dict[str, dict] = dict(cfg["manual"])
    # 辖区+年代任职反查的可决集（classify_unresolved.py 生成，region-unique 证据）
    gen = DATA / "vol3_cbdb_region_unique.json"
    if gen.is_file():
        for k, v in json.loads(gen.read_text(encoding="utf-8")).get(key, {}).items():
            manual.setdefault(k, v)
    todo = [p for p, e in by_pid.items()
            if not e["aligned"] and p not in keep_null and p not in manual]
    print(f"[{key}] {cfg['title']}：未对齐实体 {len(todo)} 个"
          f"（keep_null {len(keep_null)} / manual {len(manual)}），开始对齐")

    new_map: dict[str, dict] = {}
    unresolved: list[dict] = []

    # 人工裁决优先
    for pid, spec in manual.items():
        e = by_pid.get(pid)
        if e is None:
            continue
        lo, hi = e["span"]
        if spec["id"] is None:
            new_map[pid] = {"cbdb_id": None, "cbdb_name": e["person"],
                            "method": "manual-null", "score": None,
                            "birth": None, "death": None, "span": [lo, hi],
                            "note": spec.get("note", "")}
            continue
        r = biog_by_id.get(spec["id"])
        if not r:
            unresolved.append({"person_id": pid, "name": e["person"],
                               "reason": "manual-id-not-found", "manual_id": spec["id"]})
            continue
        new_map[pid] = {"cbdb_id": spec["id"], "cbdb_name": r[0],
                        "method": "manual", "score": None,
                        "birth": r[1], "death": r[2], "span": [lo, hi],
                        "note": spec.get("note", "")}

    for pid in todo:
        e = by_pid[pid]
        name, (lo, hi), offices = e["person"], e["span"], e["offices"]
        qname = t2s_norm(name)
        cands = {r[0]: r[1:] for r in
                 biog_by_name.get(name, []) + biog_by_name.get(qname, [])}
        for cpid in (altnames.get(name, set()) | altnames.get(qname, set())):
            if cpid in cands:
                continue
            r = biog_by_id.get(cpid)
            if r:
                cands[cpid] = r
        if not cands:
            unresolved.append({"person_id": pid, "name": name, "reason": "no-candidate"})
            continue

        hints = sorted({h for o in offices for h in
                        cfg["office_hint"].get(o, cfg["hint_fallback"])})
        career_stems = sorted({s for o in offices
                               for s in cfg["career_hint"].get(o, [])})
        sur = t2s_norm(name)[0]  # 本实体姓氏（S2T 归一）——任职证据的同姓守卫
        scored = []
        for cpid, (cn, birth, death, iy) in cands.items():
            s_time = span_compat(birth, death, iy, lo, hi)
            if s_time <= 0 and (birth is not None or death is not None):
                continue
            if s_time < 0:
                continue
            # 任职/仕历证据要求同姓：前任/继任同名不同姓是高发混淆
            # （如 趙榮 大理寺卿 1461–63 与 王榮 大理卿 1465），异姓不给任职分
            sur_ok = bool(cn) and t2s_norm(cn)[0] == sur
            s_office = 0.0
            if sur_ok:
                for chn, fy, ly in postings.get(cpid, ()):
                    if fy <= hi and ly >= lo and any(h in chn for h in hints):
                        s_office = 1.0
                        break
            # 仕历链分：本衙系统内任意职、窗 ±6 年（座主官前任通常为左/右/少卿等，
            # 迁转链相邻）——CBDB 座主官 recording 稀薄时的次强证据
            s_career = 0.0
            if sur_ok and career_stems:
                for chn, fy, ly in postings.get(cpid, ()):
                    if fy <= hi + 6 and ly >= lo - 6 and any(s in chn for s in career_stems):
                        s_career = 0.5
                        break
            score = s_time + s_office + s_career
            scored.append({"id": cpid, "name": cn, "birth": birth, "death": death,
                           "iy": iy, "s_time": round(s_time, 2), "s_office": s_office,
                           "s_career": s_career, "score": round(score, 2)})
        if not scored:
            unresolved.append({"person_id": pid, "name": name, "reason": "time-conflict"})
            continue
        scored.sort(key=lambda s: -s["score"])
        top, second = scored[0], (scored[1] if len(scored) > 1 else None)
        if len(scored) == 1 and top["score"] >= 0.5:
            m = "exact-unique"
        elif second is None or (top["score"] - second["score"] > 0.4
                                and top["score"] >= 1.0):
            m = "scored-unique"
        elif (top["score"] == 0.7 and second["score"] == 0.0
              and all(s["score"] == 0.0 for s in scored[1:])):
            # era-unique：无生卒，唯一年代锚合窗，其余候选全部年代相斥——
            # 1.0 门槛是为有生卒/任职分的候选定的；纯 index_year 案例里
            # 「合窗 vs 相斥」对比即强证据。任一候选未相斥（≥0.5）则仍拒绝。
            m = "era-unique"
        else:
            unresolved.append({"person_id": pid, "name": name, "reason": "ambiguous",
                               "cands": scored[:4]})
            continue
        new_map[pid] = {"cbdb_id": top["id"], "cbdb_name": top["name"], "method": m,
                        "score": top["score"], "birth": top["birth"], "death": top["death"],
                        "span": [lo, hi]}

    merged = dict(old_map)
    merged.update(new_map)
    (DATA / cfg["out_map"]).write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / cfg["out_review"]).write_text(
        json.dumps({"unresolved": unresolved}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    dist = Counter(v["method"] for v in new_map.values())
    print(f"[{key}] 新增对齐 {len(new_map)}；仍未决 {len(unresolved)}"
          f"（→ {cfg['out_review']}）；总映射 {len(merged)} → {cfg['out_map']}")
    print(f"[{key}] 方法分布: {dict(dist)}")
    return merged, unresolved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", choices=sorted(TABLES), default=None,
                    help="只跑指定表；缺省两表都跑")
    args = ap.parse_args()
    if not CBDB.is_file():
        print(f"CBDB 库缺失: {CBDB}", file=sys.stderr)
        return 1
    con = sqlite3.connect(str(CBDB))

    print("预载 CBDB 索引…", flush=True)
    postings: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for cpid, chn, fy, ly in con.execute(
            "select p.c_personid, o.c_office_chn, p.c_firstyear, p.c_lastyear "
            "from POSTED_TO_OFFICE_DATA p join OFFICE_CODES o on o.c_office_id=p.c_office_id"):
        fy2 = fy or 0
        ly2 = ly if ly else (fy2 + 30 if fy2 else 9999)
        postings[cpid].append((chn, fy2, min(ly2, 9999)))
    altnames: dict[str, set[int]] = defaultdict(set)
    for cpid, alt in con.execute("select c_personid, c_alt_name_chn from ALTNAME_DATA"):
        if alt:
            altnames[alt].add(cpid)
    # BIOG_MAIN 也一次全扫进内存（c_name_chn 无索引，逐候选查询 = 每次全表扫 66 万行）
    biog_by_name: dict[str, list[tuple]] = defaultdict(list)
    biog_by_id: dict[int, tuple] = {}
    for cpid, cn, b, d, iy in con.execute(
            "select c_personid, c_name_chn, c_birthyear, c_deathyear, c_index_year "
            "from BIOG_MAIN"):
        row = (cn, b, d, iy)
        biog_by_name[cn].append((cpid,) + row)
        biog_by_id[cpid] = row
    print(f"  任职记录 {sum(len(v) for v in postings.values())} 条 / 别名 {len(altnames)} 项 / "
          f"人名 {len(biog_by_name)} 项", flush=True)

    for key, cfg in TABLES.items():
        if args.table and key != args.table:
            continue
        match_table(key, cfg, con, postings, altnames, biog_by_name, biog_by_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())