import re


def install_stub_ai(main_module, rating_by_scene=None):
    rating_by_scene = rating_by_scene or {}

    def stub_story_response(system_prompt: str, messages: list[dict]):
        if len(messages) == 1 and messages[0]["content"] in {
            "【場景開始】只敘述這個單一場景的開場。",
            "[Scene start] Describe only the opening of this single scene.",
        }:
            return "場景開始。", {"source": "test_opening", "attempts": []}
        return "場景繼續。", {"source": "test_turn", "attempts": []}

    def stub_evaluate_rating(prompt: str, transcript_text: str):
        match = re.search(r"(?:【場景 ID】|\[Scene ID\])\s*([^\n]+)", prompt)
        scene_id = match.group(1).strip() if match else "unknown"
        rating = rating_by_scene.get(scene_id, "neutral")
        return rating, f"{scene_id}:{rating}", {"scene_id": scene_id, "source": "test"}

    main_module.story_response = stub_story_response
    main_module.evaluate_rating = stub_evaluate_rating
    main_module.summarize_memory = lambda transcript_text, **kwargs: "測試摘要"


def create_session(client):
    response = client.post("/sessions", json={"player_name": "Claire", "locale": "zh-Hant"})
    assert response.status_code == 200
    return response.json()["session_id"]


def get_session(client, session_id: str):
    response = client.get(f"/sessions/{session_id}")
    assert response.status_code == 200
    return response.json()


def next_scene(client, session_id: str):
    response = client.get(f"/sessions/{session_id}/next-scene")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    return payload


def finish_current_scene(client, session_id: str):
    session = get_session(client, session_id)
    scene_id = session["current_scene_id"]
    round_number = session["round"]
    max_rounds = session["max_rounds"]
    last_payload = None

    if scene_id == "perf_review_cycle":
        turn_inputs = ["1 2", "1A 2B"]
    else:
        remaining = max_rounds - round_number
        turn_inputs = ["繼續"] * remaining

    for message in turn_inputs:
        response = client.post(f"/sessions/{session_id}/turn", json={"message": message})
        assert response.status_code == 200
        last_payload = response.json()

    assert last_payload is not None
    return last_payload


def complete_scene_and_transition(client, session_id: str):
    payload = finish_current_scene(client, session_id)
    if payload.get("game_ended"):
        return payload, None
    assert payload["scene_ended"] is True
    next_scene(client, session_id)
    return payload, get_session(client, session_id)


def set_session_state(modules, session_id: str, **updates):
    db = modules["db"].SessionLocal()
    try:
        session = db.get(modules["db"].GameSession, session_id)
        session.state = {**session.state, **updates}
        db.commit()
    finally:
        db.close()


def test_story_runtime_provider_priority_only_uses_gemini_then_claude(app_modules, monkeypatch):
    ai = app_modules["ai"]

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("AI_PROVIDER_PRIORITY", "openai,anthropic,gemini")

    assert ai._provider_priority() == ["gemini", "anthropic"]
    assert ai._story_models() == ["gemini-2.5-flash"]


def test_create_session_returns_503_when_story_ai_unavailable(client, app_modules):
    main = app_modules["main"]

    def stub_story_response(system_prompt: str, messages: list[dict]):
        return "（系統暫時無法產生場景內容，請稍後再試。）", {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "source": "all_providers_fallback",
            "attempts": [],
            "fallback": True,
        }

    main.story_response = stub_story_response

    response = client.post("/sessions", json={"player_name": "Claire", "locale": "zh-Hant"})

    assert response.status_code == 503
    assert response.json()["detail"] == "AI 服務暫時不可用，請晚點再來。"


def test_next_scene_returns_503_when_next_opening_ai_unavailable(client, app_modules):
    main = app_modules["main"]

    opening_count = 0

    def stub_story_response(system_prompt: str, messages: list[dict]):
        nonlocal opening_count
        if len(messages) == 1 and messages[0]["content"] in {
            "【場景開始】只敘述這個單一場景的開場。",
            "[Scene start] Describe only the opening of this single scene.",
        }:
            opening_count += 1
            if opening_count == 1:
                return "場景開始。", {"source": "test_opening", "attempts": [], "fallback": False}
            return "（系統暫時無法產生場景內容，請稍後再試。）", {
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
                "source": "all_providers_fallback",
                "attempts": [],
                "fallback": True,
            }
        return "場景繼續。", {"source": "test_turn", "attempts": [], "fallback": False}

    def stub_evaluate_rating(prompt: str, transcript_text: str):
        return "neutral", "test", {"source": "test_eval"}

    main.story_response = stub_story_response
    main.evaluate_rating = stub_evaluate_rating
    main.summarize_memory = lambda transcript_text, **kwargs: "測試摘要"

    session_id = create_session(client)
    payload = finish_current_scene(client, session_id)

    assert payload["scene_ended"] is True

    response = client.get(f"/sessions/{session_id}/next-scene")

    assert response.status_code == 503
    assert response.json()["detail"] == "AI 服務暫時不可用，請晚點再來。"


