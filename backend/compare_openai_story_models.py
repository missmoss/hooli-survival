import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import asc, select

import ai
import main
from db import GameSession, SceneLog, SessionLocal
from prompt_registry import default_player_name, get_prompt_bundle


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _recent_memories_before(db, session_id: str, before_created_at, limit: int = 5) -> list[str]:
    rows = db.execute(
        select(SceneLog.memory_text, SceneLog.cast_snapshot)
        .where(
            SceneLog.session_id == session_id,
            SceneLog.memory_text.is_not(None),
            SceneLog.created_at < before_created_at,
        )
        .order_by(SceneLog.created_at.desc())
        .limit(limit)
    ).all()
    return [main._memory_with_cast(memory_text, cast_snapshot) for memory_text, cast_snapshot in rows if memory_text]


def _ordered_scene_logs(db, session_id: str) -> list[SceneLog]:
    return list(
        db.execute(
            select(SceneLog)
            .where(SceneLog.session_id == session_id)
            .order_by(asc(SceneLog.created_at), asc(SceneLog.id))
        ).scalars()
    )


def _resolve_target_scene_log(db, session_id: str, scene_log_id: str | None, scene_index: int | None) -> SceneLog:
    if scene_log_id:
        row = db.get(SceneLog, scene_log_id)
        if row is None or row.session_id != session_id:
            raise SystemExit(f"Scene log not found in session: {scene_log_id}")
        return row
    logs = _ordered_scene_logs(db, session_id)
    if not logs:
        raise SystemExit(f"No scene logs found for session: {session_id}")
    if scene_index is None:
        return logs[-1]
    if scene_index < 1 or scene_index > len(logs):
        raise SystemExit(f"scene-index out of range: {scene_index} (session has {len(logs)} scenes)")
    return logs[scene_index - 1]


def _scene_cast(scene_log: SceneLog, session: GameSession) -> dict:
    cast = scene_log.cast_snapshot if isinstance(scene_log.cast_snapshot, dict) else None
    if cast:
        return cast
    return session.characters


def _format_messages(messages: list[dict]) -> str:
    blocks: list[str] = []
    for idx, msg in enumerate(messages, start=1):
        blocks.append(f"### {idx}. {msg['role']}")
        blocks.append("")
        blocks.append(msg["content"].strip())
        blocks.append("")
    return "\n".join(blocks).strip()


