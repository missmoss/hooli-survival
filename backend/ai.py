import difflib
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from enum import Enum
from typing import Any
from typing import Literal

import certifi
from google import genai
from google.genai import types
from pydantic import BaseModel

from prompt_registry import default_player_name, get_prompt_bundle, normalize_locale


GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL = "gpt-4.1-mini"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
STORY_FALLBACK_TEXT = "(The system could not generate the scene right now. Please try again shortly.)"
CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")
OPTION_LINE_RE = re.compile(r"^\s*(?:[*_`]\s*)*([ABC])(?:\s*[*_`])*\s*[\.\)）．、:：-]\s+.+", re.IGNORECASE)
SENTENCE_END_RE = re.compile(r"[。！？?!.」』\"]\s*$")
SUSPICIOUS_TRAILING_RE = re.compile(r"[「『（([{：:，、…-]\s*$")
COMPLETE_BOUNDARY_RE = re.compile(r"[。！？?!.](?:[」』\"])?")
CONTEXT_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]+")
PLACEHOLDER_RE = re.compile(
    r"\[(?:[^\]\n]{0,80}(?:請在此處|待填|TODO|姓名|名字|接續|placeholder)[^\]\n]*)\]"
)
LEAKED_RETRY_NOTE_RE = re.compile(r"(我上一版輸出在句中中斷或格式不完整|my previous output was cut off or malformed)", re.IGNORECASE)
CONTEXT_STOPWORDS = {
    "這個",
    "那個",
    "我們",
    "你們",
    "他們",
    "目前",
    "問題",
    "服務",
    "ticket",
    "tickets",
    "service",
    "issue",
}


def _has_balanced_story_delimiters(text: str) -> bool:
    pairs = [
        ("「", "」"),
        ("『", "』"),
        ("（", "）"),
        ("“", "”"),
    ]
    for opener, closer in pairs:
        if text.count(opener) != text.count(closer):
            return False
    if text.count('"') % 2 != 0:
        return False
    return True


def _has_incomplete_dialogue_tail(last_line: str) -> bool:
    line = (last_line or "").strip()
    if not line:
        return False
    for opener, closer in [('"', '"'), ("“", "”"), ("「", "」"), ("『", "』")]:
        opener_index = line.rfind(opener)
        if opener_index == -1:
            continue
        prefix = line[:opener_index]
        if ":" not in prefix and "：" not in prefix:
            continue
        closer_index = line.find(closer, opener_index + 1)
        if closer_index == -1:
            return True
    return False


def _is_zh(locale: str | None) -> bool:
    return normalize_locale(locale) == "zh-Hant"


def _memory_prompt(locale: str | None) -> str:
    return get_prompt_bundle(locale).MEMORY_PROMPT


def _perf_artifact_prompt(locale: str | None) -> str:
    return get_prompt_bundle(locale).PERF_ARTIFACT_PROMPT


def _memory_fallback(locale: str | None) -> str:
    return "玩家完成了本場景互動，整體表現中性。" if _is_zh(locale) else "The player completed the scene interaction with an overall neutral performance."


class EvalResult(BaseModel):
    rating: Literal["good", "neutral", "bad"]
    reason: str


class PerfArtifactResult(BaseModel):
    title: str
    summary: str
    framing_a: str
    framing_b: str


EVAL_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rating": {"type": "string", "enum": ["good", "neutral", "bad"]},
        "reason": {"type": "string"},
    },
    "required": ["rating", "reason"],
}

PERF_ARTIFACT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "framing_a": {"type": "string"},
        "framing_b": {"type": "string"},
    },
    "required": ["title", "summary", "framing_a", "framing_b"],
}


def _client() -> genai.Client | None:
    api_key = os.getenv(GEMINI_API_KEY_ENV)
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _anthropic_api_key() -> str:
    return os.getenv(ANTHROPIC_API_KEY_ENV, "").strip()


def _anthropic_available() -> bool:
    return bool(_anthropic_api_key())


def _openai_api_key() -> str:
    return os.getenv(OPENAI_API_KEY_ENV, "").strip()


def _openai_available() -> bool:
    return bool(_openai_api_key())


def _provider_priority() -> list[str]:
    configured = [
        token.strip().lower()
        for token in os.getenv("AI_PROVIDER_PRIORITY", "").split(",")
        if token.strip()
    ]
    if not configured:
        configured = ["gemini", "anthropic", "openai"]

    order: list[str] = []
    for provider in configured:
        if provider == "gemini" and _client() is not None:
            order.append("gemini")
        elif provider == "anthropic" and _anthropic_available():
            order.append("anthropic")
        elif provider == "openai" and _openai_available():
            order.append("openai")
    return order


def _anthropic_messages(messages: list[dict]) -> list[dict]:
    converted: list[dict] = []
    for msg in messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        converted.append({"role": role, "content": msg["content"]})
    return converted


def _openai_input_messages(messages: list[dict]) -> list[dict]:
    converted: list[dict] = []
    for msg in messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        content_type = "output_text" if role == "assistant" else "input_text"
        converted.append(
            {
                "role": role,
                "content": [{"type": content_type, "text": str(msg["content"])}],
            }
        )
    return converted


def _anthropic_models() -> list[str]:
    return [CLAUDE_MODEL]


def _openai_models() -> list[str]:
    return [OPENAI_MODEL]


def _openai_reasoning_effort_for_model(model: str) -> str | None:
    normalized = (model or "").strip().lower()
    if normalized.startswith("gpt-5-mini") or normalized.startswith("gpt-5-nano"):
        return "minimal"
    if normalized.startswith("gpt-5"):
        return "none"
    return None


