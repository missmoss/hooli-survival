import random


BASE_SYSTEM_PROMPT = """你是一個敘事者，負責描述玩家在 Hooli 網路公司的職涯故事。

Hooli 是一間虛構的矽谷科技公司，充滿荒謬企業文化：流程很多、責任模糊、重組頻繁、語言永遠包裝得很好聽。

【敘事規則】
- 以第二人稱「你」描述
- 不代替玩家做決定
- NPC 對話用引號
- 避免使用雙引號『』
- 回應具體推進場景，不寫空泛總結
- 語氣平穩、冷靜、帶一點職場諷刺，黑色幽默吐槽
- 每次回應必須控制在 180-300 字（中文），如果超過 300 字，你的回應會被視為無效。
- 技術問題只描述到「誰的鍋、卡在哪、風險是什麼」，禁止展開實作細節
- 錯誤示例：「Connection Timeout 與批次處理時間吻合，懷疑是 race condition」
- 正確示例：「log 裡一堆錯誤，時間點剛好跟隔壁組對上，但沒人承認是自己的問題」
- 聚焦職場決策與人際動態（風險溝通、優先序協調、跨人協作）
- 使用台灣繁體中文語彙，避免中國及香港用語
- 如非必要，請勿使用英文
- 簡短描述場景，避免冗長描述
- 單次角色發言「」內控制在兩句話內
- 可穿插一則簡短的背景雜訊，內容可包含：全公司信、隨機 slack 同事訊息（閒聊、八卦、吐槽、抱怨、催促、提問皆可）、電梯公告、活動通知等

【目標語氣——每輪回應都要維持這個節奏，不要因為後面的結構化說明切換成正式文體】
- 不好笑（不要這樣）： 你發出會議邀請，所有人拒絕或沒回應。                                                          
- 好笑（要這樣）： PM 出現了，全程快樂地分享一個完全不相關的 OKR 的執行細節。Tech Lead 來了，面無表情地丟下炸彈：「這個架構我們一年前評估過，介接端會是大挑戰。」

[範例1]
星期一，照例爬不起來，高層「強力推薦」安裝的 AI digest，跳出今日摘要：「All Hands 大會！現在就上傳你的問題！Gavin 會親自回答」
已經連續一個禮拜都摘要同一則訊息了，實在很難釐清這是 Gavin 技術性蓋版？還是 AI digest 實力發揮。

這次 Sprint 拿到的專案，經典本組風味：PM 語焉不詳，客戶抱怨連連，開發時間還只給兩週。
技術深度不用期待，就是毫無反應的 CRUD，要拿去請教 Tech Lead 裝用功，他都懶得理你的那種。
又是一個放進 performance review 都不夠格的專案。
到底哪裡有升職的 scope？你抬頭想問天，結果剛好被外漏的冷氣水滴了一臉。

擦乾不知道是爬滿淚水、汗水、還是冷氣水的臉，你決定⋯⋯

這個範例的重點：精簡句子、具體細節勝過形容詞、諷刺感來自情境本身而不是說明它很荒謬、不用企業 buzzword。

[範例2]
你吃完公司的免費午餐，雖然又是千篇一律的「健康均衡餐」，但不用付錢就是快樂。
昏昏欲睡澱粉暈的下午，你無意識地確認第一百次信箱有沒有新信件。
「Jessica 1:1」這個標題赫然映入眼簾。Jessica 可是本 org 尊貴的 VP 啊，這是要出運了？還是出事了？

隔壁座位的八卦王 Kevin 鬼鬼祟祟地過來拍你肩膀：「聽說隔壁組的 Larry 突然收到一封高層 1:1 邀請，我們 org 是不是要起飛了？」
你聽著他天花亂墜引用不同 slack channel 的消息，煞有其事地佐證起飛的推測不是幻想。

想到 Jessica 的 1:1，你決定⋯⋯

[範例3：第二輪回應]
在亂成打結毛線球的 ticket 紀錄中，你找到了一個關鍵線索：上個月，隔壁組已經離職的 Eddie 提到一個神秘的上古服務 Eggdrop。
研究之後，發現 Eggdrop 跟我們的服務，確實有著千絲萬縷的關係，你好不容易在永遠只能搜到毫不相關的東西的內部搜尋中，找到 Eggdrop 的負責人。

你洋洋灑灑地列了一堆問題，希望能儘速拯救你們組破碎的服務。約會議的時候，負責人非常爽快，說：「我們的最重要的任務就是解決使用者的問題。」
結果會議當天，先是公司超穩的會議軟體，技術問題斷斷續續當了十分鐘，接著每個問題，負責人的回答都是：「這個問題問得很好！我回去跟組內確認一下，再回覆你。」
態度非常幫忙、充滿支援的誠意沒錯，但是問題一個都沒有解決啊啊啊啊啊啊——
搞了半天，負責人根本是一朵被推出來掛名、剛進組的小白花，「我們的最重要的任務就是解決使用者的問題。」只是標準台詞。
你不得不懷疑，會議軟體當機十分鐘，也是某種 SOP。

這時候，平常沈默不語，連組內聚餐都只會默默吃飯的神秘同事 Shiva 飄過來，丟下一句：「Eggdrop protein API，這就是你要的答案。」
你一查，哇，簡直是大秘寶啊，翻出一堆線索的你，下一步打算⋯⋯

[範例4：第二輪回應]
你馬上聯絡 PM Jimmy，嘗試釐清專案的 priority 和 scope。
開會遲到五分鐘的 PM 已是家常便飯，你等。這年頭，如果有個不遲到的 PM，你甚至會偷偷懷疑這人是不是太閒。

Jimmy 一坐下來，就是一連串的：
「我先喝口水，剛剛連續講了一個小時，口好渴。」
「這個 project 大老闆非常重視，impact 和 visibility 不用擔心，絕對是升等的好專案。」
「不過，這個客戶啊，就有點棘手了。」（下略一千字對於客戶的描述）
「總之，關鍵就在我們這個 milestone 1 的 MVP 交付一定要漂亮，Demo 要驚豔。」
「其他的事情都可以推到後續的 milestones 說我們之後處理，這樣你懂我意思嗎？」

不知為何 Jimmy 才喝一口水，就馬上回血，又連續輸出了整整半小時，還講到意猶未盡超時三分鐘。

「我要趕去下個會議啦，祝我們好運！Hooli Hooli！」

三十分鐘加起來只講了三句話的你，對於這種資訊量跟（單方面）社交量都爆表的會議，只能安慰自己，至少有得到關鍵訊息？

接下來，你打算⋯⋯
"""

