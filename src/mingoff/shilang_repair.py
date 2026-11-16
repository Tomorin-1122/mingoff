# -*- coding: utf-8 -*-
"""侍郎年表 book-patch：原书核验修正（2026-11-08，正字/核验轮）。

背景：几何解析对 103 个「行带警报页」存在三类已证实的错挂——
  A. 兵部带首行被吸进前一衙的 r3（954/800 两例同构，相距百余年）；
  B. 易州山廠带被吸进前一衙的 r3（760 陳恭 / 800 萬祺·談倫）；
  C. 整页部界级联错移（760：自戶部以下逐衙错一格）。
每处均以原书页图（D:\\北山研史\\明代职官\\第1册，物理页=正文+15）逐行核对后定案；
渲染件 _scratch/shilang/verify/bookNNN.png，报告 docs/侍郎表接入报告.md。

格式：BOOK_FIX[book页] = [(old_office, old_row, col, person) → (new_office, new_row), ...]
col/person 为 None/缺省时匹配该 (office,row) 全部条目；person 可限定只重挂某人
（防同格他人误伤）。未列出的警报页保持 pending（待校对台），数据不删，站点灰显。
整页实拍核验通过、无错挂的警报页入 VERIFIED_PAGES 清 pending。
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
    # ── 811（弘治八年 1495）：C 型整页级联错位（同 760）——原书 8 格
    #    （吏｜戶｜禮｜刑｜兵｜工｜山廠｜都察院）被 geo 错切成
    #    吏部r1-r3｜戶部r1-r2｜禮部r1-r3｜兵部r1-r2｜刑部r1-r2｜工部r1-r2｜山廠r1。
    #    逐行对原书渲染件 bookphys826.png（正文 811）重挂：
    #    格1 吏部：周經（左）+秦民悅→佀鍾（右）——geo 吏部 r1/r2 本就正确；
    #    格2 戶部：吳原卒/劉大夏 12-4 右侍遷（左带）+佀鍾 10-5 改吏右侍/
    #        劉大夏 10-18 右副都改→12-4 遷左/韓文 12-4 到任（右带）——geo 吏部 r3+戶部 r1；
    #    格3 禮部：徐瓊（左）+傅瀚（右）——geo 戶部 r2+禮部 r1；
    #    格4 刑部：李介 2-12 右侍遷升刑左+李介遷左/王宗彝 2-12 到任刑右——geo 禮部 r2/r3；
    #    格5 兵部：張錦丁憂→戴珊+戴珊遷左/謝綬 3-21 工右侍改——geo 兵部 r1/r2 正确；
    #    格6 工部：徐貫 4-1 兼右僉都治蘇松水道（工左带在任出差）+謝綬 3-21 改刑右侍/
    #        曾鑑 3-27 提督山廠工右侍改理部事（工右带）——geo 刑部 r1/r2；
    #    格7 山廠：曾鑑 3-27 改理部事（离任）/王傅 4-3 左通政遷太僕卿管山厂
    #        →5-2 降鄖陽知府/彭禮 5-3 太僕卿接——geo 工部 r1/r2；
    #    格8 都察院：翟瑄（左副都在任）+劉大夏 7-17 召/8-20 回理院事/10-18 改戶右侍
    #        （右副都带）——geo 山廠 r1。
    #    衙序佐证：p810/p812 行带链完全自洽（秦民悅 12-14 戶右改吏右→佀鍾 12-20
    #    接戶右督倉場；佀鍾 1496-4-18 吏右遷左；傅瀚 1496-4-18 禮右遷左）。
    811: [
        {"from": ("吏部", 3), "col": None, "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": None, "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": None, "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": None, "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": None, "to": ("刑部", 1)},
        {"from": ("禮部", 3), "col": None, "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": None, "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": None, "to": ("工部", 2)},
        {"from": ("工部", 1), "col": None, "to": ("易州山廠提督", 1)},
        {"from": ("工部", 2), "col": None, "to": ("易州山廠提督", 1)},
        # 格8 都察院：geo 山廠带按列拆——c1 翟瑄=左副都带（r1）、
        # c2 劉大夏 7-17 召/8-20 回理院事/10-18 改戶右侍=右副都带（r2）
        {"from": ("易州山廠提督", 1), "col": 1, "to": ("都察院", 1)},
        {"from": ("易州山廠提督", 1), "col": 2, "to": ("都察院", 2)},
    ],
    # ── 812（弘治九年 1496）：仅一处 D 型三行带——geo 工部 r3 彭禮「四、丁亥、十，
    #    遷工右侍」实为书页山廠带离任注（X遷Y=迁往工右侍），应归 r2（工右带）。
    812: [
        {"from": ("工部", 3), "col": None, "to": ("工部", 2)},
    ],
    # ── 詹沂都察院连环错挂（2026-11-15 侍郎核验小轮，实拍 838/945 判读）：
    #    詹沂 1603-12-16 太常卿遷左副都御史，至 1609-9 封印求罷一直在都察院 r1，
    #    geo 却把 927/929/930/933 四页的都察院行名字吸进前一衙深行带
    #    （928/931/932 三页正常）——书内五重铁证：
    #    ①927 到任注「太常卿遷左副都」自证迁入衙；②929 注「署院印」（院=都察院）；
    #    ③933 注「封印求罷」（掌印堂官行为，侍郎无印可封）；④933 注「赠左都」
    #    （生前职衔为副都御史的追赠规格）；⑤928/931/932 都察院 r1 连续在任闭合。
    #    933 刑部 r2 c2 許弘綱为正确挂刑右侍，person 限定防误伤。
    927: [
        {"from": ("工部", 1), "col": 1, "person": "詹沂", "to": ("都察院", 1)},
    ],
    929: [
        {"from": ("工部", 2), "col": 1, "person": "詹沂", "to": ("都察院", 1)},
    ],
    930: [
        {"from": ("工部", 3), "col": 1, "person": "詹沂", "to": ("都察院", 1)},
    ],
    933: [
        {"from": ("刑部", 2), "col": 1, "person": "詹沂", "to": ("都察院", 1)},
    ],
    # ══ 2026-11-15 侍郎 band 核验批量轮（子代理逐页实拍+主会话复核，verdict 存档
    #    _scratch/shilang/verify_batch/verdicts/）。主模式：C 型整页级联／山廠行误吸
    #    前衙深行带／都察院行误吸工部 r3／missing 名字被吞进邻条 notes。
    # ── 760（正统十年）：重写 11-08 修复——丁璿/程富实为都察院 r1/r2 真条目
    #    （SPURIOUS 已撤销），兵部 r1 薛希璉/馬昂/丁鉉归刑部 r2（4x 特写刑部 r1 空置）。
    760: [
        {"from": ("吏部", 3), "col": None, "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": None, "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": None, "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": None, "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": None, "to": ("兵部", 1)},
        {"from": ("禮部", 3), "col": None, "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": None, "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": None, "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": None, "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": None, "to": ("易州山廠提督", 1)},
        {"from": ("易州山廠提督", 1), "col": 1, "to": ("都察院", 1)},
        {"from": ("易州山廠提督", 2), "col": 1, "to": ("都察院", 2)},
    ],
    # ── 717（建文四年）：C 型整页级联——geo 自卓敬行（实为戶部上行）起整体下移一衙，
    #    末格御史府·御史中丞并入工部（716 标签列同构+茅大方/師逵/夏原吉注互证）。
    717: [
        {"from": ("吏部", 3), "col": 1, "person": "卓敬", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 2, "person": "郭任", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 3, "person": "夏原吉", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 4, "person": "古樸", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "夏原吉", "to": ("戶部", 2)},
        {"from": ("戶部", 1), "col": 2, "person": "盧迥", "to": ("戶部", 2)},
        {"from": ("戶部", 1), "col": 3, "person": "古樸", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 3, "person": "師逵", "to": ("吏部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "董倫", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 2, "person": "陳性善", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 3, "person": "黄觀", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 4, "person": "宋禮", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "王景", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 2, "person": "黄魁", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 3, "person": "宋禮", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 4, "person": "戚存心", "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "劉儁", "to": ("兵部", 1)},
        {"from": ("禮部", 2), "col": 2, "person": "邊昇", "to": ("兵部", 1)},
        {"from": ("禮部", 2), "col": 3, "person": "方賓", "to": ("兵部", 1)},
        {"from": ("禮部", 2), "col": 4, "person": "盧淵", "to": ("兵部", 1)},
        {"from": ("兵部", 1), "col": 1, "person": "徐宗實", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 2, "person": "古樸", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 3, "person": "陳植", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 4, "person": "方賓", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 5, "person": "師逵", "to": ("兵部", 2)},
        {"from": ("兵部", 2), "col": 1, "person": "劉季篪", "to": ("刑部", 1)},
        {"from": ("刑部", 1), "col": 1, "person": "胡子昭", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 2, "person": "金有聲", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 3, "person": "金純", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 4, "person": "墨麟", "to": ("刑部", 2)},
        {"from": ("刑部", 2), "col": 1, "person": "黄福", "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": 2, "person": "張思恭", "to": ("工部", 1)},
        {"from": ("刑部", 3), "col": 1, "person": "黄福", "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": 2, "person": "張顯宗", "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": 3, "person": "金忠", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 1, "person": "練子寧", "to": ("御史中丞", 1)},
        {"from": ("工部", 1), "col": 2, "person": "陳瑛", "to": ("御史中丞", 1)},
        {"from": ("工部", 2), "col": 1, "person": "黄信", "to": ("御史中丞", 2)},
    ],
    # ── 706（洪武二十五年）：都察院 band1 右半条目被吸进工部 r3+列号误记
    706: [
        {"from": ("工部", 3), "col": 1, "person": "張廷蘭", "to": ("都察院", 1)},
        {"from": ("工部", 3), "col": 2, "person": "凌漢", "to": ("都察院", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "吴斌", "to": ("都察院", 1), "to_col": 3},
        {"from": ("都察院", 3), "col": 1, "person": "解敏", "to": ("都察院", 2), "to_col": 2},
    ],
    # ── 739（永乐廿二年）：C 型整页级联（geo 自第 3 条起晚一格；740 标签页对位）
    739: [
        {"from": ("吏部", 3), "col": 1, "person": "古樸", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 2, "person": "郭敦", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "李昶", "to": ("戶部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "李友直", "to": ("兵部", 1)},
        {"from": ("禮部", 2), "col": 2, "person": "孫時", "to": ("兵部", 1)},
        {"from": ("禮部", 3), "col": 1, "person": "崔衍", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 1, "person": "樊敬", "to": ("刑部", 1)},
        {"from": ("兵部", 2), "col": 1, "person": "張本", "to": ("刑部", 2)},
        {"from": ("兵部", 2), "col": 2, "person": "楊勉", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "李友直", "to": ("工部", 1)},
        {"from": ("刑部", 1), "col": 2, "person": "許廓", "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": 1, "person": "郭璡", "to": ("工部", 2)},
        {"from": ("刑部", 2), "col": 2, "person": "許廓", "to": ("工部", 2)},
        {"from": ("刑部", 2), "col": 3, "person": "楊和", "to": ("工部", 2)},
        {"from": ("刑部", 2), "col": 4, "person": "蔡信", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 1, "person": "虞謙", "to": ("都察院", 1)},
        {"from": ("工部", 1), "col": 2, "person": "陳勉", "to": ("都察院", 1)},
        {"from": ("工部", 2), "col": 1, "person": "李素", "to": ("都察院", 2)},
        {"from": ("工部", 2), "col": 2, "person": "胡廙", "to": ("都察院", 2)},
    ],
    # ── 759（正统九年）：C 型整页级联（与 760 共享网格；758 标签列直读）；
    #    鄺垫=鄺埜 OCR 名误（name_fix 随重挂）
    759: [
        {"from": ("吏部", 3), "col": 1, "person": "李暹", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 2, "person": "姜濤", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "王質", "to": ("戶部", 2)},
        {"from": ("戶部", 1), "col": 2, "person": "焦宏", "to": ("戶部", 2)},
        {"from": ("戶部", 1), "col": 3, "person": "劉璉", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "王英", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 2, "person": "侯璡", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "鄺垫", "to": ("兵部", 1),
         "to_person": "鄺埜"},
        {"from": ("兵部", 1), "col": 1, "person": "虞祥", "to": ("兵部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "薛希璉", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 2, "person": "楊寧", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 3, "person": "馬昂", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 4, "person": "丁鉉", "to": ("刑部", 2)},
        {"from": ("刑部", 2), "col": 1, "person": "黎澄", "to": ("工部", 1)},
        {"from": ("刑部", 3), "col": 1, "person": "李蕡", "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": 2, "person": "王永和", "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": 3, "person": "王佑", "to": ("工部", 2)},
        {"from": ("易州山廠提督", 2), "col": 1, "person": "張琦", "to": ("都察院", 1)},
        {"from": ("易州山廠提督", 2), "col": 2, "person": "丁璿", "to": ("都察院", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "王翱", "to": ("都察院", 2)},
        {"from": ("都察院", 1), "col": 2, "person": "曹翼", "to": ("都察院", 2)},
    ],
    # ── 771（景泰七年）：工部格——真趙榮挂刑部 r3；蒯祥 r1c2→r2（黎叔林/陸祥
    #    ENTRY_ADD 补；幻影趙榮条 SPURIOUS_SL 删）
    771: [
        {"from": ("刑部", 3), "col": 1, "person": "趙榮", "to": ("工部", 1)},
        {"from": ("工部", 1), "col": 2, "person": "蒯祥", "to": ("工部", 2)},
    ],
    # ── 777（天顺五年）：吴復工部 r3→山廠 r1
    777: [
        {"from": ("工部", 3), "col": 1, "person": "吴復", "to": ("易州山廠提督", 1)},
    ],
    # ── 785（成化五年）：C 型整页级联（geo 自吏部 r3 起下移一带）
    785: [
        {"from": ("吏部", 3), "col": 1, "person": "原傑", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "陳俊", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "萬安", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 2, "person": "邢讓", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "葉盛", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 2, "person": "劉吉", "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "李震", "to": ("兵部", 1)},
        {"from": ("禮部", 3), "col": 1, "person": "王偉", "to": ("兵部", 2)},
        {"from": ("禮部", 3), "col": 2, "person": "陳宜", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 1, "person": "曾翬", "to": ("刑部", 1)},
        {"from": ("兵部", 2), "col": 1, "person": "董方", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "李顒", "to": ("工部", 2)},
        {"from": ("刑部", 1), "col": 2, "person": "黎叔林", "to": ("工部", 2)},
        {"from": ("刑部", 2), "col": 1, "person": "霍瑄", "to": ("易州山廠提督", 1)},
        {"from": ("刑部", 2), "col": 2, "person": "王詔", "to": ("易州山廠提督", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "項忠", "to": ("都察院", 2)},
        {"from": ("都察院", 1), "col": 2, "person": "楊璿", "to": ("都察院", 2)},
    ],
    # ── 794（成化十四年）：萬祺工部 r3→山廠 r1（标签格首行）
    794: [
        {"from": ("工部", 3), "col": 1, "person": "萬祺", "to": ("易州山廠提督", 1)},
    ],
    # ── 798（成化十八年）：萬祺→山廠 r1；都察院程宗/李裕空 r1 槽下第二槽→r2
    798: [
        {"from": ("工部", 3), "col": 1, "person": "萬祺", "to": ("易州山廠提督", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "程宗", "to": ("都察院", 2)},
        {"from": ("都察院", 1), "col": 2, "person": "李裕", "to": ("都察院", 2)},
    ],
    # ── 801（成化廿一年）：C 型整页级联（同 739 型）；談倫→山廠 r1；
    #    屠滽 ENTRY_ADD（注被串进談倫 notes）
    801: [
        {"from": ("吏部", 3), "col": 1, "person": "李衍", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 2, "person": "孫仁", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "秦紘", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "徐溥", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "謝一夔", "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "阮勤", "to": ("兵部", 1)},
        {"from": ("兵部", 1), "col": 1, "person": "侯瓚", "to": ("兵部", 2)},
        {"from": ("兵部", 2), "col": 1, "person": "何喬新", "to": ("刑部", 1)},
        {"from": ("兵部", 2), "col": 2, "person": "杜銘", "to": ("刑部", 1)},
        {"from": ("兵部", 3), "col": 1, "person": "侣鍾", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "杜謙", "to": ("工部", 1)},
        {"from": ("刑部", 2), "col": 1, "person": "賈俊", "to": ("工部", 2)},
        {"from": ("刑部", 3), "col": 1, "person": "談倫", "to": ("易州山廠提督", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "馮貫", "to": ("都察院", 2)},
    ],
    # ── 806（弘治三年）：潘禮工部 r3→山廠 r1
    806: [
        {"from": ("工部", 3), "col": 1, "person": "潘禮", "to": ("易州山廠提督", 1)},
    ],
    # ── 814（弘治十一年）：林鳳/陳琬工部 r3→山廠 r1（标签列直读）
    814: [
        {"from": ("工部", 3), "col": 1, "person": "林鳳", "to": ("易州山廠提督", 1)},
        {"from": ("工部", 3), "col": 2, "person": "陳琬", "to": ("易州山廠提督", 1)},
    ],
    # ── 819（弘治十六年）：C 型级联（geo 自第 2 格起上移一格）；李士實(工部上行)
    #    实为李鐩（to_person）；張憲→山廠 r1；閻仲宇→都察院 r1
    819: [
        {"from": ("吏部", 3), "col": 1, "person": "王儼", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "顧佐", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "焦芳", "to": ("禮部", 1)},
        {"from": ("戶部", 2), "col": 2, "person": "李傑", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "李傑", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 2, "person": "王華", "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "熊肿", "to": ("兵部", 1),
         "to_person": "熊翀"},
        {"from": ("禮部", 3), "col": 1, "person": "熊繡", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 1, "person": "屠勲", "to": ("刑部", 1)},
        {"from": ("兵部", 2), "col": 1, "person": "李士實", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "李士實", "to": ("工部", 1),
         "to_person": "李鐩"},
        {"from": ("刑部", 2), "col": 1, "person": "張達", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 1, "person": "張憲", "to": ("易州山廠提督", 1)},
        {"from": ("易州山廠提督", 1), "col": 1, "person": "閻仲宇", "to": ("都察院", 1)},
    ],
    # ── 821（弘治十八年）：刑部格上下行拆错两半；張達/張憲工部 r1→r2
    821: [
        {"from": ("兵部", 3), "col": 1, "person": "屠勲", "to": ("刑部", 1)},
        {"from": ("兵部", 3), "col": 2, "person": "何鑑", "to": ("刑部", 1)},
        {"from": ("刑部", 1), "col": 1, "person": "李士實", "to": ("刑部", 2)},
        {"from": ("刑部", 1), "col": 2, "person": "魏紳", "to": ("刑部", 2)},
        {"from": ("工部", 1), "col": 1, "person": "張達", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 2, "person": "張憲", "to": ("工部", 2)},
    ],
    # ── 828（弘治二年）：戶部格 band1 两条挂吏部 r3、band2 三条上移 r1+col 顺延
    828: [
        {"from": ("吏部", 3), "col": 1, "person": "胡汝礪", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 2, "person": "儲瓘", "to": ("戶部", 1)},
        {"from": ("戶部", 1), "col": 1, "person": "孫交", "to": ("戶部", 2), "to_col": 2},
        {"from": ("戶部", 1), "col": 2, "person": "喬宇", "to": ("戶部", 2), "to_col": 3},
        {"from": ("戶部", 1), "col": 3, "person": "儲瓘", "to": ("戶部", 2), "to_col": 4},
    ],
    # ── 835（正德十年）：廖紀→山廠 r1；金獻民都察院 r1→r2（像素实测 r1 空置）
    835: [
        {"from": ("工部", 3), "col": 1, "person": "廖紀", "to": ("易州山廠提督", 1)},
        {"from": ("都察院", 1), "col": 1, "person": "金獻民", "to": ("都察院", 2)},
    ],
    # ── 838（正德十三年）：楊廷儀工部 r3→山廠 r1
    838: [
        {"from": ("工部", 3), "col": 1, "person": "楊廷儀", "to": ("易州山廠提督", 1)},
    ],
    # ── 841（正德十六年）：馮蘭/沈冬魁工部 r3→山廠 r1；劉玉 col 顺延（王懋中 ENTRY_ADD 后）
    841: [
        {"from": ("工部", 3), "col": 1, "person": "馮蘭", "to": ("易州山廠提督", 1)},
        {"from": ("工部", 3), "col": 2, "person": "沈冬魁", "to": ("易州山廠提督", 1)},
        {"from": ("都察院", 2), "col": 3, "person": "劉玉", "to": ("都察院", 2), "to_col": 4},
    ],
    # ── 847（嘉靖六年）：两薄行带各归后一格首带；禮部/工部第 2 带 4 条行号 1→2
    847: [
        {"from": ("戶部", 3), "col": 1, "person": "劉龍", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "翟鑾", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 2, "person": "桂萼", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 3, "person": "方獻夫", "to": ("禮部", 2)},
        {"from": ("禮部", 1), "col": 4, "person": "徐縉", "to": ("禮部", 2)},
        {"from": ("刑部", 3), "col": 1, "person": "童瑞", "to": ("工部", 1)},
        {"from": ("工部", 1), "col": 1, "person": "何天衢", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 2, "person": "閔楷", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 3, "person": "何詔", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 4, "person": "潘希曾", "to": ("工部", 2)},
    ],
    # ── 848（嘉靖七年）：何詔刑部 r3→工部 r1；工部 r1 四人→r2
    848: [
        {"from": ("刑部", 3), "col": 1, "person": "何詔", "to": ("工部", 1)},
        {"from": ("工部", 1), "col": 1, "person": "何詔", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 2, "person": "潘希曾", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 3, "person": "何瑭", "to": ("工部", 2)},
        {"from": ("工部", 1), "col": 4, "person": "黄衷", "to": ("工部", 2)},
    ],
    # ── 899（万历五年）：嚴清/申時行 col 顺延（陳炌 ENTRY_ADD 补 r2c1）
    899: [
        {"from": ("吏部", 2), "col": 1, "person": "嚴清", "to": ("吏部", 2), "to_col": 2},
        {"from": ("吏部", 2), "col": 2, "person": "申時行", "to": ("吏部", 2), "to_col": 3},
    ],
    # ── 918（万历二十二年）：工部 r3 两条为都察院 band1 误吸（詹沂同型）
    918: [
        {"from": ("工部", 3), "col": 1, "person": "劉東星", "to": ("都察院", 1)},
        {"from": ("工部", 3), "col": 2, "person": "王世揚", "to": ("都察院", 1)},
    ],
    # ── 943（万历四十七年）：稀疏页行带网格整体错位（7 条全改；944 注文铁证）
    943: [
        {"from": ("吏部", 1), "col": 1, "person": "史繼偕", "to": ("吏部", 2)},
        {"from": ("戶部", 1), "col": 1, "person": "李長庚", "to": ("戶部", 2)},
        {"from": ("戶部", 2), "col": 1, "person": "何宗彦", "to": ("禮部", 1)},
        {"from": ("禮部", 1), "col": 1, "person": "孫如游", "to": ("禮部", 2)},
        {"from": ("禮部", 2), "col": 1, "person": "楊應聘", "to": ("兵部", 1)},
        {"from": ("禮部", 3), "col": 1, "person": "祁光宗", "to": ("兵部", 2)},
        {"from": ("刑部", 1), "col": 1, "person": "林如楚", "to": ("工部", 2)},
    ],
    # ── 960（崇祯二年）：楊鶴/韓繼思工部 r3→都察院 r1（詹沂同型）
    960: [
        {"from": ("工部", 3), "col": 1, "person": "楊鶴", "to": ("都察院", 1)},
        {"from": ("工部", 3), "col": 2, "person": "韓繼思", "to": ("都察院", 1)},
    ],
    # ── 963（崇祯三年）：C 型级联（geo 自吏部 r2 起下移一衙）；王之菜→王之棻、
    #    程注→程註（to_person）
    963: [
        {"from": ("吏部", 1), "col": 1, "person": "曾楚卿", "to": ("吏部", 2)},
        {"from": ("吏部", 1), "col": 2, "person": "唐大章", "to": ("吏部", 2)},
        {"from": ("吏部", 2), "col": 1, "person": "康新民", "to": ("戶部", 1)},
        {"from": ("吏部", 3), "col": 1, "person": "劉重慶", "to": ("戶部", 2)},
        {"from": ("吏部", 3), "col": 2, "person": "周士樸", "to": ("戶部", 2)},
        {"from": ("禮部", 1), "col": 1, "person": "王之菜", "to": ("兵部", 2),
         "to_person": "王之棻"},
        {"from": ("禮部", 1), "col": 2, "person": "范景文", "to": ("兵部", 2)},
        {"from": ("兵部", 1), "col": 1, "person": "涂國鼎", "to": ("刑部", 1)},
        {"from": ("兵部", 2), "col": 1, "person": "程注", "to": ("刑部", 2),
         "to_person": "程註"},
    ],
    # ── 972（崇祯十一年）：吏部格单带双条——鍾炌 r2→r1、董羽宸 col 1→2
    972: [
        {"from": ("吏部", 2), "col": 1, "person": "鍾炌", "to": ("吏部", 1)},
        {"from": ("吏部", 1), "col": 1, "person": "董羽宸", "to": ("吏部", 1), "to_col": 2},
    ],
    # ── 868（嘉靖二十七年）：兵部 band2 左位幻影「張岳」实为范鏗（to_person）
    868: [
        {"from": ("兵部", 2), "col": 1, "person": "張岳", "to": ("兵部", 2),
         "to_person": "范鏗"},
    ],
}

# 整页实拍核验通过、geo 归属全部正确的 band 警报页（2026-11-15 侍郎核验小轮）：
# 页内条目 pending 清除（official_shilang 判断），BOOK_FIX 不涉及的条目视为核验确认。
# 823（正德元年）：6 条注文与原书逐字一致，警报仅行带越界 16px 几何噪声；
# 930（萬曆卅四年）：除詹沂（走 BOOK_FIX）外其余 6 条与原书一致。
VERIFIED_PAGES: set[int] = {823, 930}

# 跨页残留：geo 把前页山廠带复制到了后页。
# （2026-11-15 撤销 760 两条：批3/主会话实拍复核证明 丁璿/程富 是 760 都察院
# r1/r2 真条目，非跨页残留——见 _scratch/shilang/verify_batch/verdicts/b760.json）
SPURIOUS: set[tuple[int, str, str]] = set()

# 精确删除（2026-11-15 侍郎核验批量轮）：旧 3 元组键 (book,office,person) 无法区分
# 同页同名多挂（如 899 何維柏真条目 vs x157,y239 幽灵重复），升级为 dict 列表；
# xy 给出时须坐标全等才删，缺省匹配 (office,row,col,person)。
SPURIOUS_SL: list[dict] = [
    # ── 899（万历五年）：geo 吏部区幽灵两条
    {"book": 899, "office": "吏部", "row": 1, "col": 1, "person": "何維柏",
     "xy": (157, 239), "reason": "同人重复收录，x118,y221 为真条目"},
    {"book": 899, "office": "吏部", "row": 3, "col": 1, "person": "陳炌",
     "reason": "吏部块仅两带，r3 无实位"},
    # ── 970（崇祯十年）：工部两条幽灵（原书上行仅蔡國用、下行 c1 实为鍾炌）
    {"book": 970, "office": "工部", "row": 1, "col": 2, "person": "蔡奕琛",
     "reason": "原书工部上行无此名（蔡奕琛两条均在刑部格）"},
    {"book": 970, "office": "工部", "row": 2, "col": 1, "person": "蔡國用",
     "reason": "下行c1实为鍾炌（ENTRY_ADD 新增），此空注条目应删"},
    # ── 821（弘治十八年）：李士實 y856 注文行幽灵（notes 空，原书仅下行c1一处）
    {"book": 821, "office": "刑部", "row": 2, "col": 1, "person": "李士實",
     "xy": None, "reason": "y856 为李士實注文行生成的幽灵条目"},
    # ── 965（崇祯五年）：戶部 r3c1 人名「遷左」＝注尾+续行拼成的残行
    {"book": 965, "office": "戶部", "row": 3, "col": 1, "person": "遷左",
     "reason": "周士樸注尾与傅淑訓/劉榮嗣/蔡思充注续行拼接的幽灵条目"},
    # ── 828（弘治二年）：戶部 r1c1 无注胡汝礪幻影（x277,y398＝陳勗注文块位置，
    #    真条目在吏部 r3c1 x231,y357 带注）
    {"book": 828, "office": "戶部", "row": 1, "col": 1, "person": "胡汝礪",
     "xy": (277, 398), "reason": "陳勗注文位置生成的无注幻影条目"},
]

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
                if rule.get("person") is not None and e.get("person") != rule["person"]:
                    continue
                e["_to_office"] = rule["to"]
                e["_to_row"] = rule["to_row"] if "to_row" in rule else rule["to"][1]
                if rule.get("to_col") is not None:
                    e["_to_col"] = rule["to_col"]
                if rule.get("to_person") is not None:
                    e["_to_person"] = rule["to_person"]
                break
        for e in out:
            if "_to_office" in e:
                e["office_fix"] = {"from_office": e["office"], "from_row": e["row"],
                                   "to_office": e["_to_office"], "to_row": e["_to_row"],
                                   "source": f"原书核验 p{book}"}
                e["office"] = e.pop("_to_office")[0]
                e["row"] = e.pop("_to_row")
                if "_to_col" in e:
                    e["col"] = e.pop("_to_col")
                if "_to_person" in e:
                    e["name_fix"] = {"from": e["person"], "to": e["_to_person"]}
                    e["person"] = e.pop("_to_person")
                moved += 1

    before = len(out)
    out = [e for e in out
           if (e["book"], e["office"], e["person"]) not in SPURIOUS
           or e.get("office_fix")]
    rep["book_fix"] = {"moved": moved, "removed": before - len(out),
                       "pages": sorted(BOOK_FIX)}
    return out


# OCR 人名异写归一（2026-11-13 抽查轮）：佀鍾（1440–1511，鄆城人，弘治間戶右侍
# 督倉場→吏右→吏左）在 p810/p811/p812/p813 三形并存——「侣鍾」「倡鍾」皆 ⿰亻吕
# 之 OCR 误识，《明史》无「倡鍾/侣鍾」。全局归一（不按年键），CBDB 按佀鍾连上。
NAME_CANON: dict[str, str] = {
    "侣鍾": "佀鍾",
    "倡鍾": "佀鍾",
    # 2026-11-15 批量轮：geo 简繁/字形混写归一（匹配统一按规范繁体）
    "吴一鹏": "吳一鵬",
    "黄珂": "黃珂",
    "蒋勉": "蔣勉",
    "熊浃": "熊浹",
    # 2026-11-16 转录型试点轮（bT）
    "胡淡": "胡濙",
    "郝鹏": "郝鵬",
    "費菜": "費宷",
    "李鏞": "李鑴",
    # 2026-11-16 Paddle 对照批量轮（bV）：字形异写
    "余立": "佘立",
    "張鑒": "張鎣",
    "魏骥": "魏驥",
}


def apply_name_canon(entries: list[dict], report: dict | None = None) -> list[dict]:
    rep = report if report is not None else {}
    n = 0
    for e in entries:
        canon = NAME_CANON.get(e.get("person") or "")
        if canon:
            e["name_fix"] = {"from": e["person"], "to": canon}
            e["person"] = canon
            n += 1
    rep["name_canon"] = {"renamed": n}
    return entries


# ── 原书补录（2026-11-15 侍郎核验批量轮）：原书实存而 geo 整条漏收的条目。
# year/era 在应用时从同页任一既有条目复制；notes 直接给原书注文。
ENTRY_ADD_SL: dict[int, list[dict]] = {
    # 821（弘治十八年）：工部格上行 c1 李鐩（无注）——孤儿注「李」归入
    821: [{"office": "工部", "row": 1, "col": 1, "person": "李鐩", "notes": []}],
    # 970（崇祯十年）：鍾炌两条——吏部上行 c2 / 工部下行 c1（同日互证 4/22）
    970: [{"office": "吏部", "row": 1, "col": 2, "person": "鍾炌",
           "notes": ["四、辛卯、廿二，工右侍遷。"]},
          {"office": "工部", "row": 2, "col": 1, "person": "鍾炌",
           "notes": ["四、辛卯、廿二，遷吏左侍。"]}],
    # 739（永乐廿二年）：刑部下行 c3 吳廷用——名字被吞进楊勉 notes 首段
    739: [{"office": "刑部", "row": 2, "col": 3, "person": "吳廷用",
           "notes": ["九、己丑、十七，戶給遷，歸省。宣德十年七、戊戌、廿九，遷禮左侍。"]}],
    # 771（景泰七年）：工部下行 黎叔林（在任无注）/陸祥（长履历注＝幻影趙榮条所挂）
    771: [{"office": "工部", "row": 2, "col": 1, "person": "黎叔林", "notes": []},
          {"office": "工部", "row": 2, "col": 2, "person": "陸祥",
           "notes": ["七、甲午、廿七，太僕少遷，仍督工匠。天順元年二、乙未、一，降太僕少，尋復。",
                     "成化二年七、甲戌、十七，遷工左侍。", "成化五年十二、辛亥、二，卒。"]}],
    # 801（成化廿一年）：都察院下行 c1 屠滽——注被串进談倫 notes
    801: [{"office": "都察院", "row": 2, "col": 1, "person": "屠滽",
           "notes": ["七、甲戌、廿六，遷右都。"]}],
    # 841（正德十六年）：兵部上行 c3 李鉞 / 都察院下行 c3 王懋中（劉玉顺延 col4）
    841: [{"office": "兵部", "row": 1, "col": 3, "person": "李鉞",
           "notes": ["六、辛丑、廿一，右侍遷。"]},
          {"office": "都察院", "row": 2, "col": 3, "person": "王懋中",
           "notes": ["十一、壬戌、十四，南右副都改督江務。"]}],
    # 899（万历五年）：吏部下行 c1 陳炌——注「遷左」现误挂何維柏
    899: [{"office": "吏部", "row": 2, "col": 1, "person": "陳炌",
           "notes": ["十一、戊午、六，遷左。"]}],
    # 847（嘉靖六年）：戶部下行 c2 王軏——注被并入王承裕条
    847: [{"office": "戶部", "row": 2, "col": 2, "person": "王軏",
           "notes": ["五、辛巳、五，南刑右侍改。"]}],
    # 960（崇祯二年）：兵部 4 条——名与注被并入申用懋/熊明遇 notes（批5 verdict
    # + 主会话 crop960_bingbu2/3 实拍拆注）
    960: [{"office": "兵部", "row": 1, "col": 2, "person": "唐世濟",
           "notes": ["三、辛未、十五，罷。", "五年六、己卯、十三，起遷南右都。"]},
          {"office": "兵部", "row": 1, "col": 3, "person": "程正己",
           "notes": ["三、己卯、廿三，右侍遷。"]},
          {"office": "兵部", "row": 2, "col": 2, "person": "程正己",
           "notes": ["三、己卯、廿三，遷左。"]},
          {"office": "兵部", "row": 2, "col": 3, "person": "魏雲中",
           "notes": ["是年，起撫寧夏右僉都遷添設；", "九、戊申、廿七，遷兵尚兼右副都總宣大。"]}],
    # 965（崇祯五年）：戶部下行 c4/c5 + 兵部下行 c3（crop965_hubu 实拍拆注）
    965: [{"office": "戶部", "row": 2, "col": 4, "person": "劉榮嗣",
           "notes": ["九、己酉、十四，順天府尹遷理錢法。"]},
          {"office": "戶部", "row": 2, "col": 5, "person": "蔡思充",
           "notes": ["十二、己巳、六，南太常卿遷。"]},
          {"office": "兵部", "row": 2, "col": 3, "person": "劉宇烈",
           "notes": ["三、壬寅、五，督理更調薊門川兵及青州兵馬，尋遣戍。"]}],
}

# 注文修复（原书注文错粘/串行/残片）：notes 全量重写（notes=...）或剥离子串（strip）。
NOTE_FIX: list[dict] = [
    # 970：田維嘉注剥离鍾残片与鍾炌吏部注；蔡國用名下实无注
    {"book": 970, "office": "吏部", "row": 1, "col": 1, "person": "田維嘉",
     "notes": ["三、乙巳、六，遷吏尚。"]},
    {"book": 970, "office": "工部", "row": 1, "col": 1, "person": "蔡國用",
     "notes": []},
    # 841：楊廷儀注剥离「李」残片与李鉞注；王時中剥离王懋中注碎片；李瓚注尾残片
    {"book": 841, "office": "兵部", "row": 1, "col": 2, "person": "楊廷儀",
     "notes": ["五、甲子、十三，右侍遷。", "六、庚寅、十，劾罷。",
               "嘉靖十九年十、戊辰、九，卒。"]},
    {"book": 841, "office": "都察院", "row": 2, "col": 2, "person": "王時中",
     "notes": ["五、丙寅、十五，撫寧夏右僉都遷。", "十、丙申、十八，歸省。",
               "嘉靖三年二、庚子、五，復原職。"]},
    {"book": 841, "office": "都察院", "row": 1, "col": 2, "person": "李瓚",
     "strip": "王懋中"},
    # 801：談倫注剥离屠滽注串行
    {"book": 801, "office": "易州山廠提督", "row": 1, "col": 1, "person": "談倫",
     "strip": "七、甲戌、廿六，遷右都。"},
    # 899：何維柏（真条目）注剥离陳炌「遷左」注
    {"book": 899, "office": "吏部", "row": 1, "col": 1, "person": "何維柏",
     "strip": "十一、戊午、六，遷左。"},
    # 828：吏部r3c1 胡汝礪注——原书仅「正、己未、廿六，改兵左侍」，
    # 陳勗两行注被误并（批6 verdict）；陳勗条目注文拆回归位
    {"book": 828, "office": "吏部", "row": 3, "col": 1, "person": "胡汝礪",
     "notes": ["正、己未、廿六，改兵左侍。"]},
    {"book": 828, "office": "戶部", "row": 2, "col": 1, "person": "陳勗",
     "notes": ["十二、庚子、十三，進戶左侍致仕。",
               "五年九、壬午、廿九，起復總糧儲戶左侍。"]},
    # 868：張岳注剥离范鏗「遷左」注（批6 verdict）；范鏗（to_person 重挂后）赋注
    {"book": 868, "office": "兵部", "row": 1, "col": 1, "person": "張岳",
     "notes": ["六、丁未、四，兼右都總廣西貴州。"]},
    {"book": 868, "office": "兵部", "row": 2, "col": 1, "person": "范鏗",
     "notes": ["十、戊辰、廿七，遷左。"]},
    # 960：申用懋/熊明遇注剥离被吞三名注文（crop960_bingbu2/3 实拍拆注）
    {"book": 960, "office": "兵部", "row": 1, "col": 1, "person": "申用懋",
     "notes": ["五、乙酉、一，加右都；", "十一、乙巳、廿四，遷兵尚。"]},
    {"book": 960, "office": "兵部", "row": 2, "col": 1, "person": "熊明遇",
     "notes": ["三、己卯、廿三，遷兵左侍添設。"]},
    # 965：傅淑訓注剥离劉榮嗣/蔡思充名残片；楊一鵬注剥离劉宇烈残片+「卜」→「十」；
    # 周士樸 r2c2 注截断补全（crop965_hubu 实拍）
    {"book": 965, "office": "戶部", "row": 2, "col": 3, "person": "傅淑訓",
     "notes": ["九、己酉、十四，通政使遷。"]},
    {"book": 965, "office": "戶部", "row": 2, "col": 2, "person": "周士樸",
     "notes": ["九、己酉、十四，遷左。"]},
    {"book": 965, "office": "兵部", "row": 1, "col": 2, "person": "楊一鵬",
     "notes": ["三、丁未、十，工右侍遷；", "七、癸亥、廿七，署部事。"]},
]


def apply_entry_add(entries: list[dict], report: dict | None = None) -> list[dict]:
    """原书补录：ENTRY_ADD_SL 页级新增条目（year/era 从同页复制，pf=book-add 溯源）。"""
    rep = report if report is not None else {}
    by_book: dict[int, list[dict]] = {}
    for e in entries:
        by_book.setdefault(e["book"], []).append(e)
    added = 0
    out = list(entries)
    for book, items in ENTRY_ADD_SL.items():
        srcs = by_book.get(book)
        if not srcs:
            continue
        year, era = srcs[0].get("year"), srcs[0].get("era")
        for it in items:
            e = {"book": book, "year": year, "era": era, "office": it["office"],
                 "office_raw": it["office"], "row": it["row"], "col": it["col"],
                 "person": it["person"], "tag": None, "inline_note": None,
                 "notes": list(it.get("notes") or []), "x": None, "y": None,
                 "flags": [], "pf": "book-add"}
            out.append(e)
            added += 1
    rep["entry_add"] = {"added": added, "pages": sorted(ENTRY_ADD_SL)}
    return out


def canon_person(name):
    """person 字串 NAME_CANON 归一（比对双侧统一用）。"""
    return NAME_CANON.get(name, name)


def apply_spurious_sl(entries: list[dict], report: dict | None = None) -> list[dict]:
    """精确删除：SPURIOUS_SL 按 (office,row,col,person) 匹配（person 双侧 NAME_CANON
    归一后比对）；xy 给出时须坐标全等。须在 book_fix 重挂之前应用（geo 原始键）。"""
    rep = report if report is not None else {}
    out = []
    removed = 0
    for e in entries:
        hit = None
        e_person = canon_person(e.get("person"))
        for s in SPURIOUS_SL:
            if (e["book"] == s["book"] and e["office"] == s["office"]
                    and e["row"] == s["row"] and e["col"] == s["col"]
                    and e_person == canon_person(s["person"])):
                if s.get("xy") is not None and (e.get("x"), e.get("y")) != tuple(s["xy"]):
                    continue
                hit = s
                break
        if hit:
            e["spurious_fix"] = {"reason": hit["reason"], "source": f"原书核验 p{e['book']}"}
            removed += 1
        else:
            out.append(e)
    rep["spurious_sl"] = {"removed": removed}
    return out


def apply_note_fix(entries: list[dict], report: dict | None = None) -> list[dict]:
    """注文修复：NOTE_FIX 按 (office,row,col,person) 精确匹配——notes 全量重写或剥离子串。"""
    rep = report if report is not None else {}
    n = 0
    for e in entries:
        for f in NOTE_FIX:
            if (e["book"] == f["book"] and e["office"] == f["office"]
                    and e["row"] == f["row"] and e["col"] == f["col"]
                    and e.get("person") == f["person"]):
                if "notes" in f:
                    e["note_fix"] = {"from": e.get("notes"), "to": f["notes"]}
                    e["notes"] = list(f["notes"])
                if "strip" in f:
                    ns = [s.replace(f["strip"], "").strip("；; ") for s in (e.get("notes") or [])]
                    ns = [s for s in ns if s]
                    e["note_fix"] = {"strip": f["strip"]}
                    e["notes"] = ns
                n += 1
                break
    rep["note_fix"] = {"applied": n}
    return entries


# ══ 2026-11-15 侍郎 band 核验批量轮（批2/7-12 编译注入）══
# 数据模块由 compile_verdicts.py 从 verdicts/*.json 生成（geo 键校验零跳过），
# 与上方手写常量合并应用；应用顺序见 official_shilang.load_shilang_repaired：
# spurious → name_canon → book_fix → entry_add → note_fix
from mingoff.shilang_verify_fixes import (BOOK_FIX_BATCH, ENTRY_ADD_BATCH,  # noqa: E402
                                          NOTE_FIX_BATCH, SPURIOUS_BATCH)

for _book, _rules in BOOK_FIX_BATCH.items():
    BOOK_FIX.setdefault(_book, []).extend(_rules)
for _book, _items in ENTRY_ADD_BATCH.items():
    ENTRY_ADD_SL.setdefault(_book, []).extend(_items)
SPURIOUS_SL.extend(SPURIOUS_BATCH)
NOTE_FIX.extend(NOTE_FIX_BATCH)