def _openai_verbosity_for_model(model: str) -> str | None:
    normalized = (model or "").strip().lower()
    if normalized.startswith("gpt-5"):
        return "low"
    return None


def _openai_temperature_for_model(model: str, requested: float | None) -> float | None:
    normalized = (model or "").strip().lower()
    if normalized.startswith("gpt-5"):
        return None
    return requested


def _latency_ms(start: float, end: float) -> int:
    return max(0, int(round((end - start) * 1000)))


def _anthropic_request(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": _anthropic_messages(messages),
    }
    if temperature is not None:
        payload["temperature"] = temperature

    request = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": _anthropic_api_key(),
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"AnthropicHTTPError: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AnthropicURLError: {exc.reason}") from exc


def _openai_request(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float | None = None,
    verbosity: str | None = None,
    reasoning_effort: str | None = None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "instructions": system,
        "input": _openai_input_messages(messages),
        "max_output_tokens": max_tokens,
        "store": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if reasoning_effort is not None:
        payload["reasoning"] = {"effort": reasoning_effort}

    text_payload: dict[str, Any] = {"format": response_format or {"type": "text"}}
    if verbosity is not None:
        text_payload["verbosity"] = verbosity
    payload["text"] = text_payload

    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {_openai_api_key()}",
            "content-type": "application/json",
        },
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"OpenAIHTTPError: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAIURLError: {exc.reason}") from exc


def _anthropic_text(payload: dict[str, Any]) -> str:
    parts = payload.get("content") or []
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            text = str(part.get("text", "")).strip()
            if text:
                texts.append(text)
    return "\n".join(texts).strip()


def _openai_text(payload: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = str(content.get("text", "")).strip()
                if text:
                    texts.append(text)
    return "\n".join(texts).strip()


def _anthropic_debug_payload(payload: dict[str, Any], mode: str, model: str) -> dict[str, Any]:
    return {
        "provider": "anthropic",
        "mode": mode,
        "model": model,
        "text": _anthropic_text(payload),
        "stop_reason": payload.get("stop_reason"),
        "raw": _json_safe(payload),
    }


def _openai_debug_payload(payload: dict[str, Any], mode: str, model: str) -> dict[str, Any]:
    return {
        "provider": "openai",
        "mode": mode,
        "model": model,
        "text": _openai_text(payload),
        "status": payload.get("status"),
        "incomplete_details": _json_safe(payload.get("incomplete_details")),
        "error": _json_safe(payload.get("error")),
        "usage": _json_safe(payload.get("usage")),
        "raw": _json_safe(payload),
    }


def _to_contents(messages: list[dict]) -> list[dict]:
    return [
        {
            "role": "model" if msg["role"] == "assistant" else msg["role"],
            "parts": [{"text": msg["content"]}],
        }
        for msg in messages
    ]


def _strip_code_fence(text: str) -> str:
    raw = (text or "").strip()
    match = CODE_BLOCK_RE.search(raw)
    if match:
        return match.group(1).strip()
    if not raw.startswith("```"):
        return raw

    lines = raw.splitlines()
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_response_text(response) -> str:
    text = (getattr(response, "text", None) or "").strip()
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    fragments: list[str] = []
    for part in parts:
        part_text = getattr(part, "text", None)
        if isinstance(part_text, str) and part_text.strip():
            fragments.append(part_text)
    return "\n".join(fragments).strip()


def _extract_finish_reason(response) -> str:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return ""
    return str(reason)


def _looks_like_complete_story(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if PLACEHOLDER_RE.search(stripped):
        return False
    if LEAKED_RETRY_NOTE_RE.search(stripped):
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False

    last_line = lines[-1]
    if _has_incomplete_dialogue_tail(last_line):
        return False
    if not _has_balanced_story_delimiters(stripped):
        return False
    if OPTION_LINE_RE.match(last_line):
        return True
    if SENTENCE_END_RE.search(last_line):
        return True
    if SUSPICIOUS_TRAILING_RE.search(last_line):
        return False
    return False


def _trim_to_complete_story(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if PLACEHOLDER_RE.search(stripped):
        return ""
    if LEAKED_RETRY_NOTE_RE.search(stripped):
        return ""

    lines = [line.rstrip() for line in stripped.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""

    if OPTION_LINE_RE.match(lines[-1].strip()):
        return "\n".join(lines).strip()

    joined = "\n".join(lines).strip()
    matches = list(COMPLETE_BOUNDARY_RE.finditer(joined))
    if not matches:
        return ""

    for match in reversed(matches):
        candidate = joined[: match.end()].strip()
        if _looks_like_complete_story(candidate) and _is_usable_trimmed_story(candidate):
            return candidate
    return ""


def _is_usable_trimmed_story(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False
    if OPTION_LINE_RE.match(lines[-1]):
        return True
    sentence_count = len(COMPLETE_BOUNDARY_RE.findall(stripped))
    if sentence_count >= 3:
        return True
    return sentence_count >= 2 and len(stripped) >= 220


def _story_context_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in CONTEXT_TOKEN_RE.finditer((text or "").strip()):
        value = match.group(0)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,}", value):
            tokens.add(value.lower())
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", value):
            han = value
            for size in range(2, min(4, len(han)) + 1):
                for index in range(0, len(han) - size + 1):
                    tokens.add(han[index : index + size])
    return {token for token in tokens if token not in CONTEXT_STOPWORDS}


def _latest_story_user_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def _latest_story_assistant_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant":
            return str(message.get("content") or "").strip()
    return ""


def _token_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _normalized_story_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _previous_assistant_prefix_duplicate_ratio(text: str, messages: list[dict]) -> float:
    previous_assistant = _normalized_story_text(_latest_story_assistant_message(messages))
    candidate = _normalized_story_text(text)
    if not previous_assistant or not candidate:
        return 0.0

    candidate_prefix = candidate[: len(previous_assistant)]
    if not candidate_prefix:
        return 0.0
    return difflib.SequenceMatcher(a=previous_assistant, b=candidate_prefix).ratio()


def _trimmed_story_matches_turn_context(text: str, messages: list[dict]) -> bool:
    latest_user = _latest_story_user_message(messages)
    if not latest_user:
        return True
    if latest_user.startswith("【場景開始】") or latest_user.startswith("[SCENE START]"):
        return True

    if _previous_assistant_prefix_duplicate_ratio(text, messages) >= 0.9:
        return False

    user_tokens = _story_context_tokens(latest_user)
    candidate_tokens = _story_context_tokens(text)
    if len(user_tokens) >= 2:
        return bool(user_tokens & candidate_tokens)

    previous_assistant_tokens = _story_context_tokens(_latest_story_assistant_message(messages))
    return _token_overlap_ratio(candidate_tokens, previous_assistant_tokens) < 0.6


def _parse_eval_json(text: str) -> tuple[str, str] | None:
    raw = _strip_code_fence(text)
    if not raw:
        return None

    # Try direct JSON first.
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(raw)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    rating = parsed.get("rating", "neutral")
    reason = str(parsed.get("reason", "")).strip()
    if rating in {"good", "neutral", "bad"}:
        return rating, (reason or "未提供判定理由。")
    return None


def _parse_eval_response(response) -> tuple[str, str] | None:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, EvalResult):
        return parsed.rating, parsed.reason.strip() or "未提供判定理由。"
    if isinstance(parsed, dict):
        rating = str(parsed.get("rating", "")).strip()
        reason = str(parsed.get("reason", "")).strip()
        if rating in {"good", "neutral", "bad"}:
            return rating, (reason or "未提供判定理由。")
    return _parse_eval_json(_extract_response_text(response))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump())
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _response_debug_payload(response, mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "text": getattr(response, "text", None),
        "parsed": _json_safe(getattr(response, "parsed", None)),
        "finish_reason": _extract_finish_reason(response),
        "model_dump": _json_safe(response.model_dump()),
    }


def _story_models() -> list[str]:
    return [GEMINI_MODEL]


def _is_retryable_story_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".upper()
    retry_markers = [
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "DEADLINE_EXCEEDED",
        "INTERNAL",
        "TIMEOUT",
        "CONNECTION",
    ]
    return any(marker in text for marker in retry_markers)


def _is_retryable_anthropic_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".upper()
    retry_markers = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "529",
        "OVERLOADED",
        "TIMEOUT",
        "CONNECTION",
        "SSL",
    ]
    return any(marker in text for marker in retry_markers)


def _is_retryable_openai_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".upper()
    retry_markers = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "RATE_LIMIT",
        "TIMEOUT",
        "CONNECTION",
        "OVERLOADED",
    ]
    return any(marker in text for marker in retry_markers)