def _render_output_section(title: str, output: dict) -> str:
    lines = [f"## {title}", ""]
    lines.append(f"- provider: `{output.get('provider', '')}`")
    lines.append(f"- model: `{output.get('model', '')}`")
    lines.append("")
    if output.get("raw_text"):
        lines.extend(
            [
                "### Raw",
                "",
                "```text",
                output["raw_text"],
                "```",
                "",
            ]
        )
    if output.get("narration"):
        lines.extend(
            [
                "### Parsed Narration",
                "",
                "```text",
                output["narration"],
                "```",
                "",
            ]
        )
    options = output.get("options") or []
    if options:
        lines.append("### Parsed Options")
        lines.append("")
        for opt in options:
            lines.append(f"- `{opt['id']}` {opt['text']}")
        lines.append("")
    if output.get("debug") is not None:
        lines.extend(
            [
                "### Debug",
                "",
                "```json",
                _json_dump(output["debug"]),
                "```",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _messages_before_target(scene_messages: list[dict], turn: int) -> list[dict]:
    if turn <= 0:
        raise ValueError("turn must be >= 1 for turn comparisons")
    collected: list[dict] = []
    user_count = 0
    for msg in scene_messages:
        collected.append(msg)
        if msg["role"] == "user":
            user_count += 1
            if user_count == turn:
                return collected
    raise SystemExit(f"Scene does not have user turn {turn}")


def _original_response_for_turn(scene_messages: list[dict], turn: int) -> str:
    if turn == 0:
        for msg in scene_messages:
            if msg["role"] == "assistant":
                return msg["content"]
        raise SystemExit("Scene has no opening assistant message")

    user_count = 0
    seen_target_user = False
    for msg in scene_messages:
        if msg["role"] == "user":
            user_count += 1
            if user_count == turn:
                seen_target_user = True
                continue
        if seen_target_user and msg["role"] == "assistant":
            return msg["content"]
    raise SystemExit(f"Scene does not have assistant response for turn {turn}")


def _base_scene_context(db, session: GameSession, scene_log: SceneLog) -> dict[str, Any]:
    locale = main._session_locale(session)
    scene_kind = main._scene_kind_from_ids(scene_log.project_id, scene_log.event_id)
    scene_id = scene_log.project_id if scene_kind == "project" else scene_log.event_id
    scene = main._resolve_scene(scene_kind, scene_id, locale)
    if main._is_perf_scene(scene_id) or main._is_promo_scene(scene_id) or main._is_reorg_scene(scene_id):
        raise SystemExit("This script only compares AI-generated story scenes. perf/promo/reorg are deterministic.")
    if main._is_pip_scene(scene_id):
        raise SystemExit("PIP continuation comparison is not wired into this script yet.")
    cast = _scene_cast(scene_log, session)
    memories = _recent_memories_before(db, session.id, scene_log.created_at, limit=5)
    return {
        "session_id": session.id,
        "scene_log_id": scene_log.id,
        "scene_kind": scene_kind,
        "scene_id": scene_id,
        "scene": scene,
        "locale": locale,
        "rounds": int(scene["rounds"]),
        "cast": {
            "player_name": cast.get("player_name", session.characters.get("player_name", default_player_name(locale))),
            "manager": cast["manager"],
            "buddy": cast["buddy"],
            "team_members": cast.get("team_members", []),
        },
        "memories": memories,
    }


def _build_system_prompt(state: dict[str, Any], current_round: int) -> str:
    bundle = get_prompt_bundle(state["locale"])
    cast = state["cast"]
    return bundle.build_story_system_prompt(
        player_name=cast.get("player_name", default_player_name(state["locale"])),
        manager=cast["manager"],
        buddy=cast["buddy"],
        team_members=cast.get("team_members", []),
        scene_kind=state["scene_kind"],
        scene=state["scene"],
        current_round=current_round,
        rounds=int(state["rounds"]) + 1,
        memories=list(state.get("memories") or []),
    )


def _postprocess_output(state: dict[str, Any], raw_text: str, current_round: int, last_user_message: str, mode: str) -> tuple[str, list[dict]]:
    locale = state["locale"]
    scene = state["scene"]
    scene_kind = state["scene_kind"]
    scene_id = state["scene_id"]
    is_conversational = scene.get("conversational", False)
    show_options = main._should_show_options(scene_kind, current_round, is_conversational)
    narration, options = main._split_narration_and_options(raw_text, expect_options=show_options, locale=locale)
    if show_options and scene_kind == "project":
        options = main._ensure_project_options(
            scene_id,
            current_round,
            options,
            narration,
            last_user_message,
            locale=locale,
        )
    if mode == "opening":
        if main._should_force_question(int(state["rounds"]) > 0, show_options):
            narration = main._ensure_question_ending(narration, locale)
        return narration, options
    will_end_after_response = current_round - 1 >= int(state["rounds"])
    if will_end_after_response:
        narration = main._strip_trailing_question_ending(narration)
        narration = main._ensure_scene_resolution(narration, locale, scene_kind, scene_id)
    elif main._should_force_question(True, show_options):
        narration = main._ensure_question_ending(narration, locale)
    return narration, options


def _compare_openai_model(
    system_prompt: str,
    messages: list[dict],
    model_name: str,
    reasoning_effort_override: str | None = None,
) -> tuple[str, dict]:
    original_priority = os.getenv("AI_PROVIDER_PRIORITY")
    original_primary = ai.DEFAULT_OPENAI_PRIMARY_MODEL
    original_reasoning_fn = ai._openai_reasoning_effort_for_model
    try:
        os.environ["AI_PROVIDER_PRIORITY"] = "openai"
        ai.DEFAULT_OPENAI_PRIMARY_MODEL = model_name
        if reasoning_effort_override is not None:
            ai._openai_reasoning_effort_for_model = lambda _model: reasoning_effort_override
        return ai._story_response_openai(system_prompt, messages)
    finally:
        ai.DEFAULT_OPENAI_PRIMARY_MODEL = original_primary
        ai._openai_reasoning_effort_for_model = original_reasoning_fn
        if original_priority is None:
            os.environ.pop("AI_PROVIDER_PRIORITY", None)
        else:
            os.environ["AI_PROVIDER_PRIORITY"] = original_priority


def _comparison_dir() -> Path:
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "transcripts" / "model-comparisons"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _markdown_dir() -> Path:
    out_dir = _comparison_dir() / "markdown"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _json_dir() -> Path:
    out_dir = _comparison_dir() / "json"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def _default_state_path(session_id: str, scene_log_id: str) -> Path:
    return _json_dir() / f"{_timestamp()}_{session_id}_{scene_log_id}_comparison-state.json"


def _default_markdown_path(session_id: str, scene_log_id: str, label: str) -> Path:
    return _markdown_dir() / f"{_timestamp()}_{session_id}_{scene_log_id}_{label}_openai-model-compare.md"


def _write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _load_state(path: str) -> dict[str, Any]:
    state_path = Path(path).expanduser()
    return json.loads(state_path.read_text(encoding="utf-8"))


def _save_state(path: str | Path, state: dict[str, Any]) -> Path:
    state_path = Path(path).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(_json_dump(state), encoding="utf-8")
    return state_path


def _state_messages_after_start(turn: int, input_messages: list[dict], generated_narration: str) -> list[dict]:
    if turn == 0:
        return [{"role": "assistant", "content": generated_narration}]
    return [*input_messages, {"role": "assistant", "content": generated_narration}]


def _start(args) -> int:
    db = SessionLocal()
    try:
        session = db.get(GameSession, args.session_id)
        if session is None:
            raise SystemExit(f"Session not found: {args.session_id}")
        scene_log = _resolve_target_scene_log(db, args.session_id, args.scene_log_id, args.scene_index)
        state = _base_scene_context(db, session, scene_log)

        scene_messages = main._scene_messages(db, scene_log.id)
        if args.turn == 0:
            input_messages = [{"role": "user", "content": main._scene_start_marker(state["locale"])}]
            current_round = 1
            mode = "opening"
            last_user_message = ""
        else:
            input_messages = _messages_before_target(scene_messages, args.turn)
            current_round = main._prompt_round_for_turn(args.turn - 1, int(state["rounds"]))
            mode = "turn"
            last_user_message = next((msg["content"] for msg in reversed(input_messages) if msg["role"] == "user"), "")

        system_prompt = _build_system_prompt(state, current_round)
        original_text = _original_response_for_turn(scene_messages, args.turn)
        raw_a, debug_a = _compare_openai_model(system_prompt, input_messages, args.model_a, args.reasoning_a)
        raw_b, debug_b = _compare_openai_model(system_prompt, input_messages, args.model_b, args.reasoning_b)
        narration_a, options_a = _postprocess_output(state, raw_a, current_round, last_user_message, mode)
        narration_b, options_b = _postprocess_output(state, raw_b, current_round, last_user_message, mode)

        state.update(
            {
                "version": 1,
                "completed_user_turns": args.turn,
                "reasoning_a": args.reasoning_a,
                "reasoning_b": args.reasoning_b,
                "models": {
                    "a": {
                        "name": args.model_a,
                        "history": _state_messages_after_start(args.turn, input_messages, narration_a),
                        "last_options": options_a,
                    },
                    "b": {
                        "name": args.model_b,
                        "history": _state_messages_after_start(args.turn, input_messages, narration_b),
                        "last_options": options_b,
                    },
                },
            }
        )

        state_path = _save_state(args.state_out or _default_state_path(session.id, scene_log.id), state)
        markdown_path = Path(args.out).expanduser() if args.out else _default_markdown_path(session.id, scene_log.id, "start")
        _write_markdown(
            markdown_path,
            [
                "# OpenAI Story Model Comparison",
                "",
                f"- session_id: `{session.id}`",
                f"- scene_log_id: `{scene_log.id}`",
                f"- scene_kind: `{state['scene_kind']}`",
                f"- scene_id: `{state['scene_id']}`",
                f"- locale: `{state['locale']}`",
                f"- target: `{'opening' if args.turn == 0 else f'turn {args.turn}'}`",
                f"- model_a: `{args.model_a}`",
                f"- model_b: `{args.model_b}`",
                f"- reasoning_a: `{args.reasoning_a or 'default'}`",
                f"- reasoning_b: `{args.reasoning_b or 'default'}`",
                f"- state_file: `{state_path}`",
                "",
                "## System Prompt",
                "",
                "```text",
                system_prompt,
                "```",
                "",
                "## Input Messages",
                "",
                _format_messages(input_messages),
                "",
                "## Original Stored Response",
                "",
                "```text",
                original_text.strip(),
                "```",
                "",
                _render_output_section(
                    f"Candidate A: {args.model_a}",
                    {
                        "provider": "openai",
                        "model": args.model_a,
                        "raw_text": raw_a,
                        "narration": narration_a,
                        "options": options_a,
                        "debug": {**debug_a, "reasoning_effort_override": args.reasoning_a},
                    },
                ),
                "",
                _render_output_section(
                    f"Candidate B: {args.model_b}",
                    {
                        "provider": "openai",
                        "model": args.model_b,
                        "raw_text": raw_b,
                        "narration": narration_b,
                        "options": options_b,
                        "debug": {**debug_b, "reasoning_effort_override": args.reasoning_b},
                    },
                ),
                "",
            ],
        )
        print(markdown_path)
        print(state_path)
        return 0
    finally:
        db.close()


def _start_single(args) -> int:
    db = SessionLocal()
    try:
        session = db.get(GameSession, args.session_id)
        if session is None:
            raise SystemExit(f"Session not found: {args.session_id}")
        scene_log = _resolve_target_scene_log(db, args.session_id, args.scene_log_id, args.scene_index)
        state = _base_scene_context(db, session, scene_log)

        scene_messages = main._scene_messages(db, scene_log.id)
        if args.turn == 0:
            input_messages = [{"role": "user", "content": main._scene_start_marker(state["locale"])}]
            current_round = 1
            mode = "opening"
            last_user_message = ""
        else:
            input_messages = _messages_before_target(scene_messages, args.turn)
            current_round = main._prompt_round_for_turn(args.turn - 1, int(state["rounds"]))
            mode = "turn"
            last_user_message = next((msg["content"] for msg in reversed(input_messages) if msg["role"] == "user"), "")

        system_prompt = _build_system_prompt(state, current_round)
        original_text = _original_response_for_turn(scene_messages, args.turn)
        raw_text, debug = _compare_openai_model(system_prompt, input_messages, args.model, args.reasoning)
        narration, options = _postprocess_output(state, raw_text, current_round, last_user_message, mode)

        branch = args.branch
        state.update(
            {
                "version": 1,
                "completed_user_turns": args.turn,
                f"reasoning_{branch}": args.reasoning,
                "models": {
                    branch: {
                        "name": args.model,
                        "history": _state_messages_after_start(args.turn, input_messages, narration),
                        "last_options": options,
                    }
                },
            }
        )

        state_path = _save_state(args.state_out or _default_state_path(session.id, scene_log.id), state)
        markdown_path = Path(args.out).expanduser() if args.out else _default_markdown_path(session.id, scene_log.id, f"start-branch-{branch}")
        _write_markdown(
            markdown_path,
            [
                "# OpenAI Story Model Single-Branch Start",
                "",
                f"- session_id: `{session.id}`",
                f"- scene_log_id: `{scene_log.id}`",
                f"- scene_kind: `{state['scene_kind']}`",
                f"- scene_id: `{state['scene_id']}`",
                f"- locale: `{state['locale']}`",
                f"- target: `{'opening' if args.turn == 0 else f'turn {args.turn}'}`",
                f"- branch: `{branch}`",
                f"- model: `{args.model}`",
                f"- reasoning: `{args.reasoning or 'default'}`",
                f"- state_file: `{state_path}`",
                "",
                "## System Prompt",
                "",
                "```text",
                system_prompt,
                "```",
                "",
                "## Input Messages",
                "",
                _format_messages(input_messages),
                "",
                "## Original Stored Response",
                "",
                "```text",
                original_text.strip(),
                "```",
                "",
                _render_output_section(
                    f"Candidate {branch.upper()}: {args.model}",
                    {
                        "provider": "openai",
                        "model": args.model,
                        "raw_text": raw_text,
                        "narration": narration,
                        "options": options,
                        "debug": {**debug, "reasoning_effort_override": args.reasoning},
                    },
                ),
                "",
            ],
        )
        print(markdown_path)
        print(state_path)
        return 0
    finally:
        db.close()


def _continue(args) -> int:
    state_path = Path(args.state).expanduser()
    state = _load_state(str(state_path))
    completed_user_turns = int(state.get("completed_user_turns", 0))
    next_user_turn = completed_user_turns + 1
    current_round = main._prompt_round_for_turn(completed_user_turns, int(state["rounds"]))
    system_prompt = _build_system_prompt(state, current_round)
    user_message = args.user_message.strip()
    if not user_message:
        raise SystemExit("--user-message cannot be empty")

    outputs: dict[str, dict[str, Any]] = {}
    for key in ("a", "b"):
        model_state = dict(state["models"][key])
        model_name = model_state["name"]
        input_messages = [*model_state["history"], {"role": "user", "content": user_message}]
        reasoning_key = f"reasoning_{key}"
        raw_text, debug = _compare_openai_model(system_prompt, input_messages, model_name, state.get(reasoning_key))
        narration, options = _postprocess_output(state, raw_text, current_round, user_message, "turn")
        model_state["history"] = [*input_messages, {"role": "assistant", "content": narration}]
        model_state["last_options"] = options
        state["models"][key] = model_state
        outputs[key] = {
            "provider": "openai",
            "model": model_name,
            "raw_text": raw_text,
            "narration": narration,
            "options": options,
            "debug": {**debug, "reasoning_effort_override": state.get(reasoning_key)},
            "input_messages": input_messages,
        }

    state["completed_user_turns"] = next_user_turn
    _save_state(state_path, state)
    markdown_path = Path(args.out).expanduser() if args.out else _default_markdown_path(state["session_id"], state["scene_log_id"], f"continue-turn-{next_user_turn}")
    _write_markdown(
        markdown_path,
        [
            "# OpenAI Story Model Comparison",
            "",
            f"- session_id: `{state['session_id']}`",
            f"- scene_log_id: `{state['scene_log_id']}`",
            f"- scene_kind: `{state['scene_kind']}`",
            f"- scene_id: `{state['scene_id']}`",
            f"- locale: `{state['locale']}`",
            f"- continued_turn: `{next_user_turn}`",
            f"- state_file: `{state_path}`",
            "",
            "## System Prompt",
            "",
            "```text",
            system_prompt,
            "```",
            "",
            "## New User Input",
            "",
            "```text",
            user_message,
            "```",
            "",
            "## Candidate A Input History",
            "",
            _format_messages(outputs["a"]["input_messages"]),
            "",
            _render_output_section(f"Candidate A: {state['models']['a']['name']}", outputs["a"]),
            "",
            "## Candidate B Input History",
            "",
            _format_messages(outputs["b"]["input_messages"]),
            "",
            _render_output_section(f"Candidate B: {state['models']['b']['name']}", outputs["b"]),
            "",
        ],
    )
    print(markdown_path)
    print(state_path)
    return 0


def _continue_single(args) -> int:
    state_path = Path(args.state).expanduser()
    state = _load_state(str(state_path))
    branch = args.branch
    if branch not in ("a", "b"):
        raise SystemExit("--branch must be 'a' or 'b'")

    completed_user_turns = int(state.get("completed_user_turns", 0))
    next_user_turn = completed_user_turns + 1
    current_round = main._prompt_round_for_turn(completed_user_turns, int(state["rounds"]))
    system_prompt = _build_system_prompt(state, current_round)
    user_message = args.user_message.strip()
    if not user_message:
        raise SystemExit("--user-message cannot be empty")

    model_state = dict(state["models"][branch])
    model_name = args.model or model_state["name"]
    default_reasoning = state.get(f"reasoning_{branch}")
    reasoning_effort = args.reasoning if args.reasoning is not None else default_reasoning
    input_messages = [*model_state["history"], {"role": "user", "content": user_message}]
    raw_text, debug = _compare_openai_model(system_prompt, input_messages, model_name, reasoning_effort)
    narration, options = _postprocess_output(state, raw_text, current_round, user_message, "turn")

    output = {
        "provider": "openai",
        "model": model_name,
        "raw_text": raw_text,
        "narration": narration,
        "options": options,
        "debug": {**debug, "reasoning_effort_override": reasoning_effort},
        "input_messages": input_messages,
    }

    if args.state_out:
        next_state = json.loads(_json_dump(state))
        next_model_state = dict(next_state["models"][branch])
        next_model_state["name"] = model_name
        next_model_state["history"] = [*input_messages, {"role": "assistant", "content": narration}]
        next_model_state["last_options"] = options
        next_state["models"][branch] = next_model_state
        next_state["completed_user_turns"] = next_user_turn
        next_state[f"reasoning_{branch}"] = reasoning_effort
        _save_state(args.state_out, next_state)

    markdown_path = (
        Path(args.out).expanduser()
        if args.out
        else _default_markdown_path(
            state["session_id"],
            state["scene_log_id"],
            f"continue-turn-{next_user_turn}-branch-{branch}",
        )
    )
    _write_markdown(
        markdown_path,
        [
            "# OpenAI Story Model Single-Branch Continuation",
            "",
            f"- session_id: `{state['session_id']}`",
            f"- scene_log_id: `{state['scene_log_id']}`",
            f"- scene_kind: `{state['scene_kind']}`",
            f"- scene_id: `{state['scene_id']}`",
            f"- locale: `{state['locale']}`",
            f"- continued_turn: `{next_user_turn}`",
            f"- source_state_file: `{state_path}`",
            f"- branch: `{branch}`",
            f"- model: `{model_name}`",
            f"- reasoning: `{reasoning_effort or 'default'}`",
            "",
            "## System Prompt",
            "",
            "```text",
            system_prompt,
            "```",
            "",
            "## Input History",
            "",
            _format_messages(input_messages),
            "",
            _render_output_section(f"Candidate {branch.upper()}: {model_name}", output),
            "",
        ],
    )
    print(markdown_path)
    if args.state_out:
        print(Path(args.state_out).expanduser())
    return 0


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Compare OpenAI story model outputs and continue both branches across turns.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start a comparison from an existing session scene.")
    start_parser.add_argument("--session-id", required=True, help="Game session id")
    start_parser.add_argument("--scene-log-id", help="Specific scene_log id in the session")
    start_parser.add_argument("--scene-index", type=int, help="1-based scene index within the session")
    start_parser.add_argument("--turn", type=int, default=0, help="0 = opening, 1+ = assistant response after that user turn")
    start_parser.add_argument("--model-a", default="gpt-4.1-mini")
    start_parser.add_argument("--model-b", default="gpt-5-mini")
    start_parser.add_argument("--reasoning-a", choices=["minimal", "low", "medium", "high"])
    start_parser.add_argument("--reasoning-b", choices=["minimal", "low", "medium", "high"])
    start_parser.add_argument("--out", help="Output markdown path")
    start_parser.add_argument("--state-out", help="Output state json path")

    start_single_parser = subparsers.add_parser("start-single", help="Start a single model branch from an existing session scene.")
    start_single_parser.add_argument("--session-id", required=True, help="Game session id")
    start_single_parser.add_argument("--scene-log-id", help="Specific scene_log id in the session")
    start_single_parser.add_argument("--scene-index", type=int, help="1-based scene index within the session")
    start_single_parser.add_argument("--turn", type=int, default=0, help="0 = opening, 1+ = assistant response after that user turn")
    start_single_parser.add_argument("--branch", required=True, choices=["a", "b"])
    start_single_parser.add_argument("--model", required=True)
    start_single_parser.add_argument("--reasoning", choices=["minimal", "low", "medium", "high"])
    start_single_parser.add_argument("--out", help="Output markdown path")
    start_single_parser.add_argument("--state-out", help="Output state json path")

    continue_parser = subparsers.add_parser("continue", help="Continue both model branches with a new user message.")
    continue_parser.add_argument("--state", required=True, help="Path to comparison state json")
    continue_parser.add_argument("--user-message", required=True, help="New player message to append to both branches")
    continue_parser.add_argument("--out", help="Output markdown path")

    continue_single_parser = subparsers.add_parser("continue-single", help="Continue one model branch with a new user message.")
    continue_single_parser.add_argument("--state", required=True, help="Path to comparison state json")
    continue_single_parser.add_argument("--branch", required=True, choices=["a", "b"], help="Which stored branch history to continue")
    continue_single_parser.add_argument("--user-message", required=True, help="New player message to append")
    continue_single_parser.add_argument("--model", help="Override model name for this branch")
    continue_single_parser.add_argument("--reasoning", choices=["minimal", "low", "medium", "high"], help="Override reasoning effort")
    continue_single_parser.add_argument("--out", help="Output markdown path")
    continue_single_parser.add_argument("--state-out", help="Optional output state json for the continued branch")

    args = parser.parse_args()
    if args.command == "start":
        if args.scene_log_id and args.scene_index is not None:
            raise SystemExit("Use either --scene-log-id or --scene-index, not both.")
        if args.turn < 0:
            raise SystemExit("--turn must be >= 0")
        return _start(args)
    if args.command == "start-single":
        if args.scene_log_id and args.scene_index is not None:
            raise SystemExit("Use either --scene-log-id or --scene-index, not both.")
        if args.turn < 0:
            raise SystemExit("--turn must be >= 0")
        return _start_single(args)
    if args.command == "continue-single":
        return _continue_single(args)
    return _continue(args)


if __name__ == "__main__":
    raise SystemExit(main_cli())
