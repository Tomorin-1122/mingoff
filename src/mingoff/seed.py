# -*- coding: utf-8 -*-
"""MVP 种子数据：崇祯朝兵部尚书历任。

数据来自 PRD 第 12.2 节（张德信《明代职官年表》口径），是**已验证的事实清单**：

    阎鸣泰→王在晋→王洽→申用懋(署)→梁廷栋→熊明遇→张凤翼→杨嗣昌
    →傅宗龙→陈新甲→张国维→李邦华→冯元飙→张缙彦

## 三点必须留意的数据问题（都在代码里显式处理）

1. **申用懋是「署」**（署理），不是实授 —— 这正是 PRD 要求区分 tenure_type 的原因。
2. **袁崇焕、孙传庭、卢象升不带此表**：他们是"兵部尚书衔/督师/总督"，属**加衔**，
   不是京中兵部尚书。混进来会让"历任兵部尚书"统计出错。
3. **年份多为约数**：崇祯朝兵部尚书更迭频繁且史料记载有歧，起始年按年表口径给，
   置信度不设为 1.0。这些正是后续要挂 `discrepancy` 的地方。

## 为什么把种子数据写成代码而不是 SQL 文件

它需要与 `TENURE_TYPES` 等常量一致，且测试要能直接 import 它做断言。
SQL 文件做不到这两点。
"""
from __future__ import annotations

from .repo import Office, Person, Source, Tenure

#: 崇祯朝兵部尚书历任：(姓名, 起始年, 离任年, 任职类型, 离任原因)
#: 年份按张德信年表口径；None = 史料未明确
CHONGZHEN_MINISTERS: tuple[tuple[str, int | None, int | None, str, str], ...] = (
    ("閻鳴泰", 1627, 1628, "实授", "罢免"),
    ("王在晉", 1628, 1628, "实授", "罢免"),
    ("王洽", 1628, 1629, "实授", "下狱"),
    ("申用懋", 1629, 1629, "署理", "迁转"),
    ("梁廷棟", 1629, 1630, "实授", "罢免"),
    ("熊明遇", 1630, 1631, "实授", "罢免"),
    ("張鳳翼", 1631, 1636, "实授", "自尽"),
    ("楊嗣昌", 1636, 1641, "实授", "卒于任"),
    ("傅宗龍", 1641, 1641, "实授", "下狱"),
    ("陳新甲", 1641, 1642, "实授", "下狱"),
    ("張國維", 1642, 1643, "实授", "罢免"),
    ("李邦華", 1643, 1643, "实授", "调任"),
    ("馮元飆", 1643, 1644, "实授", "致仕"),
    ("張縉彥", 1644, 1644, "实授", "降贼"),
)

#: PRD 12.2 明确要排除的人：带兵部尚书衔的督师/总督，非京中兵部尚书
HOLDERS_OF_TITLE_ONLY: tuple[str, ...] = ("袁崇煥", "孫傳庭", "盧象昇")

#: 兵部的雅称（PRD 12.1）。用于检索明实录原文时的关键词扩展 ——
#: 史料里"枢部""本兵"都指兵部，只用"兵部"检索会漏大量记载。
BINGBU_ALIASES: tuple[str, ...] = (
    "樞部", "樞垣", "樞曹", "本兵", "夏官", "武部", "大司馬",
)

#: 代表著作（PRD 12.2），作为人物的 bio 补充
WORKS: dict[str, str] = {
    "王在晉": "《三朝遼事實錄》",
    "熊明遇": "《中樞集略》",
    "張鳳翼": "《樞政錄》",
    "楊嗣昌": "《楊文弱先生集》",
    "張國維": "《吳中水利全書》",
    "李邦華": "《李忠肅公奏疏》",
    "張縉彥": "《菉居文集》",
}

#: 本批数据的史料来源
SOURCE_ZHANGDEXIN = Source(
    source_name="张德信年表",
    citation="张德信《明代职官年表》（2009，4册）· 兵部尚书年表",
    note="权威现代整理本，含署理区分",
)
SOURCE_MINGSHI = Source(
    source_name="明史",
    citation="《明史·七卿年表》",
    note="正史原表，范围窄且有讹误，须与年表校勘",
)


def office_bingbu_shangshu() -> Office:
    return Office(
        office_chn="兵部尚書",
        pinyin="Bingbu Shangshu",
        office_type="文",
        department="兵部",
        note="明代七卿之一，掌军事行政。雅称见 BINGBU_ALIASES",
    )


def office_bingbu() -> Office:
    """兵部衙门本身（作为父节点）。"""
    return Office(
        office_chn="兵部",
        pinyin="Bingbu",
        office_type="文",
        department="兵部",
        note="六部之一",
    )


def persons() -> list[Person]:
    out = []
    for name, *_ in CHONGZHEN_MINISTERS:
        out.append(
            Person(
                name_chn=name,
                native_addr="",
                bio=WORKS.get(name, ""),
                note="崇祯朝兵部尚书（据张德信年表）",
            )
        )
    return out


def tenures(person_ids: list[int], office_id: int) -> list[Tenure]:
    """按 CHONGZHEN_MINISTERS 生成任职记录。

    置信度不是常数：署理比实授的可考性低（年表对署任的起止记载常不精确），
    所以给 0.7；实授给 0.8 —— **不设 1.0**，因为这批数据尚未与《明实录》
    逐条校勘，而 PRD 明确要求"不追求绝对正确"。
    """
    if len(person_ids) != len(CHONGZHEN_MINISTERS):
        raise ValueError(
            f"人数不匹配：{len(person_ids)} 个 id vs {len(CHONGZHEN_MINISTERS)} 条记录"
        )
    out = []
    for pid, (name, start, end, ttype, leave) in zip(person_ids, CHONGZHEN_MINISTERS):
        out.append(
            Tenure(
                person_id=pid,
                office_id=office_id,
                start_year=start,
                end_year=end,
                tenure_type=ttype,
                leave_reason=leave,
                confidence=0.7 if ttype == "署理" else 0.8,
                note=f"{name}（据张德信年表）",
            )
        )
    return out