def test_turn_returns_503_when_story_ai_unavailable(client, app_modules):
    main = app_modules["main"]

    def stub_story_response(system_prompt: str, messages: list[dict]):
        if len(messages) == 1 and messages[0]["content"] in {
            "【場景開始】只敘述這個單一場景的開場。",
            "[Scene start] Describe only the opening of this single scene.",
        }:
            return "場景開始。", {"source": "test_opening", "attempts": [], "fallback": False}
        return "（系統暫時無法產生場景內容，請稍後再試。）", {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "source": "all_providers_fallback",
            "attempts": [],
            "fallback": True,
        }

    main.story_response = stub_story_response
    main.evaluate_rating = lambda *args, **kwargs: ("neutral", "x", {})
    main.summarize_memory = lambda text, **kwargs: "摘要"

    session_id = create_session(client)
    response = client.post(f"/sessions/{session_id}/turn", json={"message": "繼續"})

    assert response.status_code == 503
    assert response.json()["detail"] == "AI 服務暫時不可用，請晚點再來。"


def test_reorg_overrides_normal_event_and_returns_to_game(client, app_modules, monkeypatch):
    monkeypatch.setenv("REORG_PROBABILITY", "1")
    install_stub_ai(app_modules["main"])

    session_id = create_session(client)
    _, state_after_event_one = complete_scene_and_transition(client, session_id)
    assert state_after_event_one["current_scene_type"] == "event"

    _, state_after_cycle_one = complete_scene_and_transition(client, session_id)
    assert state_after_cycle_one["current_scene_type"] == "project"

    characters_before_reorg = state_after_cycle_one["characters"]
    _, reorg_state = complete_scene_and_transition(client, session_id)

    assert reorg_state["current_scene_id"] == "reorg_cycle"
    assert reorg_state["characters"] != characters_before_reorg

    _, post_reorg_state = complete_scene_and_transition(client, session_id)
    assert post_reorg_state["current_scene_type"] == "project"
    assert post_reorg_state["current_scene_id"] != "reorg_cycle"


def test_perf_review_can_lead_to_promo_endgame(client, app_modules):
    install_stub_ai(app_modules["main"], {"perf_review_cycle": "neutral"})

    session_id = create_session(client)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)

    set_session_state(
        app_modules,
        session_id,
        tech=7,
        visibility=6,
        affinity=5,
        pip_potential=4,
        completed_cycles=3,
        rounds_since_promo=3,
    )

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "perf_review_cycle"

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "promo_result"

    promo_result = finish_current_scene(client, session_id)
    assert promo_result["game_ended"] is True
    assert promo_result["end_reason"] == "promoted"
    assert promo_result["ending"]["actions"]["share"] is True
    assert promo_result["ending"]["end_state"]["top_case_label"]
    assert promo_result["ending"]["end_state"]["achievement_line"]


def test_perf_review_can_lead_to_pip_and_back_to_game(client, app_modules):
    install_stub_ai(app_modules["main"], {"perf_review_cycle": "neutral", "pip_cycle": "good"})

    session_id = create_session(client)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)

    set_session_state(
        app_modules,
        session_id,
        tech=4,
        visibility=4,
        affinity=4,
        pip_potential=6,
        completed_cycles=3,
        rounds_since_promo=3,
    )

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "perf_review_cycle"

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "pip_cycle"

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_type"] == "project"
    assert state["status"] == "active"