def _fallback_text_eval(
    client: genai.Client, eval_prompt: str, transcript_text: str
) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=eval_prompt,
                temperature=0,
                response_mime_type="application/json",         
                max_output_tokens=5000,
            ),
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"{transcript_text}\n\n"
                                "只輸出一個 JSON 物件，必須包含 rating 與 reason。"
                                "不要有任何前言、後記或 markdown code block。"
                            )
                        }
                    ],
                }
            ],
        )
    except Exception as exc:
        return None, {"mode": "text_fallback", "error": f"{type(exc).__name__}: {exc}"}
    return _parse_eval_json(_extract_response_text(response)), _response_debug_payload(
        response, "text_fallback"
    )


def _story_response_openai(system_prompt: str, messages: list[dict]) -> tuple[str, dict[str, Any]]:
    if not _openai_available():
        return STORY_FALLBACK_TEXT, {"source": "no_openai_client", "attempts": [], "fallback": True}

    best_partial = ""
    attempts: list[dict[str, Any]] = []
    base_messages = list(messages)

    for model_index, model_name in enumerate(_openai_models()):
        model_messages = list(base_messages)
        for attempt in range(2):
            attempt_label = f"openai_story_attempt_{len(attempts) + 1}"
            try:
                started_at = time.perf_counter()
                payload = _openai_request(
                    model=model_name,
                    system=system_prompt,
                    messages=model_messages,
                    max_tokens=2048,
                    temperature=_openai_temperature_for_model(model_name, 0.7),
                    verbosity=_openai_verbosity_for_model(model_name),
                    reasoning_effort=_openai_reasoning_effort_for_model(model_name),
                )
                finished_at = time.perf_counter()
            except Exception as exc:
                retryable = _is_retryable_openai_error(exc)
                attempts.append(
                    {
                        "provider": "openai",
                        "mode": attempt_label,
                        "model": model_name,
                        "retryable": retryable,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                if retryable:
                    time.sleep(0.8 * (attempt + 1))
                continue

            text = _openai_text(payload)
            attempt_payload = _openai_debug_payload(payload, attempt_label, model_name)
            attempt_payload["latency_ms"] = _latency_ms(started_at, finished_at)
            attempt_payload["complete"] = _looks_like_complete_story(text)
            attempts.append(attempt_payload)
            status = str(payload.get("status", "") or "")
            if _looks_like_complete_story(text) and status == "completed":
                return text, {
                    "provider": "openai",
                    "source": attempt_label,
                    "model": model_name,
                    "attempts": attempts,
                    "fallback": False,
                }
            trimmed = _trim_to_complete_story(text)
            if len(trimmed) > len(best_partial):
                best_partial = trimmed

        if model_index < len(_openai_models()) - 1:
            time.sleep(1.0)

    if best_partial and _trimmed_story_matches_turn_context(best_partial, messages):
        return best_partial, {
            "provider": "openai",
            "source": "trimmed_partial",
            "attempts": attempts,
            "fallback": False,
        }
    return STORY_FALLBACK_TEXT, {
        "provider": "openai",
        "source": "rejected_trimmed_partial" if best_partial else "fallback_text",
        "models": _openai_models(),
        "attempts": attempts,
        "fallback": True,
        "trimmed_partial_rejected": bool(best_partial),
    }


def _story_response_claude(system_prompt: str, messages: list[dict]) -> tuple[str, dict[str, Any]]:
    if not _anthropic_available():
        return STORY_FALLBACK_TEXT, {"source": "no_anthropic_client", "attempts": [], "fallback": True}

    best_partial = ""
    attempts: list[dict[str, Any]] = []
    base_messages = list(messages)

    for model_index, model_name in enumerate(_anthropic_models()):
        model_messages = list(base_messages)
        for attempt in range(2):
            attempt_label = f"claude_story_attempt_{len(attempts) + 1}"
            try:
                started_at = time.perf_counter()
                payload = _anthropic_request(
                    model=model_name,
                    system=system_prompt,
                    messages=model_messages,
                    max_tokens=2048,
                    temperature=0.7,
                )
                finished_at = time.perf_counter()
            except Exception as exc:
                retryable = _is_retryable_anthropic_error(exc)
                attempts.append(
                    {
                        "provider": "anthropic",
                        "mode": attempt_label,
                        "model": model_name,
                        "retryable": retryable,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                if retryable:
                    time.sleep(0.8 * (attempt + 1))
                continue

            text = _anthropic_text(payload)
            attempt_payload = _anthropic_debug_payload(payload, attempt_label, model_name)
            attempt_payload["latency_ms"] = _latency_ms(started_at, finished_at)
            attempt_payload["complete"] = _looks_like_complete_story(text)
            attempts.append(attempt_payload)
            stop_reason = str(payload.get("stop_reason", "") or "")
            if _looks_like_complete_story(text) and (not stop_reason or stop_reason == "end_turn"):
                return text, {
                    "provider": "anthropic",
                    "source": attempt_label,
                    "model": model_name,
                    "attempts": attempts,
                    "fallback": False,
                }
            trimmed = _trim_to_complete_story(text)
            if len(trimmed) > len(best_partial):
                best_partial = trimmed

        if model_index < len(_anthropic_models()) - 1:
            time.sleep(1.0)

    if best_partial and _trimmed_story_matches_turn_context(best_partial, messages):
        return best_partial, {
            "provider": "anthropic",
            "source": "trimmed_partial",
            "attempts": attempts,
            "fallback": False,
        }
    return STORY_FALLBACK_TEXT, {
        "provider": "anthropic",
        "source": "rejected_trimmed_partial" if best_partial else "fallback_text",
        "models": _anthropic_models(),
        "attempts": attempts,
        "fallback": True,
        "trimmed_partial_rejected": bool(best_partial),
    }


def _story_response_gemini(system_prompt: str, messages: list[dict]) -> tuple[str, dict[str, Any]]:
    client = _client()
    if client is None:
        return STORY_FALLBACK_TEXT, {"source": "no_client", "attempts": [], "fallback": True}

    contents = _to_contents(messages)
    best_partial = ""
    attempts: list[dict[str, Any]] = []

    story_models = _story_models()
    max_attempts_per_model = 2
    for model_index, model_name in enumerate(story_models):
        model_contents = list(contents)
        for attempt in range(max_attempts_per_model):
            attempt_label = f"story_attempt_{len(attempts) + 1}"
            try:
                started_at = time.perf_counter()
                response = client.models.generate_content(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=2048,
                    ),
                    contents=model_contents,
                )
                finished_at = time.perf_counter()
            except Exception as exc:
                retryable = _is_retryable_story_error(exc)
                attempts.append(
                    {
                        "mode": attempt_label,
                        "model": model_name,
                        "retryable": retryable,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                if retryable:
                    time.sleep(0.6 * (attempt + 1))
                continue

            text = _extract_response_text(response)
            finish_reason = _extract_finish_reason(response)
            attempt_payload = _response_debug_payload(response, attempt_label)
            attempt_payload["latency_ms"] = _latency_ms(started_at, finished_at)
            attempt_payload["model"] = model_name
            attempt_payload["complete"] = _looks_like_complete_story(text)
            attempts.append(attempt_payload)
            if _looks_like_complete_story(text) and (
                not finish_reason or finish_reason.endswith("STOP")
            ):
                return text, {
                    "provider": "gemini",
                    "source": attempt_payload["mode"],
                    "model": model_name,
                    "attempts": attempts,
                    "fallback": False,
                }
            trimmed = _trim_to_complete_story(text)
            if len(trimmed) > len(best_partial):
                best_partial = trimmed

        contents = list(contents)
        if model_index < len(story_models) - 1:
            time.sleep(0.8)

    if best_partial and _trimmed_story_matches_turn_context(best_partial, messages):
        return best_partial, {
            "provider": "gemini",
            "source": "trimmed_partial",
            "attempts": attempts,
            "fallback": False,
        }
    return STORY_FALLBACK_TEXT, {
        "provider": "gemini",
        "source": "rejected_trimmed_partial" if best_partial else "fallback_text",
        "models": story_models,
        "attempts": attempts,
        "fallback": True,
        "trimmed_partial_rejected": bool(best_partial),
    }


def story_response(system_prompt: str, messages: list[dict]) -> tuple[str, dict[str, Any]]:
    provider_debugs: dict[str, dict[str, Any]] = {}
    last_text = STORY_FALLBACK_TEXT
    last_debug: dict[str, Any] = {"provider": "system", "source": "no_provider_attempted", "fallback": True}
    for provider in _provider_priority():
        if provider == "openai":
            text, debug = _story_response_openai(system_prompt, messages)
        elif provider == "anthropic":
            text, debug = _story_response_claude(system_prompt, messages)
        else:
            text, debug = _story_response_gemini(system_prompt, messages)
        provider_debugs[provider] = debug
        last_text = text
        last_debug = debug
        if not debug.get("fallback"):
            combined = dict(debug)
            if provider_debugs:
                combined["fallback_chain"] = provider_debugs
            return text, combined
    combined = dict(last_debug)
    combined["provider_failures"] = provider_debugs
    combined["fallback"] = True
    combined["source"] = "all_providers_fallback"
    return last_text, combined


def _evaluate_rating_claude(eval_prompt: str, transcript_text: str) -> tuple[str, str, dict[str, Any]]:
    if not _anthropic_available():
        return "neutral", "未連線 Claude Eval。", {"source": "no_anthropic_client", "attempts": []}

    last_error = ""
    last_raw_output = ""
    attempts: list[dict[str, Any]] = []
    for attempt in range(2):
        user_text = transcript_text
        if attempt == 1:
            user_text = (
                f"{transcript_text}\n\n"
                f"你上一個輸出不合法：{last_raw_output or '（空輸出）'}\n"
                "請重新輸出合法 JSON，且必須包含 rating 與 reason 兩個欄位。"
                "不要有任何前言、後記或 markdown code block。"
            )
        for model_name in _anthropic_models():
            mode = f"claude_eval_attempt_{len(attempts) + 1}"
            try:
                payload = _anthropic_request(
                    model=model_name,
                    system=eval_prompt,
                    messages=[{"role": "user", "content": user_text}],
                    max_tokens=600,
                    temperature=0,
                )
                text = _anthropic_text(payload)
                parsed = _parse_eval_json(text)
                attempt_payload = _anthropic_debug_payload(payload, mode, model_name)
                attempt_payload["parsed_result"] = parsed
                attempts.append(attempt_payload)
                if parsed is not None:
                    rating, reason = parsed
                    return rating, reason, {
                        "provider": "anthropic",
                        "source": mode,
                        "model": model_name,
                        "attempts": attempts,
                    }
                raw_excerpt = _strip_code_fence(text).replace("\n", " ").strip()
                last_raw_output = raw_excerpt[:500]
                if raw_excerpt:
                    last_error = f"Claude Eval JSON 解析失敗：{raw_excerpt[:160]}"
                else:
                    last_error = "Claude Eval JSON 解析失敗：模型未回傳可讀文字。"
            except Exception as exc:
                attempts.append(
                    {
                        "provider": "anthropic",
                        "mode": mode,
                        "model": model_name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                last_error = f"Claude Eval 呼叫失敗：{type(exc).__name__}: {exc}"
                if _is_retryable_anthropic_error(exc):
                    time.sleep(0.8 * (attempt + 1))
                continue
    return "neutral", (last_error or "Claude Eval 輸出解析失敗。"), {
        "provider": "anthropic",
        "source": "fallback_neutral",
        "attempts": attempts,
    }


def _fallback_text_eval_openai(
    eval_prompt: str, transcript_text: str
) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
    for model_name in _openai_models():
        try:
            started_at = time.perf_counter()
            payload = _openai_request(
                model=model_name,
                system=eval_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"{transcript_text}\n\n"
                            "只輸出一個 JSON 物件，必須包含 rating 與 reason。"
                            "不要有任何前言、後記或 markdown code block。"
                        ),
                    }
                ],
                max_tokens=800,
                temperature=_openai_temperature_for_model(model_name, 0),
                verbosity=_openai_verbosity_for_model(model_name),
                reasoning_effort=_openai_reasoning_effort_for_model(model_name),
            )
            finished_at = time.perf_counter()
        except Exception as exc:
            return None, {
                "provider": "openai",
                "mode": "text_fallback",
                "model": model_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        parsed = _parse_eval_json(_openai_text(payload))
        debug_payload = _openai_debug_payload(payload, "text_fallback", model_name)
        debug_payload["latency_ms"] = _latency_ms(started_at, finished_at)
        return parsed, debug_payload
    return None, None


def _evaluate_rating_openai(eval_prompt: str, transcript_text: str) -> tuple[str, str, dict[str, Any]]:
    if not _openai_available():
        return "neutral", "未連線 OpenAI Eval。", {"source": "no_openai_client", "attempts": []}

    last_error = ""
    last_raw_output = ""
    attempts: list[dict[str, Any]] = []
    response_format = {
        "type": "json_schema",
        "name": "eval_result",
        "schema": EVAL_JSON_SCHEMA,
        "strict": True,
    }
    for attempt in range(2):
        user_text = transcript_text
        if attempt == 1:
            user_text = (
                f"{transcript_text}\n\n"
                f"你上一個輸出不合法：{last_raw_output or '（空輸出）'}\n"
                "請重新輸出合法 JSON，且必須包含 rating 與 reason 兩個欄位。"
                "不要有任何前言、後記或 markdown code block。"
            )
        for model_name in _openai_models():
            mode = f"openai_eval_attempt_{len(attempts) + 1}"
            try:
                started_at = time.perf_counter()
                payload = _openai_request(
                    model=model_name,
                    system=eval_prompt,
                    messages=[{"role": "user", "content": user_text}],
                    max_tokens=800,
                    temperature=_openai_temperature_for_model(model_name, 0),
                    verbosity=_openai_verbosity_for_model(model_name),
                    reasoning_effort=_openai_reasoning_effort_for_model(model_name),
                    response_format=response_format,
                )
                finished_at = time.perf_counter()
                text = _openai_text(payload)
                parsed = _parse_eval_json(text)
                attempt_payload = _openai_debug_payload(payload, mode, model_name)
                attempt_payload["latency_ms"] = _latency_ms(started_at, finished_at)
                attempt_payload["parsed_result"] = parsed
                attempts.append(attempt_payload)
                if parsed is not None:
                    rating, reason = parsed
                    return rating, reason, {
                        "provider": "openai",
                        "source": mode,
                        "model": model_name,
                        "attempts": attempts,
                    }
                raw_excerpt = _strip_code_fence(text).replace("\n", " ").strip()
                last_raw_output = raw_excerpt[:500]
                if raw_excerpt:
                    last_error = f"OpenAI Eval JSON 解析失敗：{raw_excerpt[:160]}"
                else:
                    last_error = "OpenAI Eval JSON 解析失敗：模型未回傳可讀文字。"
            except Exception as exc:
                attempts.append(
                    {
                        "provider": "openai",
                        "mode": mode,
                        "model": model_name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                last_error = f"OpenAI Eval 呼叫失敗：{type(exc).__name__}: {exc}"
                if _is_retryable_openai_error(exc):
                    time.sleep(0.8 * (attempt + 1))
                continue

    fallback, fallback_debug = _fallback_text_eval_openai(eval_prompt, transcript_text)
    if fallback_debug is not None:
        fallback_debug["parsed_result"] = fallback
        attempts.append(fallback_debug)
    if fallback is not None:
        rating, reason = fallback
        return rating, reason, {
            "provider": "openai",
            "source": "text_fallback",
            "attempts": attempts,
        }
    return "neutral", (last_error or "OpenAI Eval 輸出解析失敗。"), {
        "provider": "openai",
        "source": "fallback_neutral",
        "attempts": attempts,
    }


def _evaluate_rating_gemini(eval_prompt: str, transcript_text: str) -> tuple[str, str, dict[str, Any]]:
    client = _client()
    if client is None:
        return (
            "neutral",
            "開發模式：未連線 Eval AI，預設 neutral。",
            {"source": "no_client", "attempts": []},
        )

    last_error = ""
    last_raw_output = ""
    attempts: list[dict[str, Any]] = []
    for attempt in range(2):
        user_text = transcript_text
        if attempt == 1:
            user_text = (
                f"{transcript_text}\n\n"
                f"你上一個輸出不合法：{last_raw_output or '（空輸出）'}\n"
                "請重新輸出合法 JSON，且必須包含 rating 與 reason 兩個欄位。"
                "不要有任何前言、後記或 markdown code block。"
            )
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=eval_prompt,
                    temperature=0,
                    max_output_tokens=5000,
                    response_mime_type="application/json",
                    response_schema=EvalResult,
                ),
                contents=[{"role": "user", "parts": [{"text": user_text}]}],
            )
            attempt_payload = _response_debug_payload(response, f"json_mode_attempt_{attempt + 1}")
            parsed = _parse_eval_response(response)
            attempt_payload["parsed_result"] = parsed
            attempts.append(attempt_payload)
            if parsed is not None:
                rating, reason = parsed
                return rating, reason, {
                    "provider": "gemini",
                    "source": attempt_payload["mode"],
                    "attempts": attempts,
                }
            raw_excerpt = _strip_code_fence(_extract_response_text(response)).replace("\n", " ").strip()
            last_raw_output = raw_excerpt[:500]
            if raw_excerpt:
                last_error = f"Eval AI JSON 解析失敗：{raw_excerpt[:160]}"
            else:
                last_error = "Eval AI JSON 解析失敗：模型未回傳可讀文字。"
        except Exception as exc:
            attempts.append(
                {
                    "mode": f"json_mode_attempt_{attempt + 1}",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            last_error = f"Eval AI 呼叫失敗：{type(exc).__name__}: {exc}"
            continue
    fallback, fallback_debug = _fallback_text_eval(client, eval_prompt, transcript_text)
    if fallback_debug is not None:
        fallback_debug["parsed_result"] = fallback
        attempts.append(fallback_debug)
    if fallback is not None:
        rating, reason = fallback
        return rating, reason, {
            "provider": "gemini",
            "source": "text_fallback",
            "attempts": attempts,
        }
    return "neutral", (last_error or "Eval AI 輸出解析失敗，回退 neutral。"), {
        "provider": "gemini",
        "source": "fallback_neutral",
        "attempts": attempts,
    }


def evaluate_rating(eval_prompt: str, transcript_text: str) -> tuple[str, str, dict[str, Any]]:
    provider_debugs: dict[str, dict[str, Any]] = {}
    last_result = ("neutral", "所有 Eval provider 都失敗。")
    last_debug: dict[str, Any] = {"provider": "system", "source": "no_provider_attempted", "attempts": []}
    for provider in _provider_priority():
        if provider == "openai":
            rating, reason, debug = _evaluate_rating_openai(eval_prompt, transcript_text)
        elif provider == "anthropic":
            rating, reason, debug = _evaluate_rating_claude(eval_prompt, transcript_text)
        else:
            rating, reason, debug = _evaluate_rating_gemini(eval_prompt, transcript_text)
        provider_debugs[provider] = debug
        last_result = (rating, reason)
        last_debug = debug
        if debug.get("source") != "fallback_neutral":
            combined = dict(debug)
            combined["fallback_chain"] = provider_debugs
            return rating, reason, combined
    combined = dict(last_debug)
    combined["provider_failures"] = provider_debugs
    combined["source"] = "fallback_neutral"
    combined["fallback"] = True
    return last_result[0], last_result[1], combined


def _summarize_memory_claude(transcript_text: str, locale: str | None) -> str:
    if not _anthropic_available():
        return _memory_fallback(locale)
    zh = _is_zh(locale)
    user_text = (
        f"{transcript_text}\n\n"
        + ("只輸出 2-3 句摘要，使用第三人稱「玩家」，保留具體行為與結果。" if zh else 'Output only a 2-3 sentence summary using third person "the player" and keep the concrete actions and outcomes.')
    )
    for model_name in _anthropic_models():
        try:
            started_at = time.perf_counter()
            payload = _anthropic_request(
                model=model_name,
                system=_memory_prompt(locale),
                messages=[{"role": "user", "content": user_text}],
                max_tokens=300,
                temperature=0.2,
            )
            finished_at = time.perf_counter()
            text = _anthropic_text(payload).strip()
            if text:
                return text
        except Exception:
            continue
    return _memory_fallback(locale)


def _summarize_memory_openai(transcript_text: str, locale: str | None) -> str:
    if not _openai_available():
        return _memory_fallback(locale)

    zh = _is_zh(locale)
    user_text = (
        f"{transcript_text}\n\n"
        + ("只輸出 2-3 句摘要，使用第三人稱「玩家」，保留具體行為與結果。" if zh else 'Output only a 2-3 sentence summary using third person "the player" and keep the concrete actions and outcomes.')
    )
    for model_name in _openai_models():
        try:
            started_at = time.perf_counter()
            payload = _openai_request(
                model=model_name,
                system=_memory_prompt(locale),
                messages=[{"role": "user", "content": user_text}],
                max_tokens=300,
                temperature=_openai_temperature_for_model(model_name, 0.2),
                verbosity=_openai_verbosity_for_model(model_name),
                reasoning_effort=_openai_reasoning_effort_for_model(model_name),
            )
            finished_at = time.perf_counter()
            text = _openai_text(payload).strip()
            if text:
                return text
        except Exception:
            continue
    return _memory_fallback(locale)


def _summarize_memory_gemini(transcript_text: str, locale: str | None) -> str:
    client = _client()
    if client is None:
        return _memory_fallback(locale)

    try:
        started_at = time.perf_counter()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=_memory_prompt(locale),
                max_output_tokens=2048,
            ),
            contents=[{"role": "user", "parts": [{"text": transcript_text}]}],
        )
        finished_at = time.perf_counter()
        return (response.text or "").strip() or _memory_fallback(locale)
    except Exception:
        return _memory_fallback(locale)


def summarize_memory(transcript_text: str, *, locale: str | None = None) -> str:
    fallback_text = _memory_fallback(locale)
    for provider in _provider_priority():
        if provider == "openai":
            text = _summarize_memory_openai(transcript_text, locale)
        elif provider == "anthropic":
            text = _summarize_memory_claude(transcript_text, locale)
        else:
            text = _summarize_memory_gemini(transcript_text, locale)
        if text != fallback_text:
            return text
    return fallback_text


def _generate_perf_artifact_claude(
    *,
    scene_title: str,
    scene_id: str,
    rating: str,
    memory_text: str,
    eval_reason: str,
    transcript_text: str,
    locale: str | None,
) -> dict[str, str]:
    if not _anthropic_available():
        return {}

    if _is_zh(locale):
        user_text = (
            f"【場景】{scene_title}（{scene_id}）\n"
            f"【評分】{rating}\n"
            f"【記憶摘要】{memory_text}\n"
            f"【評分理由】{eval_reason}\n\n"
            f"【完整對話】\n{transcript_text}\n\n"
            "只輸出一個 JSON 物件，包含 title、summary、framing_a、framing_b。"
            "不要有任何前言、後記或 markdown code block。"
        )
    else:
        user_text = (
            f"[Scene] {scene_title} ({scene_id})\n"
            f"[Rating] {rating}\n"
            f"[Memory summary] {memory_text}\n"
            f"[Rating reason] {eval_reason}\n\n"
            f"[Full transcript]\n{transcript_text}\n\n"
            "Output only one JSON object containing title, summary, framing_a, and framing_b. Do not include any preamble, postscript, or markdown code block."
        )
    for model_name in _anthropic_models():
        try:
            started_at = time.perf_counter()
            payload = _anthropic_request(
                model=model_name,
                system=_perf_artifact_prompt(locale),
                messages=[{"role": "user", "content": user_text}],
                max_tokens=1200,
                temperature=0.2,
            )
            finished_at = time.perf_counter()
            parsed_json = _parse_perf_artifact_json(_anthropic_text(payload))
            if parsed_json is None:
                continue
            cleaned = {
                "title": str(parsed_json.get("title", "")).strip(),
                "summary": str(parsed_json.get("summary", "")).strip(),
                "framing_a": str(parsed_json.get("framing_a", "")).strip(),
                "framing_b": str(parsed_json.get("framing_b", "")).strip(),
            }
            if all(cleaned.values()):
                return cleaned
        except Exception:
            continue
    return {}


def _generate_perf_artifact_openai(
    *,
    scene_title: str,
    scene_id: str,
    rating: str,
    memory_text: str,
    eval_reason: str,
    transcript_text: str,
    locale: str | None,
) -> dict[str, str]:
    if not _openai_available():
        return {}

    if _is_zh(locale):
        user_text = (
            f"【場景】{scene_title}（{scene_id}）\n"
            f"【評分】{rating}\n"
            f"【記憶摘要】{memory_text}\n"
            f"【評分理由】{eval_reason}\n\n"
            f"【完整對話】\n{transcript_text}\n\n"
            "只輸出一個 JSON 物件，包含 title、summary、framing_a、framing_b。"
            "不要有任何前言、後記或 markdown code block。"
        )
    else:
        user_text = (
            f"[Scene] {scene_title} ({scene_id})\n"
            f"[Rating] {rating}\n"
            f"[Memory summary] {memory_text}\n"
            f"[Rating reason] {eval_reason}\n\n"
            f"[Full transcript]\n{transcript_text}\n\n"
            "Output only one JSON object containing title, summary, framing_a, and framing_b. Do not include any preamble, postscript, or markdown code block."
        )
    response_format = {
        "type": "json_schema",
        "name": "perf_artifact_result",
        "schema": PERF_ARTIFACT_JSON_SCHEMA,
        "strict": True,
    }
    for model_name in _openai_models():
        try:
            started_at = time.perf_counter()
            payload = _openai_request(
                model=model_name,
                system=_perf_artifact_prompt(locale),
                messages=[{"role": "user", "content": user_text}],
                max_tokens=1200,
                temperature=_openai_temperature_for_model(model_name, 0.2),
                verbosity=_openai_verbosity_for_model(model_name),
                reasoning_effort=_openai_reasoning_effort_for_model(model_name),
                response_format=response_format,
            )
            finished_at = time.perf_counter()
            parsed_json = _parse_perf_artifact_json(_openai_text(payload))
            if parsed_json is None:
                continue
            cleaned = {
                "title": str(parsed_json.get("title", "")).strip(),
                "summary": str(parsed_json.get("summary", "")).strip(),
                "framing_a": str(parsed_json.get("framing_a", "")).strip(),
                "framing_b": str(parsed_json.get("framing_b", "")).strip(),
            }
            if all(cleaned.values()):
                return cleaned
        except Exception:
            continue
    return {}


def _generate_perf_artifact_gemini(
    *,
    scene_title: str,
    scene_id: str,
    rating: str,
    memory_text: str,
    eval_reason: str,
    transcript_text: str,
    locale: str | None,
) -> dict[str, str]:
    client = _client()
    if client is None:
        return {}

    if _is_zh(locale):
        user_text = (
            f"【場景】{scene_title}（{scene_id}）\n"
            f"【評分】{rating}\n"
            f"【記憶摘要】{memory_text}\n"
            f"【評分理由】{eval_reason}\n\n"
            f"【完整對話】\n{transcript_text}"
        )
    else:
        user_text = (
            f"[Scene] {scene_title} ({scene_id})\n"
            f"[Rating] {rating}\n"
            f"[Memory summary] {memory_text}\n"
            f"[Rating reason] {eval_reason}\n\n"
            f"[Full transcript]\n{transcript_text}"
        )
    try:
        started_at = time.perf_counter()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=_perf_artifact_prompt(locale),
                temperature=0.2,
                max_output_tokens=1200,
                response_mime_type="application/json",
                response_schema=PerfArtifactResult,
            ),
            contents=[{"role": "user", "parts": [{"text": user_text}]}],
        )
        finished_at = time.perf_counter()
    except Exception:
        return {}

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, PerfArtifactResult):
        artifact = parsed.model_dump()
    elif isinstance(parsed, dict):
        artifact = parsed
    else:
        parsed_json = _parse_perf_artifact_json(_extract_response_text(response))
        if parsed_json is None:
            return {}
        artifact = parsed_json

    cleaned = {
        "title": str(artifact.get("title", "")).strip(),
        "summary": str(artifact.get("summary", "")).strip(),
        "framing_a": str(artifact.get("framing_a", "")).strip(),
        "framing_b": str(artifact.get("framing_b", "")).strip(),
    }
    if not all(cleaned.values()):
        return {}
    return cleaned


def generate_perf_artifact(
    *,
    scene_title: str,
    scene_id: str,
    rating: str,
    memory_text: str,
    eval_reason: str,
    transcript_text: str,
    locale: str | None = None,
) -> dict[str, str]:
    for provider in _provider_priority():
        if provider == "openai":
            artifact = _generate_perf_artifact_openai(
                scene_title=scene_title,
                scene_id=scene_id,
                rating=rating,
                memory_text=memory_text,
                eval_reason=eval_reason,
                transcript_text=transcript_text,
                locale=locale,
            )
        elif provider == "anthropic":
            artifact = _generate_perf_artifact_claude(
                scene_title=scene_title,
                scene_id=scene_id,
                rating=rating,
                memory_text=memory_text,
                eval_reason=eval_reason,
                transcript_text=transcript_text,
                locale=locale,
            )
        else:
            artifact = _generate_perf_artifact_gemini(
                scene_title=scene_title,
                scene_id=scene_id,
                rating=rating,
                memory_text=memory_text,
                eval_reason=eval_reason,
                transcript_text=transcript_text,
                locale=locale,
            )
        if artifact:
            return artifact
    return {}


def _parse_perf_artifact_json(text: str) -> dict[str, str] | None:
    raw = _strip_code_fence(text)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(raw)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    return {
        "title": str(parsed.get("title", "")).strip(),
        "summary": str(parsed.get("summary", "")).strip(),
        "framing_a": str(parsed.get("framing_a", "")).strip(),
        "framing_b": str(parsed.get("framing_b", "")).strip(),
    }