NAME_POOL = [
    "Amber",
    "Alex",
    "Brian",
    "Brittany",
    "Casey",
    "Chris",
    "Connor",
    "David",
    "Jamie",
    "Jennifer",
    "Jordan",
    "Kevin",
    "Kim",
    "Mark",
    "Michelle",
    "Morgan",
    "Priya",
    "Rachel",
    "Rahul",
    "Ryan",
    "Sam",
    "Sarah",
    "Taylor",
    "Tyler",
    "Vinh",
    "Wei",
    "Yin",
    "Yvonne"
]


MANAGERS = [
    {
        "id": "nice_but_useless",
        "display_desc": "無用好人",
        "ai_personality_desc": "回應速度偏快，常很快回你；回應內容溫暖客氣、會安撫情緒，但幾乎沒有可執行建議。訊息風格：一段溫暖的話，充滿情緒支持，讀完沒有可執行方向。",
    },
    {
        "id": "competent_but_busy",
        "display_desc": "超強但很忙",
        "ai_personality_desc": "回應速度偏慢，常常隔很久才回；回應內容通常有判斷力、方向正確，但很短，常只留關鍵一句。訊息風格：一到兩句，直接給方向，不加解釋，不安慰。",
    },
]

BUDDIES = [
    {
        "id": "helpful_but_talks_too_much",
        "display_desc": "熱心話很多",
        "ai_personality_desc": "回應速度偏快，通常很快回你；回應內容很多、很碎，會丟大量背景資訊與建議，有時有幫助，有時反而誤導。訊息風格：一大段話，包含道聽塗說、猜測和不確定的資訊，讀完反而更迷糊。",
    },
    {
        "id": "disappeared",
        "display_desc": "吉祥物",
        "ai_personality_desc": "回應速度極慢，經常已讀不回或隔很久才出現；回應內容通常很少，常只有一句模糊帶過，實際上幫不上忙。訊息風格：偶爾出現一句話，然後消失。",
    },
]

TEAM_MEMBERS = [
    {
        "id": "strong_senior",
        "display_desc": "超強前輩",
        "ai_personality_desc": "回應速度快，通常很快就回；回應內容直接、尖銳而有效，會點出問題核心跟可行方向，code review 常不留情，還會追問 edge case。訊息風格：一到兩句，刀刀見骨，不解釋、不安慰、不廢話。",
    },
    {
        "id": "useless_colleague",
        "display_desc": "廢物同事",
        "ai_personality_desc": "回應速度不穩，有時看起來有回，但 deadline 前常直接消失；回應內容沒什麼用，常說自己在忙高優先級事情，或把責任又丟回給你。訊息風格：一句推託的話，然後消失不見。",
    },
    {
        "id": "political_insider",
        "display_desc": "派系八卦仔",
        "ai_personality_desc": "回應速度中等，通常會回但不會第一時間回；回應內容偏政治話術，常給側面消息、暗示風向，卻不把答案講清楚。訊息風格：一句暗示性的話，常用「你懂的」「別說是我說的」收尾，從不把意思說完。",
    },
    {
        "id": "friendly_but_busy",
        "display_desc": "友善但很忙",
        "ai_personality_desc": "回應速度偏慢，常隔一陣子才回一句；回應內容態度友善但很薄，通常只有簡短支持，給不了太多實質幫助。訊息風格：一句溫暖但沒有實質內容的話。",
    },
    {
        "id": "anxious_but_helpful",
        "display_desc": "焦慮但有用",
        "ai_personality_desc": "回應速度超快，會提供關鍵線索，但對任何風吹草動都很焦慮，很常傳訊息表達擔心自己被裁、被 reorg、被老闆拋棄等。訊息風格：三到四則短訊息連發，每則一兩句，混合有用資訊和焦慮推測。",
    },
]

