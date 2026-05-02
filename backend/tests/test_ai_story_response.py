import ai


def test_trimmed_partial_rejects_opening_like_turn_response():
    messages = [
        {
            "role": "assistant",
            "content": (
                "你 scrolling 著 Jira 看著一堆積壓的 ops tickets，手指不小心滑到了一張陳年的 ticket。"
                "這張票的標題簡潔有力：「不明原因服務中斷」，但裡面附上的 log 錯誤訊息卻是洋洋灑灑幾百行。"
            ),
        },
        {
            "role": "user",
            "content": "先試著從現有文件和程式碼中，釐清這個服務的架構與相關依賴。",
        },
    ]
    trimmed = (
        "你瀏覽著 Jira 上的 ops tickets，無意間點開一張陳年舊票：「不明原因服務中斷」。"
        "裡頭是幾百行 log 錯誤，時間橫跨半年，留言都寫著「Not my team's responsibility」。"
        "這像是 Hooli 的服務黑洞，沒人敢碰，但解決了肯定能寫進 performance review。"
        "你決定怎麼做？"
    )

    assert ai._trimmed_story_matches_turn_context(trimmed, messages) is False


def test_trimmed_partial_accepts_turn_response_that_uses_user_context():
    messages = [
        {
            "role": "assistant",
            "content": (
                "你 scrolling 著 Jira 看著一堆積壓的 ops tickets，手指不小心滑到了一張陳年的 ticket。"
            ),
        },
        {
            "role": "user",
            "content": "先試著從現有文件和程式碼中，釐清這個服務的架構與相關依賴。",
        },
    ]
    trimmed = (
        "你試圖從內部文件庫與程式碼中抽絲剝繭。那些過期的 wiki 頁面與零散的 README 寫著相互矛盾的架構圖，"
        "有些甚至指向十年前就下線的服務。程式碼裡，關鍵的函式庫引用著一個名為「Hooli Shared Core」的組件。"
    )

    assert ai._trimmed_story_matches_turn_context(trimmed, messages) is True


def test_length_guard_retries_with_same_messages(app_modules):
    main = app_modules["main"]
    calls: list[list[dict]] = []

    def stub_story_response(system_prompt: str, messages: list[dict]):
        calls.append([dict(message) for message in messages])
        if len(calls) == 1:
            return "甲" * 400, {"source": "first", "fallback": False}
        return "第二次正常內容。", {"source": "second", "fallback": False}

    main.story_response = stub_story_response
    text, debug = main._with_story_length_guard(
        "system prompt",
        [{"role": "user", "content": "玩家輸入"}],
        "zh-Hant",
    )

    assert text == "第二次正常內容。"
    assert debug["source"] == "second"
    assert len(calls) == 2
    assert calls[0] == calls[1] == [{"role": "user", "content": "玩家輸入"}]