def test_perf_review_can_lead_to_pip_and_fired_endgame(client, app_modules):
    install_stub_ai(app_modules["main"], {"perf_review_cycle": "neutral", "pip_cycle": "bad"})

    session_id = create_session(client)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)
    _, state = complete_scene_and_transition(client, session_id)

    set_session_state(
        app_modules,
        session_id,
        tech=4,
        visibility=4,
        affinity=3,
        pip_potential=8,
        completed_cycles=3,
        rounds_since_promo=3,
    )

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "perf_review_cycle"

    _, state = complete_scene_and_transition(client, session_id)
    assert state["current_scene_id"] == "pip_cycle"

    pip_result = finish_current_scene(client, session_id)
    assert pip_result["game_ended"] is True
    assert pip_result["end_reason"] == "fired"
    assert pip_result["ending"]["actions"]["share"] is True
    assert pip_result["ending"]["end_state"]["top_case_label"]
    assert pip_result["ending"]["end_state"]["share_text"]


def test_quit_intent_can_be_canceled_and_resume_game(client, app_modules):
    install_stub_ai(app_modules["main"])

    session_id = create_session(client)
    before = get_session(client, session_id)
    original_options = list(before["current_options"])

    response = client.post(f"/sessions/{session_id}/turn", json={"message": "我要辭職"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["scene_ended"] is False
    assert payload["options"][0]["id"] == "A"
    assert payload["options"][1]["id"] == "B"

    response = client.post(f"/sessions/{session_id}/turn", json={"message": "A"})
    assert response.status_code == 200
    resumed = response.json()
    assert resumed["scene_ended"] is False
    assert resumed["options"] == original_options

    session = get_session(client, session_id)
    assert session["status"] == "active"
    assert session["current_options"] == original_options


def test_quit_intent_can_confirm_quit_endgame(client, app_modules):
    install_stub_ai(app_modules["main"])

    session_id = create_session(client)

    response = client.post(f"/sessions/{session_id}/turn", json={"message": "我要辭職"})
    assert response.status_code == 200

    response = client.post(f"/sessions/{session_id}/turn", json={"message": "我還是要辭職"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["game_ended"] is True
    assert payload["end_reason"] == "quit"
    assert payload["ending"]["actions"]["share"] is True
    assert "transcript" not in payload["ending"]["actions"]
    assert payload["ending"]["end_state"]["achievement_line"]


def test_project_round_two_does_not_inject_default_options(app_modules):
    main = app_modules["main"]

    options = main._ensure_project_options(
        "medium_engineering_project",
        2,
        [],
        "Priya 看著你，等你回應。",
        "我先看看狀況。",
    )

    assert options == []


def test_story_debug_persists_turn_call_after_opening(client, app_modules):
    main = app_modules["main"]
    dbmod = app_modules["db"]

    def stub_story_response(system_prompt: str, messages: list[dict]):
        if len(messages) == 1:
            return "開場。\n\nA. 先看資料\nB. 先找主管\nC. 先問同事", {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "source": "opening_ok",
                "attempts": [{"provider": "gemini", "model": "gemini-2.5-flash", "mode": "opening_ok"}],
                "fallback": False,
            }
        return "（系統暫時無法產生場景內容，請稍後再試。）", {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "source": "fallback_text",
            "attempts": [{"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "mode": "fallback_text", "error": "boom"}],
            "fallback": True,
        }

    main.story_response = stub_story_response
    main.evaluate_rating = lambda *args, **kwargs: ("neutral", "x", {})
    main.summarize_memory = lambda text: "摘要"

    session_id = create_session(client)
    response = client.post(f"/sessions/{session_id}/turn", json={"message": "B"})
    assert response.status_code == 200

    db = dbmod.SessionLocal()
    try:
        session = db.get(dbmod.GameSession, session_id)
        scene_log = db.get(dbmod.SceneLog, session.current_scene_log_id)
        calls = list((scene_log.story_debug_json or {}).get("calls") or [])
        assert len(calls) == 2
        assert calls[0]["phase"] == "opening"
        assert calls[1]["phase"] == "turn"
        assert calls[1]["source"] == "fallback_text"
        assert session.round_in_scene == 1
    finally:
        db.close()


def test_openai_input_messages_uses_output_text_for_assistant(app_modules):
    ai = app_modules["ai"]

    converted = ai._openai_input_messages(
        [
            {"role": "user", "content": "使用者輸入"},
            {"role": "assistant", "content": "助理回覆"},
        ]
    )

    assert converted[0]["role"] == "user"
    assert converted[0]["content"][0]["type"] == "input_text"
    assert converted[1]["role"] == "assistant"
    assert converted[1]["content"][0]["type"] == "output_text"