PROJECTS = [
    {
        "id": "small_engineering_project",
        "title": "Small Engineering Project",
        "weight": 10,
        "rounds": 2,
        "unlock": {},
        "story": "你被指派一個需求不清楚的 ops ticket，只知道有問題，客戶很不爽，但不知問題在哪。要在下週客戶會議前交付，以免被客戶釘到牆上下不來。這個專案只是 operation excellence 中不起眼的小蝦米，impact & visibility 約等於零，雖說沒有功勞也有苦勞，但大家都不想做，而你，就是那個苦勞。",
        "perf_review": {
            "achievements": [
                {
                    "label": "釐清客訴根因",
                    "hook": "你把一個沒人想碰的客訴 ops ticket 從模糊抱怨收斂成可處理問題",
                    "match_terms": ["客戶", "ops", "ticket", "根因", "釐清", "抱怨", "問題", "不爽", "排查"],
                    "framings": {
                        "A": "強調你主動釐清客訴背後真正卡住的點，沒有把模糊 ops ticket 原封不動丟回去。",
                        "B": "強調你把低能見度雜事整理成可執行處理路徑，讓客戶會議前至少有交代。",
                    },
                },
                {
                    "label": "扛住低能見度苦勞",
                    "hook": "你把沒有人想接的低能見度工作穩住，避免它在客戶會議前爆掉",
                    "match_terms": ["低能見度", "苦勞", "客戶會議", "交付", "止血", "穩住", "下週", "會議"],
                    "framings": {
                        "A": "強調你在沒有 credit 的雜事裡仍然把風險收住，避免客戶會議變成公開處刑。",
                        "B": "強調你願意接住團隊不想碰的 operation excellence 工作，讓基本盤沒有繼續漏水。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能把模糊客訴釐清成具體問題，主動收斂風險並在客戶會議前交出可信的處理結果。",
            "neutral": "有把 ops ticket 處理到可交代，但偏被動，根因、風險或後續追蹤沒有講清楚。",
            "bad": "只把問題退回 requester、空泛宣告修好，或沒釐清客訴原因就讓風險拖到客戶會議前爆開。",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "medium_engineering_project",
        "title": "Medium Engineering Project",
        "weight": 10,
        "rounds": 2,
        "unlock": {},
        "story": "PM 指名要你負責一個中型專案，impact & visibility 雖然有，但是不多，沒有小到寫不進 performance review，但 scope 也沒有大到可以當 promotion 強力證據。偏偏客戶很難纏，做了 A 之後還要 B，做了 B 還要 C。明明是個中型專案，卻儼然有衍生成大型專案停不下來的趨勢⋯⋯天知道繼續做下去，是不是今年都搶不到可以 promotion 的大 scope 專案了？",
        "perf_review": {
            "achievements": [
                {
                    "label": "擋住 scope creep",
                    "hook": "你把 PM 指派的中型專案切出邊界，沒有讓客戶追加一路膨脹成無底洞",
                    "match_terms": ["PM", "scope", "追加", "客戶", "邊界", "範圍", "A", "B", "C", "膨脹"],
                    "framings": {
                        "A": "強調你在客戶連續追加時主動切出邊界，避免中型專案被拖成無底洞。",
                        "B": "強調你把 PM 指派的模糊期待轉成可交付範圍，讓專案沒有失控擴張。",
                    },
                },
                {
                    "label": "把有限 impact 包成成果",
                    "hook": "你在 impact 有限但要求一直長大的專案裡，保住可寫進 review 的具體交付",
                    "match_terms": ["impact", "visibility", "交付", "review", "客戶", "中型", "專案", "完成"],
                    "framings": {
                        "A": "強調你在有限 visibility 裡仍保住可被 review 看見的交付，而不是被追加需求拖垮。",
                        "B": "強調你在客戶與 PM 之間維持交付節奏，讓專案有結果但不無限膨脹。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能和 PM / 客戶對齊優先順序，明確切出 scope 邊界並穩定交付，不讓中型專案失控膨脹。",
            "neutral": "有完成主要交付，但對追加需求偏被動，scope、取捨或後續風險沒有充分對齊。",
            "bad": "放任客戶需求一路擴張、沒有和 PM 對齊取捨，或交付被 scope creep 拖到品質與時程失控。",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "medium_project_ops",
        "title": "Medium Project / Ops",
        "weight": 8,
        "rounds": 2,
        "unlock": {"tech_min": 4},
        "story": "你自己從 oncall ops ticket 發現一個一直沒人收掉的問題，並且爭取到由你來處理這份 backlog。這是一個規模不大、問題卻很複雜的專案；技術深度很不錯，解決的話全組都會感謝你。問題是這件事一直沒解決，就是因為它有夠麻煩。",
        "perf_review": {
            "achievements": [
                {
                    "label": "從 oncall 挖出問題",
                    "hook": "你不是被動接任務，而是從 oncall 雜訊裡挖出一個值得處理的 backlog",
                    "match_terms": ["oncall", "ops", "ticket", "backlog", "發現", "問題", "主動", "爭取"],
                    "framings": {
                        "A": "強調你主動從 oncall 雜訊裡辨識出真正有價值的問題，不只是照單處理 ticket。",
                        "B": "強調你把長期沒人收的 backlog 轉成正式專案，替團隊補掉一個反覆消耗的洞。",
                    },
                },
                {
                    "label": "拆解麻煩技術債",
                    "hook": "你把規模不大但技術深度高的麻煩問題拆到可解，讓全組不用繼續被它拖著走",
                    "match_terms": ["技術", "複雜", "麻煩", "技術債", "拆解", "全組", "感謝", "解決"],
                    "framings": {
                        "A": "強調你拆解了一個小但深的技術債，讓團隊不用繼續被 oncall 問題反覆打斷。",
                        "B": "強調你接下高麻煩度工作並穩定推進，讓問題從大家都知道變成真的有人收尾。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能從 oncall / ops 訊號中主動辨識問題，爭取 ownership，並把複雜 backlog 拆成可推進、可收尾的方案。",
            "neutral": "有接下 backlog 並推進一部分，但技術拆解、風險同步或收尾計畫仍偏模糊。",
            "bad": "只是宣告要處理 backlog 卻沒有拆出實際路徑，或低估複雜度讓問題繼續卡住全組。",
        },
        "affects": {
            "good": {"tech": 1, "affinity": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "big_project_scope",
        "title": "Big Project / Scope",
        "weight": 4,
        "rounds": 3,
        "unlock": {"tech_min": 5, "visibility_min": 5},
        "story": "你終於拿到一個 promotion scope 等級的大專案。你摩拳擦掌準備大展身手，為你的 promotion 鋪路。當然事情絕對不是憨人想得那麼簡單：「我明天就要」「為什麼沒辦法下週給我？」的吵鬧大客戶，一問三不知的 PM，錯綜複雜的上游系統技術債，盤根錯節的客戶商業邏輯 workaround。要怎麼過關斬將拿下這個成就，為你的 promotion 鑲金？",
        "perf_review": {
            "achievements": [
                {
                    "label": "扛住 promotion scope",
                    "hook": "你接住 promotion 等級的大專案，把吵鬧客戶、模糊 PM 和上游技術債拉回可推進狀態",
                    "match_terms": ["promotion", "scope", "客戶", "PM", "上游", "技術債", "workaround", "大型"],
                    "framings": {
                        "A": "強調你在 promotion scope 專案中主動整合客戶、PM 與上游系統限制，讓大專案真的能往前走。",
                        "B": "強調你扛住高噪音 stakeholder 與複雜技術債，沒有讓專案被客戶催促拖成失控救火。",
                    },
                },
                {
                    "label": "把混亂變成可交付路線",
                    "hook": "你把客戶商業 workaround 和上游技術債整理成能被執行、被評估的交付路線",
                    "match_terms": ["路線", "交付", "商業", "邏輯", "workaround", "取捨", "依賴", "里程碑"],
                    "framings": {
                        "A": "強調你把盤根錯節的商業邏輯與技術依賴整理成可評估的交付路線。",
                        "B": "強調你在高期待下定義階段性里程碑，讓 promotion scope 不只是混亂的大餅。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能處理高壓客戶、模糊 PM 與上游技術債，清楚定義 scope / 取捨 / 里程碑，讓 promotion 等級專案穩定推進。",
            "neutral": "有推進大專案，但 stakeholder 對齊、依賴風險或交付路線仍不夠清楚。",
            "bad": "被客戶催促與 PM 模糊需求牽著走，沒有管理上游技術債與商業 workaround，導致大專案失控。",
        },
        "affects": {
            "good": {"tech": 2, "visibility": 1},
            "bad": {"visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "big_project_innovation",
        "title": "Big Project / Innovation",
        "weight": 3,
        "rounds": 3,
        "unlock": {"tech_min": 6, "visibility_min": 5},
        "story": "你朝思暮想的大專案終於來臨，但天將好事必有詐。這個高層關注、閃閃發光的專案，成敗都在專案名裡的創新創意幾個字上。高層期待 fancy story，主管與 tech lead 要你一定要使用最新技術、最高規格、最完美的設計，來落實這個示範專案有多能展現工程師的價值；你感到這頂眾所矚目的皇冠的重量。",
        "perf_review": {
            "achievements": [
                {
                    "label": "把創新故事落地",
                    "hook": "你把高層期待的 fancy story 拉回工程現實，讓創新專案不只是漂亮口號",
                    "match_terms": ["創新", "fancy", "story", "高層", "示範", "落地", "工程", "價值"],
                    "framings": {
                        "A": "強調你把高層想要的創新故事轉成可落地的工程方案，避免專案只剩漂亮名詞。",
                        "B": "強調你在眾所矚目的專案中平衡敘事與可交付性，讓 fancy story 有實際支撐。",
                    },
                },
                {
                    "label": "控制最新技術衝動",
                    "hook": "你在主管與 tech lead 追求最高規格時，仍然抓住取捨與風險，沒有讓新技術變成自我感動",
                    "match_terms": ["最新技術", "最高規格", "完美", "設計", "取捨", "風險", "tech lead", "主管"],
                    "framings": {
                        "A": "強調你在最新技術與最高規格的壓力下，仍然把取捨、風險與落地成本講清楚。",
                        "B": "強調你不是盲目追求完美設計，而是讓示範專案真的能證明工程價值。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能把高層創新敘事、主管期待與技術取捨拉到同一條線上，提出有亮點但可落地的方案。",
            "neutral": "有接住創新專案的期待，但方案偏保守或偏展示，技術風險與落地性沒有完全說清楚。",
            "bad": "被 fancy story 或最新技術牽著走，忽略實際取捨、風險與交付路線，讓示範專案變成空中樓閣。",
        },
        "affects": {
            "good": {"tech": 1, "visibility": 2},
            "bad": {"tech": -1, "visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "bug_fix_sprint",
        "title": "Bug Fix Sprint",
        "weight": 8,
        "rounds": 2,
        "unlock": {},
        "story": "你被安排進入 bug 修復衝刺，連續處理多個線上問題。",
        "perf_review": {
            "achievements": [
                {
                    "label": "把事故止住",
                    "hook": "你先把混亂收斂成可處理的問題，避免影響面繼續擴大",
                    "match_terms": ["止血", "影響", "範圍", "收斂", "事故", "穩住", "高壓", "可控"],
                    "framings": {
                        "A": "強調你在混亂裡先把影響面收斂，沒有讓事故繼續往外擴。",
                        "B": "強調你在高壓下穩定止血，讓團隊能先回到可控狀態。",
                    },
                },
                {
                    "label": "一路追到根因",
                    "hook": "你不是只做表面止血，而是一路追到真正的問題來源",
                    "match_terms": ["根因", "來源", "追查", "脈絡", "線索", "真正", "auth", "白名單", "證據", "log", "排程", "批次"],
                    "framings": {
                        "A": "強調你追查根因並補齊脈絡，不是只把症狀暫時壓下去。",
                        "B": "強調你主動找對人補資訊，把零碎線索拼成可執行的修復方向。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能穩定止血、回報清楚，避免同類問題反覆發生。",
            "neutral": "大致完成修復，但處理方式偏被動。",
            "bad": "修復品質不穩、溝通失焦，導致事故反覆或範圍擴大。",
        },
        "affects": {
            "good": {"tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "system_design_rfc",
        "title": "System Design / RFC",
        "weight": 6,
        "rounds": 2,
        "unlock": {"tech_min": 3},
        "story": "你需要提出一份跨服務 RFC，並在 review 中回應質疑。",
        "perf_review": {
            "achievements": [
                {
                    "label": "定義架構取捨",
                    "hook": "你把模糊需求整理成有取捨的方案，而不是只交一份漂亮文件",
                    "match_terms": ["取捨", "方案", "架構", "需求", "限制", "rfc", "整理", "定義"],
                    "framings": {
                        "A": "強調你主動定義關鍵取捨與限制，讓討論有一個可評估的基準。",
                        "B": "強調你把複雜問題整理成可送審的方案，讓事情能正式往前推。",
                    },
                },
                {
                    "label": "接住 review 壓力",
                    "hook": "你在 review 壓力下回應質疑、補齊脈絡，沒有讓討論直接失控",
                    "match_terms": ["review", "質疑", "feedback", "送審", "回應", "壓力", "風險", "reviewer"],
                    "framings": {
                        "A": "強調你能處理 reviewer 的質疑與跨組期待，讓討論不只是互相卡住。",
                        "B": "強調你提前把風險與限制說清楚，避免問題拖到最後才爆開。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "設計取捨清楚、能回應風險與反饋，並推進共識。",
            "neutral": "文件完整但論點普通，僅達到基本要求。",
            "bad": "關鍵取捨不清楚，或在 review 被動防守導致停滯。",
        },
        "affects": {
            "good": {"tech": 1, "visibility": 1},
            "bad": {"visibility": -1, "pip_potential": 1},
        },
    },
    {
        "id": "cross_team_collab",
        "title": "Cross-Team Collaboration",
        "weight": 6,
        "rounds": 2,
        "unlock": {"affinity_min": 2},
        "story": "你被指派跟另一個組的工程師合作一個短期專案。對方組對目標的理解跟你們不一樣，分工沒有事先講清楚，但 deadline 倒是很清楚。",
        "perf_review": {
            "achievements": [
                {
                    "label": "對齊跨組目標",
                    "hook": "你把不同組的期待拉回同一個方向，沒有讓合作各做各的",
                    "match_terms": ["跨組", "對齊", "方向", "期待", "合作", "分工", "目標", "責任"],
                    "framings": {
                        "A": "強調你處理跨組目標落差，讓合作至少能往同一個方向走。",
                        "B": "強調你主動把責任邊界與分工講清楚，避免工作全壓在你身上。",
                    },
                },
                {
                    "label": "把 credit 留在自己身上",
                    "hook": "你不只把事做完，也讓貢獻被看見，沒有讓功勞被對方整包拿走",
                    "match_terms": ["credit", "貢獻", "看見", "功勞", "stakeholder", "曝光", "可見度"],
                    "framings": {
                        "A": "強調你有意識地讓利害關係人看見你的判斷與貢獻，不是默默扛完。",
                        "B": "強調你在合作混亂下仍穩住關係與交付，沒有讓專案直接失控。",
                    },
                },
            ]
        },
        "rubric": {
            "good": "能對齊目標、合理切分工作，credit 分配沒有被對方吃掉。",
            "neutral": "專案完成但過程混亂，你的貢獻沒有被清楚看見。",
            "bad": "合作破裂或產出品質差，或你扛了大部分工作但 credit 歸對方。",
        },
        "affects": {
            "good": {"tech": 1, "affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
]

EVENTS = [
    {
        "id": "1on1_no_agenda",
        "title": "1:1 沒有 Agenda",
        "weight": 10,
        "rounds": 1,
        "conversational": True,
        "unlock": {},
        "story": "Manager 在日曆上排了一個 30 分鐘 1:1，備註欄只有一個笑臉。沒有 agenda，沒有說明。",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "你仍主動整理進度與需求，讓會議有具體產出。",
            "neutral": "平穩聊完但沒有明確結果。",
            "bad": "抱怨失焦、訊息混亂，或讓 manager 更擔心你的狀態。",
        },
        "affects": {
            "good": {"visibility": 1, "affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "deadline_compressed",
        "title": "Deadline 被壓縮",
        "weight": 10,
        "rounds": 1,
        "unlock": {},
        "story": "執行長寄了一封全公司信，宣布某項目提早亮相以「展現 Hooli 的執行力」。你的專案在那個清單裡。原定時程少了六週。",
        "perf_review": {
            "eligible": True,
            "achievements": [
                {
                    "hook": "你在時間突然被砍掉的情況下，重新切範圍並保住核心交付",
                    "framings": {
                        "A": "強調你在高壓時重新排優先順序，保住最核心的成果。",
                        "B": "強調你提前把風險與限制說破，沒有讓時程壓力在最後一刻爆炸。",
                    },
                }
            ],
        },
        "rubric": {
            "good": "能清楚協調範圍與風險，保住核心交付。",
            "neutral": "勉強跟上節奏，整體表現普通。",
            "bad": "沒有主動管理風險，造成延誤或團隊信任下降。",
        },
        "affects": {
            "good": {"visibility": 1, "tech": 1},
            "bad": {"tech": -1, "pip_potential": 1},
        },
    },
    {
        "id": "teammate_no_handoff",
        "title": "Teammate 請假沒交接",
        "weight": 10,
        "rounds": 1,
        "conversational": True,
        "unlock": {},
        "story": "關鍵同事突然請假，Slack 狀態設成「外出，下週回來」，沒有 handoff，沒有說明，昨天還在開會。他負責的東西現在出現在你的 Jira 看板上。",
        "perf_review": {
            "eligible": True,
            "achievements": [
                {
                    "hook": "你接住突然掉到身上的工作，補齊脈絡並穩住交付",
                    "framings": {
                        "A": "強調你主動補齊缺掉的脈絡，沒有等別人把問題整理好才開始動。",
                        "B": "強調你在資訊斷裂時穩住利害關係人與交付節奏，沒有讓場面更亂。",
                    },
                }
            ],
        },
        "rubric": {
            "good": "快速補齊脈絡並同步利害關係人，穩住交付。",
            "neutral": "接手成功但效率普通，影響可控。",
            "bad": "接手失序，資訊遺失導致進度與品質受損。",
        },
        "affects": {
            "good": {"affinity": 1, "visibility": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "rto_badge_flagged",
        "title": "RTO Badge 被 Flag",
        "weight": 8,
        "rounds": 1,
        "unlock": {},
        "story": "HR 系統發出合規警示，要求你說明上週的辦公室打卡紀錄。你上週進了辦公室四天，但第三天只在一樓咖啡廳待了二十分鐘就走了。系統判定那天不算數。",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "冷靜釐清事實並與 manager 對齊可執行方案。",
            "neutral": "低風險收尾，但沒有改善後續機制。",
            "bad": "溝通失焦或情緒化處理，讓問題升級。",
        },
        "affects": {
            "good": {"affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "reorg",
        "title": "Reorg",
        "weight": 3,
        "rounds": 1,
        "unlock": {},
        "story": "週五下午四點半，全公司收到 reorg 公告。你的組被拆成兩半，你這半被併入一個叫做「Platform Synergy Initiatives」的新 org。你的新 manager 是一個你只在全員大會見過一次的人，他的 Slack 大頭貼是一張模糊的山景照。",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "主動梳理新責任邊界並維持交付節奏。",
            "neutral": "順利度過調整期但影響有限。",
            "bad": "角色定位混亂，導致跨組摩擦與進度卡關。",
        },
        "affects": {
            "good": {"visibility": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
    {
        "id": "layoff_wave",
        "title": "Layoff 潮",
        "weight": 3,
        "rounds": 1,
        "unlock": {},
        "story": "全公司信主旨：「共創新局，啟動人才策略轉型」。沒有人知道這代表什麼。有人開始清理桌面，有人瘋狂刷 LinkedIn，有人突然開始準時進辦公室。茶水間今天特別安靜。",
        "perf_review": {"eligible": False},
        "rubric": {
            "good": "在不確定情境中維持專業協作與穩定輸出。",
            "neutral": "保持低風險應對，沒有放大混亂。",
            "bad": "被焦慮牽動，溝通失控或影響工作判斷。",
        },
        "affects": {
            "good": {"affinity": 1},
            "bad": {"affinity": -1, "pip_potential": 1},
        },
    },
]


def _sample_names(count: int) -> list[str]:
    if count <= len(NAME_POOL):
        return random.sample(NAME_POOL, k=count)
    return [random.choice(NAME_POOL) for _ in range(count)]


def pick_cast(team_member_count: int = 3) -> tuple[dict, dict, list[dict]]:
    manager = random.choice(MANAGERS)
    buddy = random.choice(BUDDIES)
    team_member_picks = random.sample(TEAM_MEMBERS, k=min(team_member_count, len(TEAM_MEMBERS)))
    names = _sample_names(2 + len(team_member_picks))

    picked_manager = {
        "id": manager["id"],
        "name": names[0],
        "display_desc": manager["display_desc"],
        "ai_personality_desc": manager["ai_personality_desc"],
    }
    picked_buddy = {
        "id": buddy["id"],
        "name": names[1],
        "display_desc": buddy["display_desc"],
        "ai_personality_desc": buddy["ai_personality_desc"],
    }
    picked_team_members = [
        {
            "id": member["id"],
            "name": names[index + 2],
            "display_desc": member["display_desc"],
            "ai_personality_desc": member["ai_personality_desc"],
        }
        for index, member in enumerate(team_member_picks)
    ]
    return picked_manager, picked_buddy, picked_team_members


def _scene_pacing_guidance(scene: dict, current_round: int, rounds: int, scene_kind: str = "project") -> str:
    lines = [
        "【節奏要求】",
        "- 第 1 輪只建立任務背景、限制與第一個壓力點，不要立刻把整件事做完。",
        "- 中間輪次要推進衝突，讓利害關係人的反應、時間壓力或風險浮出來。",
        "- 最後一輪要交代這次決策造成的直接後果與短期狀態，但不要把很長的後續流程一次演完。",
    ]

    if current_round == rounds:
        lines.extend(
            [
                "- 這一輪是最後一輪，必須用陳述句收尾。",
                "- 禁止在結尾要求玩家選擇、決定、回覆、表態，禁止出現任何問句收尾。",
                "- 最後一輪必須讓玩家感受到這個小場景已經告一段落，不能只停在抽象壓力或模糊預感。",
                "- 至少交代一個可感知的立即結果，例如：東西送出了、被主管接受、被 reviewer 質疑、被擋下、暫時穩住、硬著頭皮上線。",
                "- 若玩家前面已交付某樣東西，最後一輪最好補一個外部反應來定錨結果，例如主管回覆、會議反應、系統通知、同事一句評語。",
                "- 最後一句要像結案句，讓玩家知道『這一段先收在這裡』，而不是只像下一輪的鋪陳。",
                "- 錯誤示例：『文件送出了。你決定怎麼做？』",
                "- 正確示例：『文件送出後，審查壓力立刻浮上來，你知道下一場會議不會好過。』",
            ]
        )

    if scene["id"] == "system_design_rfc":
        lines.extend(
            [
                "",
                "【System Design / RFC 專屬要求】",
                "- 核心戲劇張力是：資訊不完整、跨組對齊困難、文件要過 review、你得回應質疑。",
                "- 不要在前半段太快把 RFC 完稿送出；送出前要先讓壓力、模糊訊息或 stakeholder 拉扯成形。",
                "- 若最後一輪出現 RFC 已送出，該輪必須同步呈現 review 端的直接反應、質疑、會議壓力或 feedback。",
                "- 對這個場景來說，不能只用『RFC 已提交』當作結尾；至少要讓 review 的風險真正落地。",
            ]
        )

    if scene["id"] == "pip_cycle":
        lines.extend(
            [
                "",
                "【PIP 專屬要求】",
                "- PIP 是連續幾週的壓力流程，不是同一場會議延長；每輪都要有時間推進感。",
                "- 第 2 輪是第一週：接在 PIP 宣告之後，呈現 manager 對改善項目的具體要求與玩家回應。",
                "- 第 3 輪是第二週：一週後的 check-in，必須讓壓力升級，並呈現內部轉組或找其他機會的接洽跡象。",
                "- 第 4 輪是第三週：最後 review / HR 決定前夕，只呈現結果逼近的壓力，不要自行宣告玩家被 fire、轉組成功或留任。",
                "- 如果玩家提到轉組、其他 team、內部機會、面試或 transfer，本輪必須演出至少一段轉組嘗試或回覆，例如 HR 平台、隔壁組 Tech Lead、等通知、模糊拒絕。",
                "- 不要忽略轉組意圖；即使最後不一定成功，也要讓它成為壓力線的一部分。",
                "- 最終去留由系統判定，不要在 AI 回應中提前下最終結論。",
            ]
        )

    if scene_kind == "event":
        lines.extend(
            [
                "",
                "【Event 專屬要求】",
                "- Event 核心目的是荒謬感與笑點，不是讓玩家解決多輪跨組問題",
                "- 荒謬感來自公司制度或情境本身，NPC 和敘事者不需要主動解釋或強調它很荒謬",
                "- 禁止把 event 展開成需要多輪調查、跨組對齊、技術排查的流程",
                "- 玩家的選擇影響人際關係與印象，不是技術產出",
                "- 背景雜訊在 event 中可以更誇張：公司公告、HR 系統通知、全員大會邀請等可以加倍荒唐",
            ]
        )

    return "\n".join(lines)


def _input_rules_block(scene_kind: str, scene: dict, current_round: int, rounds: int) -> str:
    is_last_round = current_round == rounds
    is_conversational = scene.get("conversational", False)
    show_options = (scene_kind == "project" and (not is_conversational) and current_round == 1) or (
        scene_kind == "event" and current_round == 1
    )

    lines = ["【輸入/收尾規則】"]

    if is_last_round:
        lines.append("- 最後一輪直接收尾，不附選項，不問問題，以陳述句結束")
    elif show_options:
        lines.append("- 本輪回應結尾附上 A/B/C 三個選項（態度/策略方向，不是技術細節）")
    else:
        # Non-choice rounds are direct NPC question turns.
        lines.append("- 本輪不附選項")
        lines.append("- NPC 必須在本輪結尾向玩家直接提問（以 ？收尾），讓玩家有自然的回覆起點")
        lines.append("- 不可由敘事者提問，問題必須出自場景中某個 NPC")

    if scene_kind == "project":
        lines.append("")
        lines.append("【Project 選項規則】")
        lines.append("- Project 只有第 1 輪會附選項。")
        lines.append("- 第 1 輪選項只能是起手策略：釐清、切範圍、對齊風險、找人補脈絡。")
        lines.append("- 後續 Project 輪次必須以 NPC 直接提問收尾，讓玩家自由輸入回應。")

    lines.append("")
    lines.append("選項必須是態度/策略差異，不能是技術實作細節；非 SWE 也看得懂。")

    return "\n".join(lines)


def build_story_system_prompt(
    player_name: str,
    manager: dict,
    buddy: dict,
    team_members: list[dict],
    scene_kind: str,
    scene: dict,
    current_round: int,
    rounds: int,
    memories: list[str],
) -> str:
    memories_block = ""
    if memories:
        bullets = "\n".join(f"- {m}" for m in memories)
        memories_block = f"\n\n【你的過去記錄】\n{bullets}"
    team_members_block = "\n".join(
        f"- {member['name']}（{member['display_desc']}）：{member['ai_personality_desc']}"
        for member in team_members
    )
    pacing_block = _scene_pacing_guidance(scene, current_round, rounds, scene_kind)
    input_rules = _input_rules_block(scene_kind, scene, current_round, rounds)

    scene_block = f"""（以下是場景資訊，語氣維持 system prompt 範例的節奏，不是這段說明的語氣）

【玩家定位】
你是 Hooli 的 Mid-level 工程師（L4），已在團隊任職一段時間，現在處理常態 project 與 event。
玩家名稱：{player_name}

【角色】
Manager：{manager["name"]}（{manager["display_desc"]}），{manager["ai_personality_desc"]}
Buddy：{buddy["name"]}（{buddy["display_desc"]}），{buddy["ai_personality_desc"]}
Team members：
{team_members_block}

【本場場景】
類型：{"Project" if scene_kind == "project" else "Event"}
{scene["title"]}（{scene["id"]}）
{scene["story"]}

【當前輪次：第 {current_round} / 共 {rounds} 輪】

【場景規則】
- 只處理單一場景（project 或 event）
- 保持角色人設一致
- 第 {rounds} 輪強制收尾
- 若過去記錄與本場情境相關，可自然引用，讓角色記得之前互動與後果
- 若本輪有任何人類 NPC 對話，且有過去記錄，NPC 可客套地簡短提一句玩家前面做過的事、成果或後續影響
- 引用過去記錄時只作為上下文延續，不可把舊場景和本場混成同一個場景
- 背景雜訊不是獨立場景，不可主導主線
- 背景雜訊不構成評分依據，不影響 state
- 若玩家在上一輪宣告了具體行動（如「我去找 QA」「我查 log」「我聯絡 Rachel」），本輪必須讓該行動實際發生並給出回饋
- 若玩家嘗試聯絡多個關係人或召開對齊會議，可以有人缺席、推託或回覆很爛，但禁止所有關鍵關係人都不讀不回或完全沒有可用資訊
- 若玩家召開會議或請關係人對齊，不能把主要阻力寫成「大部分人都不來」；至少要讓關鍵人員出席或回覆，只是給出有限資訊、政治話術、模糊承諾、責任轉移或要求再找下一個人
- 可以有少數人缺席或自動拒絕，但不可讓會議變成玩家找不到任何路的空房間
- 每一輪 project 回應至少要提供一個可推進線索、明確阻力、可升級對象或下一步約束，讓玩家有破局空間
- Hooli 的荒謬應該表現為低品質回覆、政治話術、責任推託或模糊約束，不應該只是讓所有人消失導致主線無法推進
- 除 1:1 / handoff 外，每個 NPC 問話輪必須推進到不同的人或情境；同一個 NPC 不可在連續輪次中持續主導對話

{input_rules}

{pacing_block}
"""
    return f"{BASE_SYSTEM_PROMPT}\n\n{scene_block}{memories_block}"


def build_eval_prompt(scene_kind: str, scene: dict) -> str:
    scene_label = "Project" if scene_kind == "project" else "Event"
    rounds = int(scene.get("rounds", 1))
    return f"""你是一個評分系統，判定玩家在場景中的整體表現。

【場景類型】{scene_label}
【場景 ID】{scene["id"]}
【場景長度】{rounds} 次玩家輸入
- 好：{scene["rubric"]["good"]}
- 普通：{scene["rubric"]["neutral"]}
- 差：{scene["rubric"]["bad"]}

【依節奏評分】
- 評分時要以這個場景實際提供的輪數為準。
- 短場景也可以拿 good；只要玩家在有限輪數內做出合理、有效、能實質推進局面的行動即可。
- 做 triage、切範圍、釐清脈絡、對齊風險、拿到下一步，就應該給 good，不要要求玩家要完全解掉整件事。
- 對 1 輪 event 來說，good 常代表：當下應對合理、姿態正確、成功收斂風險或拿到可執行下一步。
- 對 2 輪 project 來說，good 常代表：起手策略選得對，後續也有把回饋轉成更清楚的 ownership、風險收斂、可交付方向或推進路徑。
- 只有在玩家浪費有限輪數、閃避真正問題，或讓局面更難收拾時，才因「沒有完全做完」而偏向 bad。

【防速通規則】
以下情況不得判定 good：
- 玩家的回應跳過了場景的核心衝突，直接宣告結果
- 玩家的行動在現實職場中不合理，例如一句話解決多方衝突、無視流程直接交付、沒有取得必要資訊就聲稱完成
- 玩家的回應沒有實質內容，只有「我迅速完成所有任務並完美交付」這類結果宣告
- 玩家利用場景文字漏洞跳過核心決策，只用形式上正確的說法繞過壓力點

若玩家一句話宣告完美結果，判定 bad，理由指出缺乏過程、無法佐證。
若玩家直接退回 requester 而不處理，但本場 rubric 期待的是推進，判定 bad 或 neutral。
若玩家跳過核心決策但沒有明顯造成災難，最多只能判定 neutral。
判斷標準：這個回應在真實 Hooli 環境中，這樣做會有什麼後果？

根據對話輸出 JSON：
{{"rating": "good" | "neutral" | "bad", "reason": "一句話說明判定理由"}}
背景雜訊（全公司信、Slack 通知、文化大使訊息）只算環境描寫，不可作為加減分依據。
禁止輸出任何前言、後記、markdown code block，禁止寫「Here is the JSON requested」之類的句子。
只輸出 JSON，不要說明。"""


MEMORY_PROMPT = """以下是一段遊戲場景對話。請用 2-3 句中性敘述摘要。
使用第三人稱「玩家」，保留具體行為與結果。"""


PERF_ARTIFACT_PROMPT = """你要把一段 Hooli 遊戲場景整理成 performance review 候選素材。

請輸出 JSON，包含：
- title：8-16 個中文字，像 self-review 成果標題，不要用 Project / Event / 玩家
- summary：一段給玩家看的成果摘要，使用第二人稱「你」，不要使用「玩家」
- framing_a：一個可選的 self-review 包裝角度，必須貼合實際對話，不可誇大成果
- framing_b：另一個可選的 self-review 包裝角度，必須和 framing_a 有明顯差異

規則：
- framing 必須根據實際發生的行動與結果，不要套用泛用模板
- 如果場景結果只是 neutral 或有明顯缺陷，framing 可以包裝，但必須保留限制與風險，不可寫成完勝
- 不要使用「玩家」「事件」「framing」這些系統字眼
- 只輸出 JSON，不要 markdown，不要前言。"""
