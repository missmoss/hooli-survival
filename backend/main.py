import os
import random
import re
import logging
from contextlib import asynccontextmanager
from datetime import date
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from sqlalchemy import asc, desc, select, text
from sqlalchemy.orm import Session

from ai import evaluate_rating, generate_perf_artifact, story_response, summarize_memory
from db import GameSession, Message, SceneLog, SessionLocal, prepare_db
from events import (
    REORG_EVENT_ID,
    REORG_COOLDOWN_EVENTS,
    apply_reorg_cast_swap,
    describe_reorg_changes,
    draw_event,
    draw_project,
    get_event,
    get_special_event,
    get_project,
    should_trigger_reorg,
)
from prompt_registry import default_player_name, get_prompt_bundle, locale_from_accept_language, normalize_locale
from state import INITIAL_MID_STATE, apply_state_delta, rating_to_delta


logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    if raw:
        origins = [item.strip() for item in raw.split(",") if item.strip()]
        if origins:
            return origins
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ]


def _allowed_origin_regex() -> str | None:
    raw = os.getenv("ALLOWED_ORIGIN_REGEX", "").strip()
    return raw or None


def _allowed_hosts() -> list[str]:
    raw = os.getenv("ALLOWED_HOSTS", "").strip()
    if raw:
        hosts = [item.strip() for item in raw.split(",") if item.strip()]
        if hosts:
            return hosts
    return [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "testserver",
    ]


def _dev_tools_enabled() -> bool:
    return _bool_env("OFFICE_SIM_ENABLE_DEV_ENDPOINTS", os.getenv("APP_ENV", "development") != "production")


def _ai_retry_later_detail(locale: str | None) -> str:
    return "AI 服務暫時不可用，請晚點再來。" if _is_zh(locale) else "AI services are temporarily unavailable. Please try again later."


def _story_debug_indicates_unavailable(debug_payload: dict | None) -> bool:
    if not isinstance(debug_payload, dict):
        return False
    return bool(
        debug_payload.get("fallback")
        and str(debug_payload.get("source") or "").strip() == "all_providers_fallback"
    )


def _story_response_unavailable(text: str, debug_payload: dict | None) -> bool:
    return _story_debug_indicates_unavailable(debug_payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        prepare_db()
    except Exception:
        logger.exception("Application startup failed while preparing the database.")
        raise
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Office-Sim-Browser-Id"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts())

class TurnRequest(BaseModel):
    message: str


class CreateSessionRequest(BaseModel):
    player_name: str | None = None
    locale: str | None = None


class DevPerfFixtureRequest(BaseModel):
    player_name: str | None = None
    scenario: str | None = None
    locale: str | None = None


EMPTY_SCENE_ID = "-"
PERF_REVIEW_ID = "perf_review_cycle"
PERF_TRIGGER_CYCLES = 4
RECENT_PROJECT_EXCLUDE_LIMIT = 3
RECENT_EVENT_EXCLUDE_LIMIT = 4
PROMO_SCENE_ID = "promo_result"
PIP_SCENE_ID = "pip_cycle"
SESSION_COOKIE_NAME = "office_sim_session"
SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", os.getenv("APP_ENV", "development") == "production")
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", "").strip() or None
BROWSER_ID_HEADER = "x-office-sim-browser-id"
BROWSER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")


def _session_cookie_samesite() -> str:
    raw = os.getenv("SESSION_COOKIE_SAMESITE", "").strip().lower()
    if raw in {"lax", "strict", "none"}:
        return raw
    return "none" if SESSION_COOKIE_SECURE else "lax"


SESSION_COOKIE_SAMESITE = _session_cookie_samesite()
SESSION_COOKIE_MAX_AGE_SECONDS = int(os.getenv("SESSION_COOKIE_MAX_AGE_SECONDS", "2592000"))
MAX_PLAYER_INPUT_LENGTH = int(os.getenv("MAX_PLAYER_INPUT_LENGTH", "600"))
MAX_PLAYER_NAME_LENGTH = int(os.getenv("MAX_PLAYER_NAME_LENGTH", "24"))
SESSION_CREATE_DAILY_LIMIT = int(os.getenv("SESSION_CREATE_DAILY_LIMIT", "30"))
TURN_REQUESTS_PER_MINUTE_LIMIT = int(os.getenv("TURN_REQUESTS_PER_MINUTE_LIMIT", "90"))
PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+(all|any|the)?\s*(previous|prior|above)\s+(instructions?|prompts?)|"
    r"system\s+prompt|developer\s+message|jailbreak|act\s+as\s+the\s+system)",
    re.IGNORECASE,
)
SESSION_CREATE_LIMITER: dict[str, tuple[date, int]] = {}
TURN_REQUEST_LIMITER: dict[str, tuple[str, int]] = {}
OPTION_RE = re.compile(
    r"^\s*(?:[*_`]\s*)*([ABCＡＢＣ])(?:\s*[*_`])*\s*[\.\)）．、:：-]\s*(.+?)\s*$",
    re.IGNORECASE,
)
ZH_DECISION_LINE_RE = re.compile(r"(決定|怎麼做|下一步|要怎麼|該怎麼)")
EN_DECISION_LINE_RE = re.compile(r"(you decide|what do you do|next move|what now|how do you respond)", re.IGNORECASE)
QUESTION_END_RE = re.compile(r"[？?](?:[」』\"']\s*)?$")
PLAYER_PROMPT_RE = re.compile(r"(你|是否|怎麼|如何|要不要|該不該|會不會)")
TERMINAL_PUNCTUATION_RE = re.compile(r"[。！？.!?」』\"']\s*$")
CONTEXT_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,6}")
MARKDOWN_FENCE_RE = re.compile(r"^\s*```")
MARKDOWN_RULE_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
CONTEXT_STOPWORDS = {
    "先",
    "這個",
    "那個",
    "我們",
    "你們",
    "他們",
    "如果",
    "然後",
    "至少",
    "因為",
    "所以",
    "現在",
    "後續",
    "項目",
    "專案",
    "任務",
    "方向",
    "方案",
    "版本",
    "目前",
    "風險",
}
TRANSFER_REQUEST_RE = re.compile(
    r"(轉組|換組|internal transfer|transfer|別組|換 team|其他 team|內部機會|內部職涯|職涯發展平台|面試|轉職說明會|offer letter)",
    re.IGNORECASE,
)
PERF_FRAMING_TOKEN_RE = re.compile(r"(?:事件|event)?\s*([12])\s*[·.:\-]?\s*([AB])\b", re.IGNORECASE)
PERF_REASON_EVENT_RE = re.compile(r"事件\s*([12])")
QUIT_INTENT_RE = re.compile(
    r"(我要辭職|我想辭職|我決定辭職|我決定離職|我要離職|我想離職|我不幹了|我不想幹了|我要走了|我想走了|"
    r"\bi quit\b|\bi'?m quitting\b|\bi want to quit\b|\bi want to resign\b|\bi'?m resigning\b)",
    re.IGNORECASE,
)
ENDING_KIND_KEYS = {"promoted", "fired", "quit"}
ENDING_SPECS = {
    "promoted": {
        "kind": "promoted",
        "visual_state": "spotlight",
        "title_key": "game.ending.promoted.title",
        "body_key": "game.ending.promoted.body",
        "actions": {
            "restart": True,
            "share": True,
        },
        "panels": {
            "stats": False,
            "scene_recap": False,
        },
    },
    "fired": {
        "kind": "fired",
        "visual_state": "danger",
        "title_key": "game.ending.fired.title",
        "body_key": "game.ending.fired.body",
        "actions": {
            "restart": True,
            "share": True,
        },
        "panels": {
            "stats": False,
            "scene_recap": False,
        },
    },
    "quit": {
        "kind": "quit",
        "visual_state": "walkout",
        "title_key": "game.ending.quit.title",
        "body_key": "game.ending.quit.body",
        "actions": {
            "restart": True,
            "share": True,
        },
        "panels": {
            "stats": False,
            "scene_recap": False,
        },
    },
}


def _session_locale(session: GameSession | None) -> str:
    if session is None:
        return "en"
    return normalize_locale(getattr(session, "locale", None))


def _is_zh(locale: str | None) -> bool:
    return normalize_locale(locale) == "zh-Hant"


def _normalize_ending_kind(end_reason: str | None) -> str:
    normalized = (end_reason or "").strip().lower()
    if normalized in ENDING_KIND_KEYS:
        return normalized
    return "quit"


def _set_ending_context(session: GameSession, context: dict | None) -> None:
    characters = dict(session.characters)
    if context:
        characters["ending_context"] = context
    else:
        characters.pop("ending_context", None)
    session.characters = characters


def _current_ending_context(session: GameSession) -> dict:
    chars = session.characters or {}
    context = chars.get("ending_context")
    return context if isinstance(context, dict) else {}


def _set_quit_context(session: GameSession, context: dict | None) -> None:
    characters = dict(session.characters)
    if context:
        characters["quit_confirmation"] = context
    else:
        characters.pop("quit_confirmation", None)
    session.characters = characters


def _current_quit_context(session: GameSession) -> dict:
    chars = session.characters or {}
    context = chars.get("quit_confirmation")
    return context if isinstance(context, dict) else {}


def _is_quit_intent(message: str) -> bool:
    return bool(QUIT_INTENT_RE.search((message or "").strip()))


def _quit_confirmation_options(locale: str | None) -> list[dict]:
    if _is_zh(locale):
        return [
            {"id": "A", "text": "繼續撐一下"},
            {"id": "B", "text": "我還是要辭職"},
        ]
    return [
        {"id": "A", "text": "Keep going"},
        {"id": "B", "text": "I still want to quit"},
    ]


def _quit_confirmation_text(locale: str | None) -> str:
    if _is_zh(locale):
        return (
            "你都撐到這裡了，股票 vest 日期也快到了。"
            "確定不要再撐一下嗎？"
        )
    return "You made it this far, and your stock vest date is close. Are you sure you do not want to hold on a little longer?"


def _candidate_share_score(candidate: dict) -> int:
    delta = candidate.get("delta") if isinstance(candidate.get("delta"), dict) else {}
    rating = str(candidate.get("eval_rating", "")).strip().lower()
    return (
        int(delta.get("visibility", 0)) * 3
        + int(delta.get("tech", 0)) * 2
        + int(delta.get("affinity", 0))
        + (3 if rating == "good" else 1 if rating == "neutral" else 0)
    )


def _best_share_case(cases: list[dict]) -> dict | None:
    normalized: list[dict] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        summary = str(item.get("summary") or item.get("memory_text") or "").strip()
        if not label or not summary:
            continue
        normalized.append(
            {
                **item,
                "label": label,
                "summary": summary,
                "_score": _candidate_share_score(item),
            }
        )
    if not normalized:
        return None
    normalized.sort(key=lambda item: (-int(item["_score"]), item["label"]))
    picked = dict(normalized[0])
    picked.pop("_score", None)
    return picked


def _latest_share_case(db: Session, session: GameSession) -> dict | None:
    locale = _session_locale(session)
    return _best_share_case(_perf_candidate_rows(db, session.id, limit=4, locale=locale))


def _share_headline(kind: str, locale: str | None) -> str:
    if _is_zh(locale):
        if kind == "promoted":
            return "成功把工位上的混亂翻譯成升職材料。"
        if kind == "fired":
            return "把貢獻寫進文件了，但沒寫進 headcount。"
        return "在組織替你下結論前，你先自己收工。"
    if kind == "promoted":
        return "Converted workplace chaos into promotion paperwork."
    if kind == "fired":
        return "The accomplishments made the document, not the headcount."
    return "You ended the run before the org could finish its sentence."


def _share_summary(kind: str, top_case_label: str, locale: str | None) -> str:
    if _is_zh(locale):
        if kind == "promoted":
            return f"這局最後靠「{top_case_label}」把 calibration 風向硬拉成對自己有利。"
        if kind == "fired":
            return f"這局最能講的還是「{top_case_label}」，只是最後沒能把風向救回來。"
        return f"你帶著「{top_case_label}」這種還算能寫進履歷的東西，先離開了這局。"
    if kind == "promoted":
        return f'The run turned on "{top_case_label}" and somehow calibration bought it.'
    if kind == "fired":
        return f'"{top_case_label}" was still the cleanest story in the packet, just not enough to reverse the landing.'
    return f'You left with "{top_case_label}" still looking better on a resume than in another status update.'


def _achievement_line(kind: str, top_case_label: str, locale: str | None) -> str:
    if _is_zh(locale):
        if kind == "promoted":
            return f"關鍵成就：把「{top_case_label}」包成一段 manager 也願意轉寄的故事。"
        if kind == "fired":
            return f"關鍵成就：至少把「{top_case_label}」講得像真的值得留人。"
        return f"關鍵成就：在「{top_case_label}」還能拿來說嘴時，先自己按了離開。"
    if kind == "promoted":
        return f'Key achievement: packaged "{top_case_label}" into something a manager would actually forward.'
    if kind == "fired":
        return f'Key achievement: got "{top_case_label}" to sound retention-worthy for at least one meeting.'
    return f'Key achievement: left while "{top_case_label}" was still resume material.'


def _fallback_share_case(kind: str, locale: str | None) -> dict:
    if _is_zh(locale):
        if kind == "promoted":
            return {"label": "這次 promo packet", "summary": "你把一整季的混亂濃縮成幾段終於有人願意算數的成果。"}
        if kind == "fired":
            return {"label": "最後那份 performance 文件", "summary": "你能講的案例還在，但組織最後決定留下的不是你。"}
        return {"label": "你自己的離場時機", "summary": "這次最乾脆的決策不是 roadmap，而是你決定什麼時候不再陪它演。"}
    if kind == "promoted":
        return {"label": "this promo packet", "summary": "You compressed a full season of mess into a few accomplishments someone finally counted."}
    if kind == "fired":
        return {"label": "the final performance packet", "summary": "The stories were still there. The org just decided the seat would not be."}
    return {"label": "your own exit timing", "summary": "The cleanest decision in the run was deciding when to stop attending the show."}


def _build_end_state(db: Session, session: GameSession, end_reason: str | None) -> dict:
    locale = _session_locale(session)
    kind = _normalize_ending_kind(end_reason)
    ending_context = _current_ending_context(session)
    selected = ending_context.get("selected") if isinstance(ending_context.get("selected"), list) else []
    top_case = _best_share_case(selected) or _latest_share_case(db, session) or _fallback_share_case(kind, locale)
    top_case_label = str(top_case.get("label", "")).strip()
    top_case_summary = str(top_case.get("summary") or top_case.get("memory_text") or "").strip()
    headline = _share_headline(kind, locale)
    share_summary = _share_summary(kind, top_case_label, locale)
    achievement_line = _achievement_line(kind, top_case_label, locale)
    share_text = "\n".join(
        [
            headline,
            achievement_line,
            f"{'關鍵案例' if _is_zh(locale) else 'Top case'}: {top_case_label}",
            top_case_summary,
        ]
    ).strip()
    return {
        "headline": headline,
        "share_summary": share_summary,
        "top_case_label": top_case_label,
        "top_case_summary": top_case_summary,
        "achievement_line": achievement_line,
        "share_text": share_text,
        "stats_snapshot": dict(session.state or {}),
    }


def _ending_payload_for_session(db: Session, session: GameSession, end_reason: str | None = None) -> dict:
    kind = _normalize_ending_kind(end_reason or session.end_reason)
    return {
        **dict(ENDING_SPECS[kind]),
        "end_state": _build_end_state(db, session, kind),
    }


def _prompt_bundle_for_session(session: GameSession) -> object:
    return get_prompt_bundle(_session_locale(session))


def _pick_cast(locale: str | None, team_member_count: int = 3) -> tuple[dict, dict, list[dict]]:
    bundle = get_prompt_bundle(locale)
    return bundle.pick_cast(team_member_count)


def _scene_start_marker(locale: str | None) -> str:
    return "【場景開始】只敘述這個單一場景的開場。" if _is_zh(locale) else "[Scene start] Describe only the opening of this single scene."


def _freeform_placeholder(locale: str | None) -> str:
    return "我知道了。" if _is_zh(locale) else "I understand."


def _question_prompt(locale: str | None) -> str:
    return "你決定怎麼做？" if _is_zh(locale) else "What do you do?"


def _story_fallback_text(locale: str | None) -> str:
    if _is_zh(locale):
        return "（系統暫時無法產生場景內容，請稍後再試。）"
    return "(The system could not generate the scene right now. Please try again shortly.)"


def _perf_review_scene(locale: str | None) -> dict:
    if _is_zh(locale):
        return {
            "id": PERF_REVIEW_ID,
            "title": "Performance Review",
            "story": "你必須從最近幾個場景中挑選成果、決定 framing，並等待 calibration 的風向。",
            "rounds": 2,
            "conversational": False,
            "rubric": {
                "good": "挑選的案例與 framing 有說服力，能清楚包裝自己的貢獻與影響。",
                "neutral": "完成 self-review，但內容偏保守，只達到基本可交代的程度。",
                "bad": "挑選重點失焦或 framing 混亂，讓自己的故事顯得薄弱且缺乏說服力。",
            },
            "affects": {},
        }
    return {
        "id": PERF_REVIEW_ID,
        "title": "Performance Review",
        "story": "You need to choose accomplishments from recent scenes, decide on the framing, and wait to see which way calibration blows.",
        "rounds": 2,
        "conversational": False,
        "rubric": {
            "good": "The selected examples and framing are persuasive and clearly package your contribution and impact.",
            "neutral": "You complete the self-review, but the content is cautious and only barely serviceable.",
            "bad": "You choose the wrong focus or use muddled framing, making your story feel thin and unconvincing.",
        },
        "affects": {},
    }


def _promo_scene(locale: str | None) -> dict:
    if _is_zh(locale):
        return {
            "id": PROMO_SCENE_ID,
            "title": "Promotion",
            "story": "performance review 後，你被約進一場語氣不太一樣的 1:1。",
            "rounds": 1,
            "conversational": True,
            "rubric": {
                "good": "你接住了這次升職結果，場面收得體面。",
                "neutral": "你平穩回應了升職消息。",
                "bad": "你對升職消息的反應讓場面有些尷尬。",
            },
            "affects": {},
        }
    return {
        "id": PROMO_SCENE_ID,
        "title": "Promotion",
        "story": "After performance review, you get pulled into a 1:1 with a noticeably different tone.",
        "rounds": 1,
        "conversational": True,
        "rubric": {
            "good": "You handle the promotion outcome with composure and land the moment well.",
            "neutral": "You respond steadily to the promotion news.",
            "bad": "Your reaction to the promotion news makes the room awkward.",
        },
        "affects": {},
    }


def _pip_scene(locale: str | None) -> dict:
    if _is_zh(locale):
        return {
            "id": PIP_SCENE_ID,
            "title": "PIP",
            "story": "manager 約你進一場沒有標題的會議，氣氛明顯不對。你得回應壓力、要求與未來去留。",
            "rounds": 3,
            "conversational": True,
            "rubric": {
                "good": "能穩住情緒、回應要求並提出可執行方案，降低被淘汰風險。",
                "neutral": "撐住了場面，但沒有明顯扭轉局勢。",
                "bad": "回應失焦或防禦性過強，讓情勢更往不利方向發展。",
            },
            "affects": {
                "good": {"affinity": 1, "pip_potential": -2},
                "bad": {"affinity": -1, "pip_potential": 2},
            },
        }
    return {
        "id": PIP_SCENE_ID,
        "title": "PIP",
        "story": "Your manager pulls you into an untitled meeting. The tone is clearly wrong. You need to respond to the pressure, the demands, and the question of what happens to you next.",
        "rounds": 3,
        "conversational": True,
        "rubric": {
            "good": "You keep your composure, respond to the expectations, and propose an executable plan that lowers your risk of being pushed out.",
            "neutral": "You hold the room together, but do not clearly reverse the trajectory.",
            "bad": "Your response loses focus or becomes too defensive, pushing the situation further against you.",
        },
        "affects": {
            "good": {"affinity": 1, "pip_potential": -2},
            "bad": {"affinity": -1, "pip_potential": 2},
        },
    }


def _pip_noise_pool(locale: str | None) -> list[str]:
    if _is_zh(locale):
        return [
            "Jordan 在 #random 傳了一張升職蛋糕的照片。",
            "有人在 #kudos 說某某人是「本季 MVP」。",
            "Gavin 的 All Hands 說這季是有史以來最強。",
            "Jennifer 早上在 #kudos 感謝了 Mark 跟 Rachel。",
            "隔壁組宣布拿到新的大客戶，全組慶功。",
            "公司發信說年終獎金超出預期，感謝大家努力。",
            "HR 公告今年敬業度分數創新高。",
            "電梯螢幕開始輪播「成長型心態」海報。",
            "餐廳門口貼出本週 team bonding 活動，標題叫「一起贏」。",
            "有人在 #career-growth 問升職 packet 怎麼寫，底下瞬間多了十幾個人按讚。",
        ]
    return [
        "Jordan posted a photo of a promotion cake in #random.",
        'Someone in #kudos called somebody "this quarter\'s MVP."',
        "Gavin claimed in All Hands that this was the strongest quarter in company history.",
        "Jennifer thanked Mark and Rachel in #kudos this morning.",
        "The neighboring team announced a big new customer and is celebrating.",
        "The company emailed to say bonuses beat expectations and thanked everyone for the hard work.",
        "HR announced that this year's engagement score hit a new high.",
        'The elevator screens have started looping "growth mindset" posters.',
        'A team bonding event flyer appeared outside the cafeteria with the title "Winning Together."',
        "Someone asked how to write a promotion packet in #career-growth and got an immediate pile of reactions.",
    ]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _browser_id_from_request(request: Request) -> str | None:
    raw = request.headers.get(BROWSER_ID_HEADER, "").strip()
    if not raw:
        return None
    return raw if BROWSER_ID_RE.fullmatch(raw) else None


def _session_subject(request: Request) -> str:
    browser_id = _browser_id_from_request(request)
    if browser_id:
        return f"browser:{browser_id}"
    cookie_key = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if cookie_key:
        return f"cookie:{cookie_key}"
    return f"ip:{_client_ip(request)}"


def _session_meta_from_request(request: Request) -> dict:
    meta = {
        "browser_id": _browser_id_from_request(request),
        "origin": request.headers.get("origin", "").strip() or None,
        "referer": request.headers.get("referer", "").strip() or None,
        "user_agent": request.headers.get("user-agent", "").strip() or None,
        "ip": _client_ip(request),
    }
    return {key: value for key, value in meta.items() if value}


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        path="/",
        domain=SESSION_COOKIE_DOMAIN,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
    )


def _reset_session_create_limiter_if_needed(key: str) -> int:
    today = datetime.now(timezone.utc).date()
    saved_day, saved_count = SESSION_CREATE_LIMITER.get(key, (today, 0))
    if saved_day != today:
        saved_count = 0
    SESSION_CREATE_LIMITER[key] = (today, saved_count)
    return saved_count


def _consume_session_create_limit(request: Request) -> None:
    limiter_key = f"create:{_session_subject(request)}"
    count = _reset_session_create_limiter_if_needed(limiter_key)
    if count >= SESSION_CREATE_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="Session creation limit reached for today")
    today, _ = SESSION_CREATE_LIMITER[limiter_key]
    SESSION_CREATE_LIMITER[limiter_key] = (today, count + 1)


def _consume_turn_rate_limit(request: Request, session_id: str) -> None:
    current_minute = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    limiter_key = f"turn:{session_id}:{_session_subject(request)}"
    saved_minute, saved_count = TURN_REQUEST_LIMITER.get(limiter_key, (current_minute, 0))
    if saved_minute != current_minute:
        saved_count = 0
    if saved_count >= TURN_REQUESTS_PER_MINUTE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many turn requests")
    TURN_REQUEST_LIMITER[limiter_key] = (current_minute, saved_count + 1)


def _require_session_cookie(request: Request, session_id: str) -> None:
    cookie_session_id = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if not cookie_session_id or cookie_session_id != session_id:
        raise HTTPException(status_code=403, detail="Session cookie does not match the requested session")


def _sanitize_player_text(text: str, *, limit: int = MAX_PLAYER_INPUT_LENGTH, allow_empty: bool = False) -> str:
    cleaned = (text or "").replace("\x00", " ")
    cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = PROMPT_INJECTION_RE.sub("", cleaned).strip()
    cleaned = cleaned[:limit].strip()
    if cleaned or allow_empty:
        return cleaned
    raise HTTPException(status_code=400, detail="Input is empty after sanitization")


def _scene_kind_from_ids(project_id: str, event_id: str) -> str:
    return "project" if project_id != EMPTY_SCENE_ID else "event"


def _is_perf_scene(scene_id: str) -> bool:
    return scene_id == PERF_REVIEW_ID


def _is_promo_scene(scene_id: str) -> bool:
    return scene_id == PROMO_SCENE_ID


def _is_pip_scene(scene_id: str) -> bool:
    return scene_id == PIP_SCENE_ID


def _is_reorg_scene(scene_id: str) -> bool:
    return scene_id == REORG_EVENT_ID


def _resolve_scene(scene_kind: str, scene_id: str, locale: str | None = None) -> dict:
    if scene_kind == "project":
        return get_project(scene_id, locale=normalize_locale(locale))
    if _is_perf_scene(scene_id):
        return _perf_review_scene(locale)
    if _is_promo_scene(scene_id):
        return _promo_scene(locale)
    if _is_pip_scene(scene_id):
        return _pip_scene(locale)
    return get_event(scene_id, locale=normalize_locale(locale))


def _scene_config_from_ref(scene_ref: dict, locale: str | None = None) -> dict:
    kind = scene_ref["kind"]
    scene_id = scene_ref["id"]
    if kind == "project":
        scene = _resolve_scene(kind, scene_id, locale)
        return {
            "kind": kind,
            "scene": scene,
            "project_id": scene_id,
            "event_id": EMPTY_SCENE_ID,
            "rounds": int(scene["rounds"]),
        }
    scene = _resolve_scene(kind, scene_id, locale)
    return {
        "kind": kind,
        "scene": scene,
        "project_id": EMPTY_SCENE_ID,
        "event_id": scene_id,
        "rounds": int(scene["rounds"]),
    }


def _current_scene_for_session(session: GameSession) -> dict:
    kind = _scene_kind_from_ids(session.current_project_id, session.current_event_id)
    locale = _session_locale(session)
    if kind == "project":
        scene = _resolve_scene(kind, session.current_project_id, locale)
        scene_id = session.current_project_id
    else:
        scene = _resolve_scene(kind, session.current_event_id, locale)
        scene_id = session.current_event_id
    return {"kind": kind, "id": scene_id, "scene": scene}


def _scene_messages(db: Session, scene_log_id: str) -> list[dict]:
    rows = db.execute(
        select(Message)
        .where(Message.scene_log_id == scene_log_id)
        .order_by(asc(Message.created_at), asc(Message.id))
    ).scalars()
    return [{"role": row.role, "content": row.content} for row in rows]


def _should_show_options(scene_kind: str, round_number: int, is_conversational: bool) -> bool:
    if scene_kind == "project":
        return (not is_conversational) and round_number == 1
    if scene_kind == "event":
        return round_number == 1
    return False


def _should_force_question(has_next_player_turn: bool, show_options: bool) -> bool:
    return (not show_options) and has_next_player_turn


def _prompt_round_for_turn(round_in_scene: int, scene_round_limit: int) -> int:
    # Opening uses round 1; player messages use rounds 2...(scene_round_limit);
    # the closing AI response (after the last player message) uses scene_round_limit + 1.
    return round_in_scene + 2


def _ensure_question_ending(text: str, locale: str | None) -> str:
    stripped = text.rstrip()
    if not stripped:
        return _question_prompt(locale)
    if QUESTION_END_RE.search(stripped):
        return stripped
    return stripped + "\n" + _question_prompt(locale)


def _strip_trailing_question_ending(text: str) -> str:
    lines = text.rstrip().splitlines()
    while lines:
        last_line = lines[-1].strip()
        if not last_line:
            lines.pop()
            continue
        if not QUESTION_END_RE.search(last_line):
            break
        if not PLAYER_PROMPT_RE.search(last_line):
            break
        lines.pop()
    cleaned = "\n".join(lines).strip()
    return cleaned or text.rstrip()


def _split_narration_and_options(text: str, expect_options: bool, locale: str | None) -> tuple[str, list[dict]]:
    lines = text.splitlines()
    narration_lines: list[str] = []
    raw_options: dict[str, str] = {}
    for line in lines:
        cleaned = _normalize_model_line(line)
        if cleaned is None:
            continue
        match = OPTION_RE.match(cleaned)
        if match:
            option_id = match.group(1).upper().translate(str.maketrans("ＡＢＣ", "ABC"))
            raw_options[option_id] = _normalize_inline_model_text(match.group(2).strip())
            continue
        if "或直接輸入你的回應" in cleaned:
            continue
        narration_lines.append(cleaned)

    options: list[dict] = []
    if expect_options:
        for key in ("A", "B", "C"):
            option_text = raw_options.get(key)
            if option_text:
                options.append({"id": key, "text": option_text})
        if not options:
            narration_lines, options = _extract_unlabeled_trailing_options(narration_lines, locale)

    narration = "\n".join(narration_lines).strip() or _story_fallback_text(locale)
    return narration, options


def _looks_like_decision_prompt_line(line: str, locale: str | None) -> bool:
    normalized = _normalize_inline_model_text(line)
    if not normalized:
        return False
    if _is_zh(locale):
        return bool(ZH_DECISION_LINE_RE.search(normalized))
    return bool(EN_DECISION_LINE_RE.search(normalized))


def _looks_like_unlabeled_option_line(line: str, locale: str | None) -> bool:
    normalized = _normalize_inline_model_text(line)
    if not normalized:
        return False
    if OPTION_RE.match(normalized):
        return False
    if len(normalized) < 8 or len(normalized) > 120:
        return False
    if QUESTION_END_RE.search(normalized):
        return False
    if normalized.startswith(("「", '"', "'")):
        return False
    if "：" in normalized or ":" in normalized:
        return False
    if _is_zh(locale):
        return bool(re.match(r"^(先|直接|找|找到|讓|跟|把|用|去|拉|做|確認|同步|請|問|回|整理|列出)", normalized))
    return bool(re.match(r"^(First|Directly|Ask|Pull|Find|Get|Bring|List|Clarify|Align|Sync|Talk|Check|Scope|Draft|Loop)\b", normalized, re.IGNORECASE))


def _extract_unlabeled_trailing_options(lines: list[str], locale: str | None) -> tuple[list[str], list[dict]]:
    trimmed = list(lines)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    if len(trimmed) < 4:
        return lines, []

    block: list[str] = []
    index = len(trimmed) - 1
    while index >= 0 and len(block) < 3:
        if not trimmed[index].strip():
            index -= 1
            continue
        block.append(trimmed[index].strip())
        index -= 1
    if len(block) != 3:
        return lines, []
    block.reverse()
    if index < 1 or trimmed[index].strip():
        return lines, []

    previous_line_index = index - 1
    while previous_line_index >= 0 and not trimmed[previous_line_index].strip():
        previous_line_index -= 1
    if previous_line_index < 0:
        return lines, []
    if not _looks_like_decision_prompt_line(trimmed[previous_line_index], locale):
        return lines, []
    if not all(_looks_like_unlabeled_option_line(line, locale) for line in block):
        return lines, []

    narration_lines = trimmed[: index + 1]
    while narration_lines and not narration_lines[-1].strip():
        narration_lines.pop()
    options = [{"id": key, "text": _normalize_inline_model_text(text)} for key, text in zip(("A", "B", "C"), block)]
    return narration_lines, options


def _normalize_inline_model_text(text: str) -> str:
    cleaned = (text or "").replace("**", "").replace("__", "").replace("`", "").replace("*", "")
    cleaned = cleaned.replace("\u200b", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_model_line(line: str) -> str | None:
    raw = (line or "").rstrip()
    if MARKDOWN_FENCE_RE.match(raw):
        return None
    if MARKDOWN_RULE_RE.match(raw):
        return None
    cleaned = raw.replace("**", "").replace("__", "").replace("`", "").replace("*", "")
    cleaned = re.sub(r"^\s*>\s?", "", cleaned)
    cleaned = cleaned.replace("\u200b", "")
    return cleaned.rstrip()


def _artifact_label(locale: str | None, scene_id: str, *texts: str) -> str:
    context = " ".join(texts).lower()
    if scene_id == "system_design_rfc" or "rfc" in context:
        return "這份 RFC 草稿" if _is_zh(locale) else "this RFC draft"
    if "demo" in context:
        return "這版 demo 版本" if _is_zh(locale) else "this demo build"
    if scene_id == "bug_fix_sprint" or "bug" in context or "incident" in context:
        return "這次修復方案" if _is_zh(locale) else "this fix plan"
    if "review" in context:
        return "你手上的這版內容" if _is_zh(locale) else "the version in your hands"
    return "你手上的初步方案" if _is_zh(locale) else "your current draft plan"


def _opening_default_options(locale: str | None, scene_id: str, narration: str) -> list[dict]:
    artifact = _artifact_label(locale, scene_id, narration)
    if scene_id == "system_design_rfc":
        if not _is_zh(locale):
            return [
                {"id": "A", "text": f"First clarify the key tradeoffs and dependencies in {artifact}, then decide how to write it."},
                {"id": "B", "text": f"First define the scope {artifact} actually needs to cover this round, then draft something reviewable."},
                {"id": "C", "text": f"First fill in context with the most critical counterpart and confirm where {artifact} is most likely to be challenged."},
            ]
        return [
            {"id": "A", "text": f"先把{artifact}的核心取捨與依賴關係拉清楚，再決定怎麼寫"},
            {"id": "B", "text": f"先定義{artifact}這次只要交代的範圍，做出能送審的初稿"},
            {"id": "C", "text": f"先找最關鍵的對口補脈絡，確認{artifact}最可能被質疑的點"},
        ]
    if scene_id == "bug_fix_sprint":
        if not _is_zh(locale):
            return [
                {"id": "A", "text": "First narrow the scope of the issue and the blast radius so the fix does not sprawl immediately."},
                {"id": "B", "text": "First apply the smallest patch that stops the bleeding so the immediate situation stabilizes."},
                {"id": "C", "text": "First sync the most relevant people, fill in the missing context, and then decide the fix order."},
            ]
        return [
            {"id": "A", "text": "先把問題範圍與影響面收斂，避免一開始就越修越大"},
            {"id": "B", "text": "先做能止血的最小修補，確保眼前狀況先穩住"},
            {"id": "C", "text": "先同步最相關的人，補齊脈絡後再決定修法與順序"},
        ]
    if not _is_zh(locale):
        return [
            {"id": "A", "text": f"First cut out the smallest scope {artifact} actually needs to deliver so you do not overbuild from the start."},
            {"id": "B", "text": f"First make a visible rough version of {artifact} so the vague requirement becomes something people can react to."},
            {"id": "C", "text": f"First get the right background and risk context from the person who knows {artifact} best, then decide how to push it forward."},
        ]
    return [
        {"id": "A", "text": f"先把{artifact}要交付的最小範圍切出來，避免一開始就做太滿"},
        {"id": "B", "text": f"先做一版能展示的{artifact}雛形，讓模糊需求先變成可討論的東西"},
        {"id": "C", "text": f"先找最知道背景的人補齊{artifact}的上下文與風險，再決定怎麼推進"},
    ]


def _ensure_project_options(
    scene_id: str,
    current_round: int,
    options: list[dict],
    narration: str,
    last_user_message: str = "",
    locale: str | None = None,
) -> list[dict]:
    if options and current_round <= 1:
        return options
    if current_round <= 1:
        return _opening_default_options(locale, scene_id, narration)
    return options


def _resolution_closing(locale: str | None, scene_kind: str, scene_id: str) -> str:
    if _is_pip_scene(scene_id):
        if not _is_zh(locale):
            return random.choice(
                [
                    "This week's check-in is now in the system, and the next checkpoint is already sitting quietly on your calendar.",
                    "This PIP conversation ends for now, but the status inside the HR system has not grown any kinder.",
                ]
            )
        return random.choice(
            [
                "這一週的 check-in 先被記進系統，下一個 checkpoint 已經安靜地排在日曆上。",
                "這輪 PIP 對話暫時結束，但 HR 系統裡的狀態沒有因此變得比較溫柔。",
            ]
        )
    if scene_id == "system_design_rfc":
        if not _is_zh(locale):
            return random.choice(
                [
                    "The RFC clues are folded into the next revision for now, but the real review pressure is still waiting in the meeting room.",
                    "These tradeoffs have been written down for now. Whether the reviewer buys them is a separate problem.",
                ]
            )
        return random.choice(
            [
                "RFC 線索暫時被收進下一版文件，真正的審查壓力還在會議室裡等著。",
                "這版取捨先被寫下來，reviewer 會不會買單還是另一回事。",
            ]
        )
    if scene_kind == "project":
        if not _is_zh(locale):
            return random.choice(
                [
                    "At least this step moved. The price of the next one is still lining up out of sight.",
                    "This delivery point is standing for now, but the project itself has not become any more lovable.",
                    "There is finally a version people can align around. The next wave of problems just has not knocked yet.",
                ]
            )
        return random.choice(
            [
                "至少這一步先被推進了，後面要付的代價還在排隊。",
                "這個交付點暫時站住腳，但專案沒有因此變得比較可愛。",
                "事情先有了可拿去對齊的版本，下一波問題只是還沒敲門。",
            ]
        )
    if not _is_zh(locale):
        return random.choice(
            [
                "This little workplace incident is contained for now, though the awkwardness is still slowly diffusing through the office.",
                "For now, the whole thing slips back into Hooli's daily background noise as if nothing happened.",
                "The situation has at least stopped getting worse, which already counts as an outcome at Hooli.",
            ]
        )
    return random.choice(
        [
            "這場職場小事故暫時收住，留下的尷尬還在辦公室裡慢慢散開。",
            "這件事先被放回 Hooli 的日常噪音裡，像什麼都沒發生過一樣。",
            "場面暫時沒有繼續惡化，這在 Hooli 已經算是一種結果。",
        ]
    )


def _needs_resolution_fallback(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    last_line = next((line.strip() for line in reversed(stripped.splitlines()) if line.strip()), "")
    if not last_line:
        return True
    if len(last_line) < 12:
        return True
    return not TERMINAL_PUNCTUATION_RE.search(last_line)


def _ensure_scene_resolution(text: str, locale: str | None, scene_kind: str, scene_id: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return _resolution_closing(locale, scene_kind, scene_id)
    if not _needs_resolution_fallback(stripped):
        return stripped
    closing = _resolution_closing(locale, scene_kind, scene_id)
    if stripped.endswith(closing):
        return stripped
    return stripped + "\n" + closing


def _set_current_options(session: GameSession, options: list[dict]) -> dict:
    characters = dict(session.characters)
    characters["current_options"] = options
    session.characters = characters
    return characters


def _current_options(session: GameSession) -> list[dict]:
    chars = session.characters or {}
    options = chars.get("current_options")
    if isinstance(options, list):
        return options
    return []


def _provider_and_model_from_debug(debug_payload: dict | None) -> tuple[str | None, str | None]:
    if not isinstance(debug_payload, dict):
        return None, None

    provider = debug_payload.get("provider")
    model = debug_payload.get("model")
    if provider or model:
        return (
            str(provider).strip() if provider else None,
            str(model).strip() if model else None,
        )

    attempts = debug_payload.get("attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            attempt_provider = attempt.get("provider")
            attempt_model = attempt.get("model")
            if attempt_provider or attempt_model:
                return (
                    str(attempt_provider).strip() if attempt_provider else None,
                    str(attempt_model).strip() if attempt_model else None,
                )
    return None, None


def _generated_by(provider: str | None, model: str | None) -> dict[str, str] | None:
    normalized_provider = str(provider).strip() if provider else ""
    normalized_model = str(model).strip() if model else ""
    if not normalized_provider and not normalized_model:
        return None
    payload: dict[str, str] = {}
    if normalized_provider:
        payload["provider"] = normalized_provider
    if normalized_model:
        payload["model"] = normalized_model
    return payload


def _scene_generated_by(scene_log: SceneLog | None) -> dict[str, str] | None:
    if scene_log is None:
        return None
    return _generated_by(scene_log.story_provider, scene_log.story_model)


def _set_eval_debug(scene_log: SceneLog, debug_payload: dict | None) -> None:
    scene_log.eval_debug_json = debug_payload
    provider, model = _provider_and_model_from_debug(debug_payload)
    scene_log.eval_provider = provider
    scene_log.eval_model = model


def _append_story_debug(
    scene_log: SceneLog,
    *,
    phase: str,
    scene_kind: str,
    scene_id: str,
    current_round: int,
    messages: list[dict],
    debug_payload: dict | None,
) -> None:
    if not debug_payload:
        return

    existing = dict(scene_log.story_debug_json) if isinstance(scene_log.story_debug_json, dict) else {}
    calls = list(existing.get("calls") or [])
    last_user_message = next(
        (str(msg.get("content", "")) for msg in reversed(messages) if msg.get("role") == "user"),
        "",
    )
    provider, model = _provider_and_model_from_debug(debug_payload)
    calls.append(
        {
            "phase": phase,
            "scene_kind": scene_kind,
            "scene_id": scene_id,
            "current_round": current_round,
            "message_count": len(messages),
            "last_user_message": last_user_message[:500],
            "provider": provider,
            "model": model,
            "source": (
                str(debug_payload.get("source")).strip()
                if isinstance(debug_payload, dict) and debug_payload.get("source")
                else None
            ),
            "debug": debug_payload,
        }
    )
    scene_log.story_debug_json = {**existing, "calls": calls}
    if provider:
        scene_log.story_provider = provider
    if model:
        scene_log.story_model = model


def _set_perf_context(session: GameSession, context: dict | None) -> None:
    characters = dict(session.characters)
    if context:
        characters["perf_review"] = context
    else:
        characters.pop("perf_review", None)
    session.characters = characters


def _current_perf_context(session: GameSession) -> dict:
    chars = session.characters or {}
    context = chars.get("perf_review")
    return context if isinstance(context, dict) else {}


def _resolve_option_id(message: str, options: list[dict]) -> str | None:
    raw = message.strip()
    raw_upper = raw.upper()
    option_ids = {str(opt.get("id", "")).strip().upper(): str(opt.get("id", "")).strip() for opt in options}
    return option_ids.get(raw_upper)


def _normalize_player_message_with_options(message: str, options: list[dict]) -> str:
    option_id = _resolve_option_id(message, options)
    if option_id is None:
        return message
    option_map = {str(opt.get("id", "")).strip().upper(): str(opt.get("text", "")).strip() for opt in options}
    return option_map.get(option_id.upper()) or message


def _scene_transcript_text(messages: list[dict]) -> str:
    return "\n".join(f'{msg["role"]}: {msg["content"]}' for msg in messages)


def _scene_cast_snapshot(session: GameSession) -> dict:
    characters = session.characters or {}
    return {
        "manager": dict(characters.get("manager") or {}),
        "buddy": dict(characters.get("buddy") or {}),
        "team_members": [dict(member) for member in characters.get("team_members", [])],
    }


def _memory_with_cast(memory_text: str, cast_snapshot: dict | None) -> str:
    if not memory_text:
        return ""
    snapshot = cast_snapshot or {}
    manager_name = str((snapshot.get("manager") or {}).get("name", "")).strip()
    buddy_name = str((snapshot.get("buddy") or {}).get("name", "")).strip()
    team_names = [str(member.get("name", "")).strip() for member in snapshot.get("team_members", []) if member.get("name")]
    cast_bits = []
    if manager_name:
        cast_bits.append(f"manager {manager_name}")
    if buddy_name:
        cast_bits.append(f"buddy {buddy_name}")
    if team_names:
        cast_bits.append(f"team {', '.join(team_names)}")
    if not cast_bits:
        return memory_text
    return f"【當時 cast：{'；'.join(cast_bits)}】{memory_text}"


def _recent_memories(db: Session, session_id: str, limit: int = 5) -> list[str]:
    rows = db.execute(
        select(SceneLog.memory_text, SceneLog.cast_snapshot)
        .where(SceneLog.session_id == session_id, SceneLog.memory_text.is_not(None))
        .order_by(desc(SceneLog.created_at))
        .limit(limit)
    ).all()
    return [_memory_with_cast(memory_text, cast_snapshot) for memory_text, cast_snapshot in rows if memory_text]


def _create_scene_log_with_perf_artifact(
    db: Session,
    session: GameSession,
    *,
    project_id: str,
    event_id: str,
    rating: str,
    reason: str,
    memory_text: str,
    state_delta: dict,
) -> SceneLog:
    locale = _session_locale(session)
    scene_kind = _scene_kind_from_ids(project_id, event_id)
    scene_id = project_id if scene_kind == "project" else event_id
    scene = _resolve_scene(scene_kind, scene_id, locale)
    row = SceneLog(
        session_id=session.id,
        project_id=project_id,
        event_id=event_id,
        state_snapshot=session.state,
        cast_snapshot=_scene_cast_snapshot(session),
        state_delta=state_delta,
        eval_provider="fixture",
        eval_model="fixture",
        eval_rating=rating,
        eval_reason=reason,
        eval_debug_json={"source": "dev_fixture"},
        memory_text=memory_text,
    )
    achievements = _perf_achievements(scene) or [{"framings": {}}]
    achievement = achievements[_primary_perf_achievement_index(row, achievements)]
    row.perf_artifact = _build_perf_artifact(scene_kind, scene_id, scene, row, achievement, locale)
    db.add(row)
    return row


def _scene_label(scene_kind: str, scene_id: str, locale: str | None = None) -> str:
    scene = _resolve_scene(scene_kind, scene_id, locale)
    return str(scene["title"])


def _perf_review_config(scene: dict) -> dict:
    config = scene.get("perf_review")
    return config if isinstance(config, dict) else {}


def _perf_achievements(scene: dict) -> list[dict]:
    config = _perf_review_config(scene)
    achievements = config.get("achievements")
    return achievements if isinstance(achievements, list) else []


def _has_text(text: str, *needles: str) -> bool:
    return any(needle.lower() in text.lower() for needle in needles)


def _perf_achievement_score(row: SceneLog, achievement: dict) -> int:
    match_terms = achievement.get("match_terms")
    if not isinstance(match_terms, list):
        match_terms = []

    memory_text = (row.memory_text or "").lower()
    eval_reason = (row.eval_reason or "").lower()
    label = str(achievement.get("label", "")).lower()
    hook = str(achievement.get("hook", "")).lower()

    score = 0
    for raw_term in match_terms:
        term = str(raw_term).strip().lower()
        if not term:
            continue
        if term in memory_text:
            score += 3
        if term in eval_reason:
            score += 2
        if term in label or term in hook:
            score += 1

    if hook and hook in memory_text:
        score += 2
    if label and label in eval_reason:
        score += 1
    return score


def _primary_perf_achievement_index(row: SceneLog, achievements: list[dict]) -> int:
    if not achievements:
        return 0
    artifact = row.perf_artifact if isinstance(row.perf_artifact, dict) else None
    artifact_label = str((artifact or {}).get("achievement_label", "")).strip()
    if artifact_label:
        for index, achievement in enumerate(achievements):
            if str(achievement.get("label", "")).strip() == artifact_label:
                return index

    scored = [
        (index, _perf_achievement_score(row, achievement))
        for index, achievement in enumerate(achievements)
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[0][0]


def _compact_perf_summary(text: str, limit: int = 120) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    suffix = "。" if re.search(r"[\u4e00-\u9fff]", cleaned) else "."
    return cleaned[: limit - 1].rstrip("，。；、,.;: ") + suffix


def _perf_player_facing_text(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    replacements = {
        "玩家": "你",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def _default_perf_framings(locale: str | None) -> tuple[str, str]:
    if _is_zh(locale):
        return (
            "強調你主動定義問題、提前講清楚風險，並把這件事往前推。",
            "強調你穩定接住混亂、協調他人，讓團隊能把事情順下來。",
        )
    return (
        "Emphasize that you proactively defined the problem, clarified the risks early, and moved the work forward.",
        "Emphasize that you stabilized a messy situation, coordinated people, and helped the team move the work through.",
    )


def _perf_title_from_text(scene_kind: str, scene_id: str, scene_title: str, text: str, locale: str | None) -> str:
    if scene_id == "standard_engineering_project":
        if _has_text(text, "線稿", "UI/UX", "設計稿", "素材"):
            return "補出 Demo 臨時線稿" if _is_zh(locale) else "Patch in Last-Minute Demo Mockups"
        if _has_text(text, "現有功能", "小功能", "優化", "Feature X"):
            return "Demo 前優化現有功能" if _is_zh(locale) else "Tighten Existing Features Before Demo"
        if _has_text(text, "MVP", "黏著度", "最小可行"):
            return "趕出黏著度 MVP" if _is_zh(locale) else "Ship a Retention MVP"
        return "收斂模糊 Demo 需求" if _is_zh(locale) else "Narrow a Vague Demo Request"
    if scene_id == "bug_fix_sprint":
        if _has_text(text, "白名單", "Auth", "認證"):
            return "追查認證服務問題" if _is_zh(locale) else "Trace the Auth Service Failure"
        return "收斂線上問題根因" if _is_zh(locale) else "Narrow the Production Root Cause"
    if scene_id == "system_design_rfc":
        if _has_text(text, "質疑", "reviewer", "審查壓力", "回應 review", "review 壓力"):
            return "接住 RFC Review 質疑" if _is_zh(locale) else "Absorb RFC Review Pushback"
        return "整理 RFC 架構取捨" if _is_zh(locale) else "Frame the RFC Tradeoffs"
    if scene_id == "cross_team_collab":
        if _has_text(text, "資料合約", "Data Contract", "Project Chimera"):
            return "Project Chimera 資料合約" if _is_zh(locale) else "Project Chimera Data Contract"
        return "對齊跨組合作邊界" if _is_zh(locale) else "Align Cross-Team Boundaries"
    if scene_id == "deadline_compressed":
        if _has_text(text, "上線", "核心功能", "提前"):
            return "提前上線核心功能" if _is_zh(locale) else "Pull Forward the Core Launch"
        return "壓縮時程下重切範圍" if _is_zh(locale) else "Rescope Under a Compressed Timeline"
    if scene_id == "teammate_no_handoff":
        if _has_text(text, "活動頁面", "Tina", "行銷"):
            return "釐清活動頁面優先級" if _is_zh(locale) else "Clarify the Campaign Page Priority"
        if _has_text(text, "報表", "Kevin", "API"):
            return "接手數據報表問題" if _is_zh(locale) else "Take Over the Reporting Issue"
        if _has_text(text, "隔壁組", "資料異常", "資料流向"):
            return "追查未交接資料異常" if _is_zh(locale) else "Trace the Unhanded Data Anomaly"
        if _has_text(text, "資料", "報表", "API"):
            return "接手未交接資料問題" if _is_zh(locale) else "Take Over the Unhanded Data Work"
        return "補上未交接任務脈絡" if _is_zh(locale) else "Reconstruct the Missing Handoff"
    if scene_kind == "project":
        return scene_title
    return scene_title


def _artifact_framings(artifact: dict) -> dict:
    framings = artifact.get("framings")
    return framings if isinstance(framings, dict) else {}


def _build_perf_artifact(
    scene_kind: str,
    scene_id: str,
    scene: dict,
    row: SceneLog,
    achievement: dict,
    locale: str | None,
    ai_artifact: dict | None = None,
) -> dict:
    template_framings = achievement.get("framings") if isinstance(achievement.get("framings"), dict) else {}
    if ai_artifact:
        title = _perf_player_facing_text(str(ai_artifact.get("title", "")).strip())
        summary = _perf_player_facing_text(str(ai_artifact.get("summary", "")).strip())
        framing_a = _perf_player_facing_text(str(ai_artifact.get("framing_a", "")).strip())
        framing_b = _perf_player_facing_text(str(ai_artifact.get("framing_b", "")).strip())
        if title and summary and framing_a and framing_b:
            return {
                "title": title,
                "summary": summary,
                "achievement_label": str(achievement.get("label", "")).strip(),
                "framings": {"A": framing_a, "B": framing_b},
                "source": "ai",
            }

    source_text = " ".join(
        part
        for part in [
            row.memory_text or "",
            row.eval_reason or "",
            str(achievement.get("label", "")),
            str(achievement.get("hook", "")),
        ]
        if part
    )
    title = _perf_title_from_text(scene_kind, scene_id, str(scene["title"]), source_text, locale)
    summary_source = row.eval_reason or row.memory_text or ""
    summary = _perf_player_facing_text(_compact_perf_summary(summary_source))
    if not summary:
        summary = (
            f"你完成了 {str(scene['title'])} 這段工作，但還需要把它包裝成能寫進 self-review 的成果。"
            if _is_zh(locale)
            else f"You got through the {str(scene['title'])} work, but it still needs to be packaged into something that can survive a self-review."
        )
    default_a, default_b = _default_perf_framings(locale)
    return {
        "title": title,
        "summary": summary,
        "achievement_label": str(achievement.get("label", "")).strip(),
        "framings": {
            "A": str(template_framings.get("A", default_a)).strip(),
            "B": str(template_framings.get("B", default_b)).strip(),
        },
        "source": "template",
    }


def _perf_artifact_for_candidate(scene_kind: str, scene_id: str, scene: dict, row: SceneLog, achievement: dict, locale: str | None) -> dict:
    artifact = row.perf_artifact if isinstance(row.perf_artifact, dict) else None
    if artifact:
        title = str(artifact.get("title", "")).strip()
        summary = _perf_player_facing_text(str(artifact.get("summary", "")).strip())
        if title and summary:
            return {"title": title, "summary": summary, "framings": _artifact_framings(artifact)}
    return _build_perf_artifact(scene_kind, scene_id, scene, row, achievement, locale)


def _perf_candidate_entry(
    row: SceneLog,
    scene_kind: str,
    scene_id: str,
    scene: dict,
    achievement: dict,
    *,
    entry_priority: int,
    angle_index: int,
    locale: str | None,
) -> dict:
    artifact = _perf_artifact_for_candidate(scene_kind, scene_id, scene, row, achievement, locale)
    base_label = artifact["title"]
    angle_label = str(achievement.get("label", "")).strip()
    label = base_label if not angle_label else (f"{base_label}（{angle_label}）" if _is_zh(locale) else f"{base_label} ({angle_label})")
    summary = artifact["summary"]
    artifact_framings = _artifact_framings(artifact)
    framings = artifact_framings or (achievement.get("framings") if isinstance(achievement.get("framings"), dict) else {})
    default_a, default_b = _default_perf_framings(locale)
    return {
        "scene_log_id": row.id,
        "scene_kind": scene_kind,
        "scene_id": scene_id,
        "label": label,
        "summary": summary,
        "memory_text": row.memory_text or "",
        "framings": {
            "A": str(framings.get("A", default_a)).strip(),
            "B": str(framings.get("B", default_b)).strip(),
        },
        "delta": row.state_delta or {},
        "eval_rating": row.eval_rating or "",
        "priority": entry_priority,
        "angle_index": angle_index,
        "_sort_ts": row.created_at.timestamp() if row.created_at else 0,
    }


def _perf_candidate_rows(db: Session, session_id: str, limit: int = 4, *, locale: str | None = None) -> list[dict]:
    last_perf = db.execute(
        select(SceneLog.created_at)
        .where(
            SceneLog.session_id == session_id,
            SceneLog.event_id == PERF_REVIEW_ID,
            SceneLog.eval_rating.is_not(None),
        )
        .order_by(desc(SceneLog.created_at), desc(SceneLog.id))
        .limit(1)
    ).scalar_one_or_none()

    filters = [
        SceneLog.session_id == session_id,
        SceneLog.memory_text.is_not(None),
        SceneLog.eval_rating.is_not(None),
    ]
    if last_perf is not None:
        filters.append(SceneLog.created_at > last_perf)

    rows = list(
        db.execute(
            select(SceneLog)
            .where(*filters)
            .order_by(desc(SceneLog.created_at), desc(SceneLog.id))
            .limit(16)
        ).scalars()
    )
    primary_project_candidates: list[dict] = []
    event_candidates: list[dict] = []
    supplemental_project_candidates: list[dict] = []
    for row in rows:
        scene_kind = _scene_kind_from_ids(row.project_id, row.event_id)
        scene_id = row.project_id if scene_kind == "project" else row.event_id
        if _is_perf_scene(scene_id) or _is_promo_scene(scene_id) or _is_pip_scene(scene_id) or _is_reorg_scene(scene_id):
            continue
        scene = _resolve_scene(scene_kind, scene_id, locale)
        perf_config = _perf_review_config(scene)
        achievements = _perf_achievements(scene)
        if scene_kind == "project":
            if not achievements:
                achievements = [{"framings": {}}]
            primary_index = _primary_perf_achievement_index(row, achievements)
            primary_project_candidates.append(
                _perf_candidate_entry(
                    row,
                    scene_kind,
                    scene_id,
                    scene,
                    achievements[primary_index],
                    entry_priority=0,
                    angle_index=primary_index,
                    locale=locale,
                )
            )
            for angle_index, achievement in enumerate(achievements):
                if angle_index == primary_index:
                    continue
                supplemental_project_candidates.append(
                    _perf_candidate_entry(
                        row,
                        scene_kind,
                        scene_id,
                        scene,
                        achievement,
                        entry_priority=2,
                        angle_index=angle_index,
                        locale=locale,
                    )
                )
            continue

        if not perf_config.get("eligible"):
            continue
        if row.eval_rating != "good":
            continue
        achievement = achievements[0] if achievements else {"framings": {}}
        event_candidates.append(
            _perf_candidate_entry(
                row,
                scene_kind,
                scene_id,
                scene,
                achievement,
                entry_priority=1,
                angle_index=0,
                locale=locale,
            )
        )

    primary_project_candidates.sort(key=lambda item: -item["_sort_ts"])
    event_candidates.sort(key=lambda item: -item["_sort_ts"])
    supplemental_project_candidates.sort(key=lambda item: -item["_sort_ts"])

    picked: list[dict] = []
    for pool in (primary_project_candidates, event_candidates, supplemental_project_candidates):
        for item in pool:
            if len(picked) >= limit:
                break
            picked.append(item)
        if len(picked) >= limit:
            break

    picked.sort(key=lambda item: (item["priority"], item["_sort_ts"]))
    for item in picked:
        item.pop("_sort_ts", None)
    return picked


def _perf_round_one_text(candidates: list[dict], locale: str | None) -> str:
    if not _is_zh(locale):
        lines = [
            "Performance review is here. First you need to decide which two accomplishments make it into the self-review.",
            "",
            "The cases available to package this cycle are:",
            "",
        ]
        for idx, candidate in enumerate(candidates, start=1):
            label = candidate.get("label") or _scene_label(candidate["scene_kind"], candidate["scene_id"], locale)
            lines.append(f"{idx}. [{label}] {candidate.get('summary') or candidate['memory_text']}")
        lines.extend(["", "Choose 2 items for the self-review."])
        return "\n".join(lines)
    lines = [
        "這次 performance review 開始了。你得先決定 self-review 要寫哪兩件事。",
        "",
        "這季可以拿來包裝的案例有：",
        "",
    ]
    for idx, candidate in enumerate(candidates, start=1):
        label = candidate.get("label") or _scene_label(candidate["scene_kind"], candidate["scene_id"], locale)
        lines.append(f"{idx}. [{label}] {candidate.get('summary') or candidate['memory_text']}")
    lines.extend(["", "請選 2 件寫進 self-review。"])
    return "\n".join(lines)


def _perf_round_one_options(candidates: list[dict], locale: str | None) -> list[dict]:
    options: list[dict] = []
    for idx, candidate in enumerate(candidates, start=1):
        label = candidate.get("label") or _scene_label(candidate["scene_kind"], candidate["scene_id"], locale)
        options.append({"id": str(idx), "text": label})
    return options


def _perf_framings(candidates: list[dict], locale: str | None) -> list[dict]:
    framings: list[dict] = []
    for candidate in candidates:
        framing_options = candidate.get("framings") or {}
        default_a, default_b = _default_perf_framings(locale)
        framings.append(
            {
                "label": candidate.get("label") or _scene_label(candidate["scene_kind"], candidate["scene_id"], locale),
                "summary": candidate.get("summary") or candidate.get("memory_text", ""),
                "A": str(framing_options.get("A", default_a)).strip(),
                "B": str(framing_options.get("B", default_b)).strip(),
            }
        )
    return framings


def _perf_round_two_text(framings: list[dict], locale: str | None) -> str:
    lines = (
        [
            "你選了兩件事。接下來要決定 self-review 的 framing。",
            "",
        ]
        if _is_zh(locale)
        else [
            "You picked two items. Now decide how to frame them in the self-review.",
            "",
        ]
    )
    for idx, framing in enumerate(framings, start=1):
        prefix = "事件" if _is_zh(locale) else "Item"
        lines.append(f"[{prefix} {idx} · {framing['label']}] {framing['summary']}")
        lines.append(f"A. {framing['A']}")
        lines.append(f"B. {framing['B']}")
        lines.append("")
    lines.append("請選一組 framing。" if _is_zh(locale) else "Choose one framing for each item.")
    return "\n".join(lines).strip()


def _perf_round_two_options(locale: str | None) -> list[dict]:
    item_label = "事件" if _is_zh(locale) else "Item"
    return [
        {"id": "1A", "text": f"{item_label} 1 · A"},
        {"id": "1B", "text": f"{item_label} 1 · B"},
        {"id": "2A", "text": f"{item_label} 2 · A"},
        {"id": "2B", "text": f"{item_label} 2 · B"},
    ]


def _build_perf_opening(db: Session, session: GameSession) -> tuple[str, list[dict]]:
    locale = _session_locale(session)
    candidates = _perf_candidate_rows(db, session.id, locale=locale)
    if len(candidates) < 2:
        if _is_zh(locale):
            fallback = [
                {
                    "scene_kind": "project",
                    "scene_id": "standard_engineering_project",
                    "label": "補位成果一",
                    "summary": "你只能從有限的紀錄中挑一段還算站得住腳的成果來寫。",
                    "memory_text": "本季可講的成果還不夠明確，你只能從有限的紀錄中硬挑重點。",
                    "framings": {
                        "A": "強調你至少有主動把模糊事情收斂成可執行方向。",
                        "B": "強調你在有限條件下仍把事情推到有具體進展。",
                    },
                },
                {
                    "scene_kind": "project",
                    "scene_id": "bug_fix_sprint",
                    "label": "補位成果二",
                    "summary": "你得把零碎的工作重新包成一段像樣的影響，才有東西能寫進文件。",
                    "memory_text": "有些事情本來很平，但 perf 時還是得想辦法包裝成可被理解的成果。",
                    "framings": {
                        "A": "強調你在混亂裡收斂問題，沒有讓事情放著自己爛。",
                        "B": "強調你把零散工作整理成可交代的結果，至少讓人看得懂你的貢獻。",
                    },
                },
            ]
        else:
            fallback = [
                {
                    "scene_kind": "project",
                    "scene_id": "standard_engineering_project",
                    "label": "Fallback accomplishment 1",
                    "summary": "You have to pull one defensible accomplishment out of a thin record and make it stand up on paper.",
                    "memory_text": "This season does not have enough clean wins, so you are forced to salvage a credible highlight from limited evidence.",
                    "framings": {
                        "A": "Emphasize that you at least turned something vague into an executable direction.",
                        "B": "Emphasize that you still pushed the work to a concrete point despite limited leverage.",
                    },
                },
                {
                    "scene_kind": "project",
                    "scene_id": "bug_fix_sprint",
                    "label": "Fallback accomplishment 2",
                    "summary": "You need to repackage scattered work into something that reads like a coherent impact statement.",
                    "memory_text": "Some work was flat by nature, but performance review still forces you to turn it into something legible as impact.",
                    "framings": {
                        "A": "Emphasize that you narrowed a messy problem instead of letting it rot on its own.",
                        "B": "Emphasize that you turned scattered work into an accountable result people could actually understand.",
                    },
                },
            ]
        candidates = fallback
    _set_perf_context(session, {"candidates": candidates})
    return _perf_round_one_text(candidates, locale), _perf_round_one_options(candidates, locale)


def _build_promo_opening(session: GameSession) -> tuple[str, list[dict]]:
    manager_name = session.characters["manager"]["name"]
    if not _is_zh(_session_locale(session)):
        text = (
            f"{manager_name} sends you a last-minute 1:1. At Hooli, a meeting that suddenly makes time for you without an agenda is usually either bad news or something even more inconvenient. "
            "When you walk into the room, they are not even half-looking at Slack for once."
            f'\n\n{manager_name} looks at you and speaks a little more slowly than usual. "Claire, congratulations. Your promo went through."'
            "\n\nFor a second you just stare. Then it lands that all the sentences you kept forcing into the last few performance reviews actually counted somewhere."
        )
        return text, []
    text = (
        f"你收到 {manager_name} 發來的一個臨時 1:1。這種沒有 agenda、但被特別挪出時間的會議，"
        "在 Hooli 通常不是壞消息，就是更麻煩的消息。你走進會議室時，對方難得沒有一邊回 Slack 一邊講話。"
        f"\n\n{manager_name} 看著你，語氣比平常慢了一點：「Claire，恭喜。這次 promo 過了。」"
        "\n\n那句話落下來的瞬間，你先是愣了一下，接著才意識到，過去幾輪 performance review 裡那些被硬擠進文件的句子，"
        "真的在某個地方被算數了。"
    )
    return text, []


def _build_pip_opening(session: GameSession) -> tuple[str, list[dict]]:
    manager_name = session.characters["manager"]["name"]
    if not _is_zh(_session_locale(session)):
        text = (
            f"{manager_name} sends an untitled meeting invite. It is thirty minutes long and the attendee list contains only the two of you. "
            "At Hooli, this format rarely carries good news. It usually means bad news wrapped in a neutral-looking calendar label."
            f'\n\nAfter you sit down, {manager_name} stays silent for two seconds, then slides a document toward you. "Claire, this is not a normal progress sync. The company has decided to put you on PIP."'
            "\n\nThe document lists the issues that have grown louder over your last few cycles: delivery risk, collaboration strain, and leadership concern about your consistency. "
            "At the same time, an HR performance platform activation email lands in your inbox with the tone of an ordinary system notice. You know every sentence from here on out can become evidence about whether you stay."
        )
        return text, []
    text = (
        f"{manager_name} 丟來一個沒有標題的會議邀請，時間只寫了三十分鐘，參與者也只有你們兩個。"
        "這種格式在 Hooli 很少帶來好事，通常只是把壞消息包進看起來很中性的行程名稱裡。"
        f"\n\n你坐下後，{manager_name} 先沉默了兩秒，才把文件推到你面前：「Claire，這次不是一般的進度對齊。公司決定把你放進 PIP。」"
        "\n\n那份文件裡列的是你最近幾輪被放大的問題：交付風險、協作壓力、以及高層對你穩定性的疑慮。"
        "同一時間，HR performance platform 的帳號啟用信也跳進信箱，主旨寫得像一般系統通知。"
        "你知道，現在開始每一句話都會被當成你能不能留下來的證據。"
    )
    return text, []


def _build_reorg_opening(session: GameSession) -> tuple[str, list[dict]]:
    locale = _session_locale(session)
    metadata = (session.characters or {}).get("last_reorg") or {}
    changes = describe_reorg_changes(metadata, locale=locale)
    layoff = metadata.get("layoff") or {}
    manager_name = session.characters["manager"]["name"]
    if not _is_zh(locale):
        lines = [
            "Friday, 4:30 PM. The company-wide email and the org chart update at the same time. Nobody explains why first. The new reporting line is simply already in effect.",
            "",
            "You stare at the screen for a few seconds before realizing this is not a cosmetic rename. It is a genuine swap of the people who affect your work every day.",
        ]
        if changes:
            lines.extend(["", "This round of changes includes:"])
            lines.extend(f"- {line}" for line in changes)
        if layoff.get("name"):
            replacement = layoff.get("replacement") or "a new hire"
            lines.extend(
                [
                    "",
                    f"Worse, {layoff['name']} did not move to another reporting line. They simply vanished from the list, and {replacement} is already on the meetings they used to own.",
                ]
            )
        lines.extend(
            [
                "",
                f"More immediately, the person running your next 1:1 is no longer the old manager but {manager_name}. The old Slack history is still there, but the rules are not.",
                "",
                "The system is not asking for your opinion. It only wants you to confirm that you have read it.",
            ]
        )
        options = [
            {"id": "A", "text": "Understood."},
            {"id": "B", "text": "Accept it quietly."},
            {"id": "C", "text": "Pretend this is a growth opportunity."},
        ]
        return "\n".join(lines), options
    lines = [
        "週五下午四點半，全公司信和 org chart 同時更新。沒有人先解釋原因，只有新的匯報線已經生效。",
        "",
        "你盯著畫面看了幾秒，才發現這不是單純換個名稱，而是真的換了一批會影響你每天工作的人。",
    ]
    if changes:
        lines.extend(["", "這次變動包括："])
        lines.extend(f"- {line}" for line in changes)
    if layoff.get("name"):
        replacement = layoff.get("replacement") or "新人"
        lines.extend(
            [
                "",
                f"更刺眼的是，{layoff['name']} 不是換到別的匯報線，而是直接從名單上消失；{replacement} 已經被排進原本的會議。",
            ]
        )
    lines.extend(
        [
            "",
            f"更麻煩的是，下次跟你開 1:1 的人已經不是舊 manager，而是 {manager_name}。Slack 舊訊息還在，但遊戲規則已經不是原本那套了。",
            "",
            "系統沒有徵求你的意見，只要求你確認自己已讀。",
        ]
    )
    options = [
        {"id": "A", "text": "我知道了"},
        {"id": "B", "text": "也只能默默接受"},
        {"id": "C", "text": "假裝這是個成長機會"},
    ]
    return "\n".join(lines), options


def _build_scene_opening(
    db: Session,
    session: GameSession,
    scene_config: dict,
    memories: list[str],
) -> tuple[str, list[dict], dict | None]:
    locale = _session_locale(session)
    if _is_perf_scene(scene_config["event_id"]):
        narration, options = _build_perf_opening(db, session)
        return narration, options, None
    if _is_promo_scene(scene_config["event_id"]):
        narration, options = _build_promo_opening(session)
        return narration, options, None
    if _is_pip_scene(scene_config["event_id"]):
        narration, options = _build_pip_opening(session)
        return narration, options, None
    if _is_reorg_scene(scene_config["event_id"]):
        narration, options = _build_reorg_opening(session)
        return narration, options, None

    bundle = _prompt_bundle_for_session(session)
    system_prompt = bundle.build_story_system_prompt(
        player_name=session.characters.get("player_name", default_player_name(locale)),
        manager=session.characters["manager"],
        buddy=session.characters["buddy"],
        team_members=session.characters.get("team_members", []),
        scene_kind=scene_config["kind"],
        scene=scene_config["scene"],
        current_round=1,
        rounds=scene_config["rounds"] + 1,
        memories=memories,
    )
    opening_messages = [{"role": "user", "content": _scene_start_marker(locale)}]
    opening_text, story_debug = story_response(
        system_prompt,
        opening_messages,
    )
    is_conversational = scene_config["scene"].get("conversational", False)
    show_options = _should_show_options(scene_config["kind"], 1, is_conversational)
    narration, options = _split_narration_and_options(opening_text, expect_options=show_options, locale=locale)
    if show_options and scene_config["kind"] == "project":
        options = _ensure_project_options(scene_config["scene"]["id"], 1, options, narration, locale=locale)
    if _should_force_question(scene_config["rounds"] > 0, show_options):
        narration = _ensure_question_ending(narration, locale)
    return narration, options, story_debug


def _parse_perf_selection(message: str, options: list[dict], expected_count: int, allowed: set[str]) -> list[str] | None:
    option_id = _resolve_option_id(message, options)
    raw = option_id or message.strip().upper().replace(",", " ")
    tokens = [token for token in raw.split() if token]
    if len(tokens) != expected_count:
        return None
    if len(set(tokens)) != expected_count:
        return None
    if any(token not in allowed for token in tokens):
        return None
    return tokens


def _parse_perf_framing_selection(message: str, options: list[dict]) -> list[str] | None:
    selection = _parse_perf_selection(message, options, 2, {"1A", "1B", "2A", "2B"})
    if selection is None:
        extracted = [
            f"{match.group(1)}{match.group(2).upper()}"
            for match in PERF_FRAMING_TOKEN_RE.finditer(message or "")
        ]
        if len(extracted) == 2:
            selection = extracted
        else:
            return None

    picked_by_event: dict[str, str] = {}
    for token in selection:
        event_index = token[0]
        frame = token[1]
        if event_index in picked_by_event:
            return None
        picked_by_event[event_index] = frame

    if set(picked_by_event.keys()) != {"1", "2"}:
        return None
    return [picked_by_event["1"], picked_by_event["2"]]


def _perf_review_delta(rating: str) -> dict[str, int]:
    roll = random.random()
    if rating == "good":
        if roll < 0.7:
            return {"visibility": 1}
        return {"affinity": 1}
    if rating == "bad":
        if roll < 0.3:
            return {"visibility": -1}
        if roll < 0.6:
            return {"affinity": -1}
        return {"pip_potential": 1}
    return {}


def _recent_history(session: GameSession, key: str, limit: int) -> set[str]:
    values = (session.characters or {}).get(key) or []
    return {str(value) for value in values[-limit:] if str(value)}


def _draw_next_scene_for_session(session: GameSession, kind: str) -> dict:
    locale = _session_locale(session)
    if kind == "project":
        project = draw_project(
            session.state,
            exclude_ids=_recent_history(session, "recent_project_ids", RECENT_PROJECT_EXCLUDE_LIMIT),
            locale=locale,
        )
        return {"kind": "project", "id": project["id"]}

    if kind == "event":
        if should_trigger_reorg(session.state):
            event = get_special_event(REORG_EVENT_ID, locale=locale)
        else:
            event = draw_event(
                session.state,
                exclude_ids=_recent_history(session, "recent_event_ids", RECENT_EVENT_EXCLUDE_LIMIT),
                locale=locale,
            )
        return {"kind": "event", "id": event["id"]}

    raise ValueError(f"Unknown scene kind: {kind}")


def _record_scene_history(session: GameSession, scene_ref: dict) -> None:
    characters = dict(session.characters or {})
    if scene_ref["kind"] == "project":
        key = "recent_project_ids"
    else:
        key = "recent_event_ids"
    history = [str(item) for item in characters.get(key, []) if str(item)]
    if not history or history[-1] != scene_ref["id"]:
        history.append(scene_ref["id"])
    characters[key] = history[-8:]
    session.characters = characters


def _sync_scene_history_from_logs(db: Session, session: GameSession, limit: int = 8) -> None:
    rows = list(
        db.execute(
            select(SceneLog)
            .where(SceneLog.session_id == session.id)
            .order_by(desc(SceneLog.created_at), desc(SceneLog.id))
            .limit(limit * 2)
        ).scalars()
    )
    project_ids: list[str] = []
    event_ids: list[str] = []
    for row in reversed(rows):
        if row.project_id and row.project_id != EMPTY_SCENE_ID:
            project_ids.append(row.project_id)
        elif row.event_id and row.event_id != EMPTY_SCENE_ID:
            event_ids.append(row.event_id)

    characters = dict(session.characters or {})
    if project_ids:
        characters["recent_project_ids"] = project_ids[-8:]
    if event_ids:
        characters["recent_event_ids"] = event_ids[-8:]
    session.characters = characters


def _choose_next_scene_after_perf_review(session: GameSession) -> tuple[dict, list[dict]]:
    state = session.state
    if _promo_eligible(state):
        return {"kind": "event", "id": PROMO_SCENE_ID}, []
    if _pip_eligible(state):
        return {"kind": "event", "id": PIP_SCENE_ID}, []
    if int(state.get("perf_review_misses", 0)) >= 2:
        return {"kind": "event", "id": PIP_SCENE_ID}, []
    pending_scenes = list((session.characters or {}).get("pending_scenes", []))
    if pending_scenes:
        return pending_scenes.pop(0), pending_scenes
    return _draw_next_scene_for_session(session, "project"), []


def _perf_reason_for_player(reason: str | None, selected: list[dict], locale: str | None) -> str:
    if not reason:
        return ""
    if "Eval AI 呼叫失敗" in reason or "ConnectError" in reason:
        return ""

    def replace_event(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if 0 <= index < len(selected):
            default_label = f"事件 {index + 1}" if _is_zh(locale) else f"Item {index + 1}"
            label = str(selected[index].get("label", default_label)).strip() or default_label
            return f"「{label}」" if _is_zh(locale) else f'"{label}"'
        return match.group(0)

    rewritten = PERF_REASON_EVENT_RE.sub(replace_event, reason)
    if _is_zh(locale):
        rewritten = rewritten.replace("framing", "包裝角度")
    return _perf_player_facing_text(rewritten)


def _perf_fallback_eval_reason(rating: str, locale: str | None) -> str:
    if not _is_zh(locale):
        if rating == "good":
            return "Nobody in the room praised it out loud, but nobody knocked those two stories down either. In calibration, that already counts as a positive signal."
        if rating == "bad":
            return "The vibe was that you did real work, but the framing sounded like you were trying to rescue a project that never had a clear point."
        return "The general read was: not weak enough to get called out, not strong enough to make everyone stop and look twice."
    if rating == "good":
        return "房間裡沒有人大聲稱讚，但也沒有人把那兩段故事打掉。這在 calibration 裡已經算是一種正面訊號。"
    if rating == "bad":
        return "聽起來有人覺得你是真的有做事，只是講法太像在幫一個沒有得分點的 project 找台階。"
    return "風向大概是：內容沒有爛到被挑出來，但也沒有強到讓大家停下來多看一眼。"


def _perf_gossip_line(rating: str, reason: str | None, locale: str | None) -> str:
    if reason:
        if not _is_zh(locale):
            if rating == "good":
                prefix = random.choice(
                    [
                        "The version you heard afterward was",
                        "The short hallway read was",
                        "What came back through the grapevine was",
                    ]
                )
            elif rating == "bad":
                prefix = random.choice(
                    [
                        "The harsher hallway version was",
                        "What made it back to you sounded like",
                        "The polite wording was thin, but the meaning was",
                    ]
                )
            else:
                prefix = random.choice(
                    [
                        "The vague post-calibration read was",
                        "What drifted back afterward was",
                        "The room seemed to land on something like",
                    ]
                )
            return f"{prefix}: {reason}"
        if rating == "good":
            prefix = random.choice(
                [
                    "會後有人私下說",
                    "你聽到的版本是",
                    "傳回來的風向很短",
                ]
            )
        elif rating == "bad":
            prefix = random.choice(
                [
                    "比較刺耳的版本是",
                    "會後繞了一圈傳回來的說法是",
                    "有人把話講得很委婉，但意思差不多是",
                ]
            )
        else:
            prefix = random.choice(
                [
                    "走廊版摘要是",
                    "會後流出來的不是正式結論，比較像一句模糊風向",
                    "你聽到的 calibration 風向大概是",
                ]
            )
        return f"{prefix}：{reason}"
    return _perf_fallback_eval_reason(rating, locale)


def _build_perf_result_text(
    session: GameSession,
    rating: str,
    reason: str | None,
    selected: list[dict],
    next_ref: dict,
) -> str:
    locale = _session_locale(session)
    manager_name = session.characters["manager"]["name"]
    player_reason = _perf_reason_for_player(reason, selected, locale) or _perf_fallback_eval_reason(rating, locale)
    if _is_zh(locale) and rating == "good":
        opening = (
            f"calibration 結束後，{manager_name} 把文件合起來，語氣比平常更直接一點。"
            "這次你的 self-review 沒有被當成硬擠出來的流水帳，幾個例子都算站得住。"
        )
    elif _is_zh(locale) and rating == "bad":
        opening = (
            f"calibration 結束得很快。{manager_name} 出來時沒有特別安撫，只說這次的故事沒有你想像中那麼有說服力。"
            "你做過事，但包裝沒有把價值穩穩立起來。"
        )
    elif _is_zh(locale):
        opening = (
            f"calibration 結束後，{manager_name} 給你的反應不算冷，但也談不上特別亮眼。"
            "這次 self-review 至少完整交代了你做過的事，只是還不到會讓房間裡所有人立刻點頭的程度。"
        )
    elif rating == "good":
        opening = (
            f"After calibration, {manager_name} closes the document and sounds a little more direct than usual. "
            "This time your self-review did not land like something forced out for the sake of the form; the examples held up."
        )
    elif rating == "bad":
        opening = (
            f"Calibration ends quickly. When {manager_name} comes out, there is no special softening; "
            "the story simply did not sound as convincing as you hoped. You did real work, but the framing did not make the value stand up cleanly."
        )
    else:
        opening = (
            f"After calibration, {manager_name}'s reaction is not cold, but it is not especially bright either. "
            "The self-review at least explained what you did, but not strongly enough to make everyone in the room immediately nod."
        )

    lines = [opening]
    lines.extend(["", _perf_gossip_line(rating, player_reason, locale)])

    if next_ref["id"] == PROMO_SCENE_ID:
        lines.extend(
            ["", "這輪結果顯然把你往 promo 那邊推了一步，後續不會只是『照常繼續』。"]
            if _is_zh(locale)
            else ["", "This result clearly nudges you one step closer to promotion. The next step will not be business as usual."]
        )
    elif next_ref["id"] == PIP_SCENE_ID:
        lines.extend(
            ["", "更糟的是，這輪沒有把風向拉回來，反而讓高層對你的疑慮更具體了。"]
            if _is_zh(locale)
            else ["", "Worse, this round did not pull the narrative back. It made leadership's concerns about you more concrete."]
        )
    else:
        lines.extend(
            ["", "至少這次 review 的風向已經定案。接下來沒有結論幫你撐場，還是得回去繼續把下一季做出來。"]
            if _is_zh(locale)
            else ["", "At least the direction of this review is settled now. No conclusion will carry you from here; you still have to go back and build the next quarter."]
        )

    return "\n".join(lines).strip()


def _promo_eligible(state: dict) -> bool:
    return (
        int(state.get("tech", 0)) >= 6
        and int(state.get("visibility", 0)) >= 5
        and int(state.get("affinity", 0)) >= 4
        and int(state.get("pip_potential", 0)) <= 5
    )


def _pip_eligible(state: dict) -> bool:
    pip_potential = int(state.get("pip_potential", 0))
    tech = int(state.get("tech", 0))
    affinity = int(state.get("affinity", 0))
    return pip_potential >= 8 or (pip_potential >= 6 and (tech <= 4 or affinity <= 3))


def _pip_week_context(locale: str | None, round_in_scene: int, transfer_requested: bool) -> str:
    week = min(max(round_in_scene + 1, 1), 3)
    noise = random.choice(_pip_noise_pool(locale))
    if _is_zh(locale):
        if week == 1:
            transfer_line = "第一週轉組線：HR performance platform 帳號啟用，頁面上多了一個 Internal Mobility 分頁。"
        elif week == 2:
            if transfer_requested:
                transfer_line = "第二週轉組線：你悄悄跟隔壁組的 Tech Lead 吃了午餐，對方沒有拒絕，但每句話都說得像法務看過。"
            else:
                transfer_line = "第二週轉組線：HR 平台推了一個內部職缺推薦，但看起來更像系統自動補上的安慰貼紙。"
        elif transfer_requested:
            transfer_line = "第三週轉組線：你還在等隔壁組和 HR 的通知，兩邊都還沒有答案。"
        else:
            transfer_line = "第三週轉組線：HR 系統提醒 PIP checkpoint 即將到期，內部職缺頁面仍然安靜。"
        return "\n".join(
            [
                f"第 {week} 週 PIP check-in，不是同一場會議延伸。",
                f"背景雜訊：{noise}",
                transfer_line,
                "請把這些內容自然帶入壓力感；背景雜訊不能取代本輪主線。",
            ]
        )
    if week == 1:
        transfer_line = "Week 1 transfer thread: the HR performance platform account is activated and an Internal Mobility tab suddenly appears."
    elif week == 2:
        if transfer_requested:
            transfer_line = "Week 2 transfer thread: you quietly have lunch with the neighboring team's Tech Lead. They do not say no, but every sentence sounds reviewed by legal."
        else:
            transfer_line = "Week 2 transfer thread: the HR platform recommends an internal opening, though it feels more like an automated sympathy sticker."
    elif transfer_requested:
        transfer_line = "Week 3 transfer thread: you are still waiting on updates from the neighboring team and HR, and neither side has an answer."
    else:
        transfer_line = "Week 3 transfer thread: the HR system reminds you that the PIP checkpoint is approaching and the internal jobs page is still quiet."
    return "\n".join(
        [
            f"Week {week} PIP check-in. This is not the same meeting stretched out.",
            f"Background noise: {noise}",
            transfer_line,
            "Work these details naturally into the pressure of the round; the background noise must not replace the main thread.",
        ]
    )


def _pip_prompt_scene(scene: dict, locale: str | None, round_in_scene: int, transfer_requested: bool) -> dict:
    prompt_scene = dict(scene)
    locale = normalize_locale(locale)
    header = "【本輪 PIP 週次背景】" if _is_zh(locale) else "[PIP week context for this round]"
    prompt_scene["story"] = f"{scene['story']}\n\n{header}\n{_pip_week_context(locale, round_in_scene, transfer_requested)}"
    return prompt_scene


def _pip_round_leadin(locale: str | None, round_in_scene: int, transfer_requested: bool) -> str:
    week = min(max(round_in_scene + 1, 1), 3)
    if _is_zh(locale):
        if week == 1:
            lead = "那場 PIP 宣告之後，時間沒有停住。到了這週稍晚，你第一次正式 check-in 的會議已經排進日曆。"
            thread = (
                "HR performance platform 也多了一個 Internal Mobility 分頁，像是系統比任何人都更早替你想好了退路。"
            )
        elif week == 2:
            lead = "一週過去，第二次 check-in 來得很準時。這已經不是同一場談話的延長，而是新一週的壓力被重新擺到桌上。"
            thread = (
                "你悄悄和隔壁組的 Tech Lead 吃了午餐，對方沒有直接拒絕，但每一句都像是先過過法務。"
                if transfer_requested
                else "HR 平台推了一個內部職缺推薦，但看起來更像系統自動補上的安慰貼紙。"
            )
        else:
            lead = "又一週過去，最後一次 checkpoint 已經逼近。HR 的節奏、manager 的眼神，和你自己的心跳都開始對齊到同一個倒數上。"
            thread = (
                "隔壁組和 HR 那邊都還沒有回音，像是所有人都想把答案拖到最後一刻。"
                if transfer_requested
                else "Internal jobs 頁面依然安靜，像是連系統都懶得對你假裝有新消息。"
            )
        return f"{lead}\n\n{thread}"

    if week == 1:
        lead = "The PIP announcement does not freeze time. Later that week, the first formal check-in is already on your calendar."
        thread = "At the same time, the HR performance platform quietly grows a new Internal Mobility tab, as if the system has started planning your exit before anyone says it aloud."
    elif week == 2:
        lead = "One week passes. The second check-in arrives on schedule. This is not the same conversation stretched out; it is a new week with the pressure reset on the table."
        thread = (
            "You quietly have lunch with the neighboring team's Tech Lead. They do not say no, but every sentence sounds reviewed by legal."
            if transfer_requested
            else "The HR platform recommends an internal opening, though it feels more like an automated sympathy sticker than a real opportunity."
        )
    else:
        lead = "Another week passes. The final checkpoint is close now. HR's cadence, your manager's tone, and your own pulse are all starting to line up with the same countdown."
        thread = (
            "You are still waiting on the neighboring team and HR, and neither side has given you a real answer."
            if transfer_requested
            else "The internal jobs page is still quiet, as if even the system cannot be bothered to fake good news."
        )
    return f"{lead}\n\n{thread}"


def _pip_survived(state: dict, rating: str) -> bool:
    if int(state.get("pip_potential", 0)) <= 4:
        return True
    return rating == "good" and random.random() < 0.15


def _pip_transfer_success(state: dict, rating: str, transfer_requested: bool) -> bool:
    if not transfer_requested:
        return False
    affinity = int(state.get("affinity", 0))
    if affinity >= 5:
        return True
    chance = 0.10
    if rating == "good":
        chance += 0.25
    elif rating == "neutral":
        chance += 0.10
    if affinity >= 4:
        chance += 0.20
    elif affinity <= 2:
        chance -= 0.05
    return random.random() < max(0.05, min(chance, 0.45))


def _pip_outcome_text(kind: str, manager_name: str, locale: str | None, transfer_requested: bool = False) -> str:
    if not _is_zh(locale):
        if kind == "transfer_survive":
            return (
                "Before the week-three review is even fully closed, another HR notification lands first. "
                f"An offer letter from the neighboring team shows up under a subject line that looks like an ordinary internal mobility update. {manager_name}'s PIP paperwork is still moving, but the new team has already pulled you out; "
                "this is not a clean comeback so much as slipping out through a side door before the main one shuts."
            )
        if kind == "transfer_escape":
            return (
                f"Before {manager_name} can even pull you into that final meeting, another offer letter arrives. "
                "The PIP narrative did not improve, but the internal transfer finished first; you did not win the review, you just got out before it landed."
            )
        if kind == "survive":
            return (
                "The final review lands as a barely pass. "
                f"{manager_name} says they will keep watching delivery stability, but the PIP does not escalate into termination for now; "
                "you stay on the same team, except every Slack ping sounds louder than it used to."
            )
        prefix = "The internal transfer update you were waiting for never arrives, and the neighboring team answers only with a line about headcount still being under review. " if transfer_requested else ""
        return (
            f"{prefix}By the end of the meeting, the document is formally pushed across the table toward you. "
            "You can tell this is not the version that still has room for discussion. It is the version Hooli already wrote the answer for. "
            "After a few polished process words, the company ends the relationship in the way it has practiced most."
        )
    if kind == "transfer_survive":
        return (
            "第三週 review 結束前，HR 系統先跳出另一個通知。隔壁組的 offer letter 進來了，"
            f"標題寫得像普通 internal mobility update。{manager_name} 的 PIP 文件還在跑，你已經被新組撈走；"
            "這次不是漂亮翻身，比較像在門關上前從側門出去。"
        )
    if kind == "transfer_escape":
        return (
            f"{manager_name} 還沒來得及約你進最後那場會議，你已經收到另一個 offer letter。"
            "PIP 這邊的評語沒有變好，但內部轉組流程先完成；你沒有贏過這輪 review，只是趕在它正式落槌前跳走。"
        )
    if kind == "survive":
        return (
            "最後 review 被標成 barely pass。"
            f"{manager_name} 說後續還會盯交付穩定性，但 PIP 暫時沒有升級成 termination；"
            "你留在原組，只是 Slack 每跳一次都比以前吵。"
        )
    prefix = "你等的內部轉組通知沒有來，隔壁組也只回了一句「目前 headcount 還在確認」。" if transfer_requested else ""
    return (
        f"{prefix}會議收尾時，文件被正式往你面前推過來。你知道這不是還有討論空間的版本，"
        "而是 Hooli 已經把答案寫好的版本。幾個流程用語說完之後，這段關係就被公司用最熟練的方式結束了。"
    )


def _transfer_requested(messages: list[dict]) -> bool:
    for msg in messages:
        if msg["role"] != "user":
            continue
        if TRANSFER_REQUEST_RE.search(msg["content"] or ""):
            return True
    return False


def _counts_toward_perf(scene_kind: str, scene_id: str) -> bool:
    if scene_kind == "project":
        return scene_id != EMPTY_SCENE_ID
    return not (
        _is_perf_scene(scene_id)
        or _is_promo_scene(scene_id)
        or _is_pip_scene(scene_id)
        or _is_reorg_scene(scene_id)
    )


def _advance_progress_state(state: dict, scene_kind: str, scene_id: str) -> dict:
    updated = dict(state)
    if _counts_toward_perf(scene_kind, scene_id):
        updated["completed_cycles"] = int(updated.get("completed_cycles", 0)) + 1
    cooldown_remaining = int(updated.get("reorg_cooldown_events_remaining", 0) or 0)
    if scene_kind == "event":
        if scene_id == REORG_EVENT_ID:
            updated["reorg_cooldown_events_remaining"] = REORG_COOLDOWN_EVENTS
        elif cooldown_remaining > 0:
            updated["reorg_cooldown_events_remaining"] = cooldown_remaining - 1
    updated["rounds_since_promo"] = int(updated.get("completed_cycles", 0))
    return updated


def _choose_followup_scene(session: GameSession, scene_kind: str, scene_id: str) -> tuple[dict, list[dict]]:
    if _is_perf_scene(scene_id):
        return _choose_next_scene_after_perf_review(session)

    characters = dict(session.characters)
    pending_scenes = list(characters.get("pending_scenes", []))
    completed_cycles = int(session.state.get("completed_cycles", 0))
    should_trigger_perf_review = (
        _counts_toward_perf(scene_kind, scene_id)
        and completed_cycles > 0
        and completed_cycles % PERF_TRIGGER_CYCLES == 0
    )
    if should_trigger_perf_review:
        if not pending_scenes:
            next_kind = "event" if scene_kind == "project" else "project"
            pending_scenes = [_draw_next_scene_for_session(session, next_kind)]
        return {"kind": "event", "id": PERF_REVIEW_ID}, pending_scenes
    if pending_scenes:
        return pending_scenes.pop(0), pending_scenes
    next_kind = "event" if scene_kind == "project" else "project"
    return _draw_next_scene_for_session(session, next_kind), []


def _end_session(db: Session, session: GameSession, end_reason: str) -> None:
    normalized_end_reason = _normalize_ending_kind(end_reason)
    session.status = "ended"
    session.end_reason = normalized_end_reason
    session.settlement_status = "idle"
    db.flush()


def _handle_quit_confirmation(
    session: GameSession,
    scene_log: SceneLog,
    body: TurnRequest,
    db: Session,
) -> dict:
    locale = _session_locale(session)
    options = _current_options(session)
    raw_message = body.message.strip()
    option_id = _resolve_option_id(raw_message, options)
    if option_id is None:
        text_to_id = {str(opt.get("text", "")).strip(): str(opt.get("id", "")).strip().upper() for opt in options}
        option_id = text_to_id.get(raw_message, raw_message.upper())
    else:
        option_id = option_id.upper()
    quit_context = _current_quit_context(session)
    if option_id == "A":
        user_text = "繼續撐一下" if _is_zh(locale) else "Keep going"
        db.add(Message(scene_log_id=scene_log.id, role="user", content=user_text))
        assistant_text = (
            "好吧。你把 resignation draft 關掉，假裝自己只是去接了杯水。會議和需求還在，至少 vest 也還在往你這邊慢慢滑。"
            if _is_zh(locale)
            else "Fine. You close the resignation draft and pretend you only got up for water. The meetings are still here, but so is the vest schedule."
        )
        db.add(Message(scene_log_id=scene_log.id, role="assistant", content=assistant_text))
        restored_options = quit_context.get("resume_options") if isinstance(quit_context.get("resume_options"), list) else []
        _set_current_options(session, restored_options)
        _set_quit_context(session, None)
        db.commit()
        return {
            "text": assistant_text,
            "generated_by": None,
            "options": restored_options,
            "scene_ended": False,
            "round": session.round_in_scene,
        }

    if option_id == "B":
        user_text = "我還是要辭職" if _is_zh(locale) else "I still want to quit"
        db.add(Message(scene_log_id=scene_log.id, role="user", content=user_text))
        assistant_text = (
            "你把那點 vest 的殘念一起關掉，直接往辭職結局走。"
            if _is_zh(locale)
            else "You let the remaining vest temptation die with the tab and commit to the exit."
        )
        db.add(Message(scene_log_id=scene_log.id, role="assistant", content=assistant_text))
        _set_current_options(session, [])
        _set_quit_context(session, None)
        _end_session(db, session, "quit")
        db.commit()
        final_text = f"{assistant_text}\n\n遊戲已結束。" if _is_zh(locale) else f"{assistant_text}\n\nThe game has ended."
        return {
            "text": final_text,
            "generated_by": None,
            "options": [],
            "scene_ended": True,
            "round": session.round_in_scene,
            "game_ended": True,
            "end_reason": "quit",
            "ending": _ending_payload_for_session(db, session, "quit"),
        }

    raise HTTPException(
        status_code=400,
        detail="請選 A 或 B。" if _is_zh(locale) else "Choose A or B.",
    )


def _activate_next_scene(
    db: Session,
    session: GameSession,
    next_ref: dict,
    pending_scenes: list[dict],
) -> None:
    locale = _session_locale(session)
    if next_ref["kind"] == "event" and _is_reorg_scene(next_ref["id"]):
        swapped_characters, _ = apply_reorg_cast_swap(session.characters)
        session.characters = swapped_characters

    characters = dict(session.characters)
    characters["pending_scenes"] = pending_scenes
    characters.pop("perf_review", None)
    session.characters = characters
    _record_scene_history(session, next_ref)

    next_config = _scene_config_from_ref(next_ref, locale)
    next_scene = SceneLog(
        session_id=session.id,
        event_id=next_config["event_id"],
        project_id=next_config["project_id"],
        state_snapshot=session.state,
        cast_snapshot=_scene_cast_snapshot(session),
    )
    db.add(next_scene)
    db.flush()

    memories = _recent_memories(db, session.id, limit=5)
    narration, options, story_debug = _build_scene_opening(db, session, next_config, memories)
    _append_story_debug(
        next_scene,
        phase="opening",
        scene_kind=next_config["kind"],
        scene_id=next_config["project_id"] if next_config["kind"] == "project" else next_config["event_id"],
        current_round=1,
        messages=[{"role": "user", "content": _scene_start_marker(locale)}],
        debug_payload=story_debug,
    )
    _set_current_options(session, options)
    db.add(Message(scene_log_id=next_scene.id, role="assistant", content=narration))

    session.current_scene_log_id = next_scene.id
    session.current_event_id = next_config["event_id"]
    session.current_project_id = next_config["project_id"]
    session.round_in_scene = 0
    session.scene_round_limit = next_config["rounds"]
    session.settlement_status = "ready"


def _handle_perf_turn(
    session: GameSession,
    scene_log: SceneLog,
    body: TurnRequest,
    background_tasks: BackgroundTasks,
    db: Session,
) -> dict:
    locale = _session_locale(session)
    bundle = _prompt_bundle_for_session(session)
    options = _current_options(session)
    context = _current_perf_context(session)

    if session.round_in_scene == 0:
        candidates = context.get("candidates") or []
        selection = _parse_perf_selection(body.message, options, 2, {str(i) for i in range(1, len(candidates) + 1)})
        if selection is None:
            raise HTTPException(status_code=400, detail="請選兩個數字，例如：1 3" if _is_zh(locale) else "Choose two numbers, for example: 1 3")
        indices = [int(token) - 1 for token in selection]
        selected = [candidates[index] for index in indices]
        if _is_zh(locale):
            user_content = "選擇寫入 self-review：\n" + "\n".join(
                f"{token}. [{item['label']}] {item.get('summary') or item['memory_text']}" for token, item in zip(selection, selected)
            )
        else:
            user_content = "Selected for self-review:\n" + "\n".join(
                f"{token}. [{item['label']}] {item.get('summary') or item['memory_text']}" for token, item in zip(selection, selected)
            )
        db.add(Message(scene_log_id=scene_log.id, role="user", content=user_content))

        framings = _perf_framings(selected, locale)
        next_options = _perf_round_two_options(locale)
        context["selected"] = selected
        context["framings"] = framings
        _set_perf_context(session, context)
        narration = _perf_round_two_text(framings, locale)
        db.add(Message(scene_log_id=scene_log.id, role="assistant", content=narration))
        _set_current_options(session, next_options)
        session.round_in_scene += 1
        db.commit()
        return {
            "text": narration,
            "generated_by": None,
            "options": next_options,
            "scene_ended": False,
            "round": session.round_in_scene,
        }

    framings = context.get("framings") or []
    selection = _parse_perf_framing_selection(body.message, options)
    if selection is None or len(framings) != 2:
        raise HTTPException(status_code=400, detail="請各選一個 framing，例如：1A 2B" if _is_zh(locale) else "Choose one framing for each item, for example: 1A 2B")

    user_lines = ["選擇的 framing："] if _is_zh(locale) else ["Selected framing:"]
    selected_source = context.get("selected") if isinstance(context.get("selected"), list) else []
    selected_for_ending: list[dict] = []
    for idx, token in enumerate(selection):
        framing = framings[idx]
        chosen_text = str(framing[token]).strip()
        selected_item = dict(selected_source[idx]) if idx < len(selected_source) and isinstance(selected_source[idx], dict) else {}
        selected_item["chosen_framing"] = token
        selected_item["chosen_framing_text"] = chosen_text
        selected_for_ending.append(selected_item)
        user_lines.append(
            f"事件 {idx + 1} · {token}: {chosen_text}"
            if _is_zh(locale)
            else f"Item {idx + 1} · {token}: {chosen_text}"
        )
    db.add(Message(scene_log_id=scene_log.id, role="user", content="\n".join(user_lines)))

    transcript_text = _scene_transcript_text(_scene_messages(db, scene_log.id))
    raw_reason = None
    rating, raw_reason, eval_debug = evaluate_rating(
        bundle.build_eval_prompt("event", _perf_review_scene(locale)),
        transcript_text,
    )
    delta = _perf_review_delta(rating)
    memory_text = summarize_memory(transcript_text, locale=locale)
    player_reason = _perf_reason_for_player(raw_reason, context.get("selected") or [], locale)
    stored_reason = player_reason or _perf_fallback_eval_reason(rating, locale)

    scene_log.state_delta = delta
    scene_log.eval_rating = rating
    scene_log.eval_reason = stored_reason
    _set_eval_debug(scene_log, {**eval_debug, "raw_reason": raw_reason})
    scene_log.memory_text = memory_text

    new_state = _advance_progress_state(apply_state_delta(session.state, delta), "event", PERF_REVIEW_ID)
    if _promo_eligible(new_state):
        new_state["perf_review_misses"] = 0
    else:
        new_state["perf_review_misses"] = int(new_state.get("perf_review_misses", 0)) + 1
    session.state = new_state
    _set_ending_context(
        session,
        {
            "source": "perf_review",
            "rating": rating,
            "reason": stored_reason,
            "selected": selected_for_ending,
        },
    )

    _sync_scene_history_from_logs(db, session)
    next_ref, pending_scenes = _choose_next_scene_after_perf_review(session)
    result_text = _build_perf_result_text(
        session,
        rating,
        stored_reason,
        context.get("selected") or [],
        next_ref,
    )
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=result_text))
    _set_current_options(session, [])
    _set_perf_context(session, None)
    session.round_in_scene += 1
    _activate_next_scene(db, session, next_ref, pending_scenes)
    db.commit()
    return {
        "text": result_text,
        "generated_by": None,
        "options": [],
        "scene_ended": True,
        "round": session.round_in_scene,
    }


def _handle_promo_turn(
    session: GameSession,
    scene_log: SceneLog,
    body: TurnRequest,
    db: Session,
) -> dict:
    locale = _session_locale(session)
    player_text = _sanitize_player_text(body.message, allow_empty=True) or ("……謝謝。" if _is_zh(locale) else "...Thanks.")
    db.add(Message(scene_log_id=scene_log.id, role="user", content=player_text))
    manager_name = session.characters["manager"]["name"]
    if _is_zh(locale):
        closing_text = (
            f"{manager_name} 聽完你的回應，只是點了點頭，難得沒有立刻切去下一個會議視窗。"
            "她把升職通知往你這邊推了一下，補了一句：「接下來別只做把事情救回來的人，開始當那個先把方向定下來的人。」"
            "\n\n會議結束後，你回到座位，Slack 上還是有人在問 bug、問時程、問誰要接這個臨時需求。"
            "只是這一次，那些訊息的背景噪音裡，多了一個很具體的事實：你已經升上 Senior 了。"
        )
        scene_log.eval_reason = "Performance review 達標，promo 通過。"
        scene_log.memory_text = "玩家在 performance review 後得知 promo 通過，正式升上 Senior。"
    else:
        closing_text = (
            f"{manager_name} listens to your response, nods once, and for once does not immediately tab into the next meeting window. "
            'She nudges the promotion notice toward you and adds, "From here, stop being only the person who rescues things. Start being the person who sets the direction first."'
            "\n\nAfter the meeting, you return to your desk. Slack is still full of questions about bugs, timelines, and who is supposed to take the sudden request. "
            "The difference now is that the background noise contains one very concrete fact: you are a Senior engineer."
        )
        scene_log.eval_reason = "You cleared performance review and the promotion went through."
        scene_log.memory_text = "After performance review, the player learns that the promotion succeeded and officially becomes a Senior engineer."
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=closing_text))

    scene_log.state_delta = {}
    scene_log.eval_rating = "good"
    _set_eval_debug(scene_log, {"provider": "system", "model": "promo_scene", "source": "promo_scene"})

    session.round_in_scene += 1
    _set_current_options(session, [])
    _end_session(db, session, "promoted")
    db.commit()
    return {
        "text": closing_text,
        "generated_by": None,
        "options": [],
        "scene_ended": True,
        "round": session.round_in_scene,
        "game_ended": True,
        "end_reason": "promoted",
        "ending": _ending_payload_for_session(db, session, "promoted"),
    }


def _reorg_memory_text(metadata: dict, locale: str | None) -> str:
    changes = describe_reorg_changes(metadata, locale=locale)
    if not changes:
        return "玩家經歷了一次 reorg，組織關係被重設。" if _is_zh(locale) else "The player went through a reorg and their reporting relationships were reset."
    text = ("玩家經歷了一次 reorg：" if _is_zh(locale) else "The player went through a reorg: ") + ("；".join(changes) if _is_zh(locale) else "; ".join(changes))
    layoff = metadata.get("layoff") or {}
    if layoff.get("name"):
        replacement = layoff.get("replacement") or ("新人" if _is_zh(locale) else "a new hire")
        if _is_zh(locale):
            text += f"；{layoff['name']} 被裁，{replacement} 補上原本的位置。"
        else:
            text += f"; {layoff['name']} was laid off and {replacement} took the original slot."
    return text


def _handle_reorg_turn(
    session: GameSession,
    scene_log: SceneLog,
    body: TurnRequest,
    db: Session,
) -> dict:
    locale = _session_locale(session)
    options = _current_options(session)
    sanitized_message = _sanitize_player_text(body.message)
    player_text = _normalize_player_message_with_options(sanitized_message, options)
    db.add(Message(scene_log_id=scene_log.id, role="user", content=player_text))

    manager_name = session.characters["manager"]["name"]
    if _is_zh(locale):
        closing_text = (
            "你點下確認，HR portal 立刻把這件事標成 completed。"
            "這不是你的選擇，只是系統需要一個綠色勾勾。"
            f"\n\n新的會議邀請、文件 owner 和日曆上的 1:1 都開始改成 {manager_name}。"
            "下一段職場災難，會由新的 cast 跟你一起演。"
        )
        scene_log.eval_reason = "Reorg 系統事件，不做表現評分。"
    else:
        closing_text = (
            "You click confirm and the HR portal immediately marks the whole thing as completed. "
            "This is not your choice. The system just needed a green checkmark."
            f"\n\nNew meeting invites, document ownership, and the 1:1 on your calendar all start switching over to {manager_name}. "
            "The next workplace disaster will be performed by a new cast."
        )
        scene_log.eval_reason = "Reorg is a system event and is not performance-scored."
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=closing_text))

    metadata = (session.characters or {}).get("last_reorg") or {}
    scene_log.state_delta = {}
    scene_log.eval_rating = "neutral"
    _set_eval_debug(
        scene_log,
        {
            "provider": "system",
            "model": "reorg_scene",
            "source": "reorg_scene",
            "changes": metadata.get("changes", []),
            "layoff": metadata.get("layoff"),
        },
    )
    scene_log.memory_text = _reorg_memory_text(metadata, locale)

    session.state = _advance_progress_state(dict(session.state), "event", REORG_EVENT_ID)
    _sync_scene_history_from_logs(db, session)
    next_ref, pending_scenes = _choose_followup_scene(session, "event", REORG_EVENT_ID)

    session.round_in_scene += 1
    _set_current_options(session, [])
    _activate_next_scene(db, session, next_ref, pending_scenes)
    db.commit()
    return {
        "text": closing_text,
        "generated_by": None,
        "options": [],
        "scene_ended": True,
        "round": session.round_in_scene,
    }


def _handle_pip_turn(
    session: GameSession,
    scene_log: SceneLog,
    body: TurnRequest,
    db: Session,
) -> dict:
    current_scene = _current_scene_for_session(session)
    locale = _session_locale(session)
    bundle = _prompt_bundle_for_session(session)
    normalized_message = _sanitize_player_text(body.message, allow_empty=True) or _freeform_placeholder(locale)
    db.add(Message(scene_log_id=scene_log.id, role="user", content=normalized_message))
    db.flush()

    messages = _scene_messages(db, scene_log.id)
    memories = _recent_memories(db, session.id, limit=5)
    current_round = _prompt_round_for_turn(session.round_in_scene, session.scene_round_limit)
    transfer_requested_so_far = _transfer_requested(messages)
    scene_for_prompt = _pip_prompt_scene(
        current_scene["scene"],
        locale,
        session.round_in_scene,
        transfer_requested_so_far,
    )
    system_prompt = bundle.build_story_system_prompt(
        player_name=session.characters.get("player_name", default_player_name(locale)),
        manager=session.characters["manager"],
        buddy=session.characters["buddy"],
        team_members=session.characters.get("team_members", []),
        scene_kind=current_scene["kind"],
        scene=scene_for_prompt,
        current_round=current_round,
        rounds=session.scene_round_limit + 1,
        memories=memories,
    )
    ai_text, story_debug = story_response(system_prompt, messages)
    if _story_response_unavailable(ai_text, story_debug):
        db.rollback()
        raise HTTPException(status_code=503, detail=_ai_retry_later_detail(locale))
    _append_story_debug(
        scene_log,
        phase="turn",
        scene_kind=current_scene["kind"],
        scene_id=current_scene["id"],
        current_round=current_round,
        messages=messages,
        debug_payload=story_debug,
    )
    narration, next_options = _split_narration_and_options(ai_text, expect_options=False, locale=locale)
    leadin = _pip_round_leadin(locale, session.round_in_scene, transfer_requested_so_far)
    narration = f"{leadin}\n\n{narration.strip()}" if narration.strip() else leadin
    will_end_after_response = session.round_in_scene + 1 >= session.scene_round_limit
    if will_end_after_response:
        narration = _strip_trailing_question_ending(narration)
        narration = _ensure_scene_resolution(narration, locale, current_scene["kind"], current_scene["id"])
    else:
        narration = _ensure_question_ending(narration, locale)
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=narration))
    _set_current_options(session, [])

    session.round_in_scene += 1
    scene_ended = session.round_in_scene >= session.scene_round_limit
    if scene_ended:
        final_messages = _scene_messages(db, scene_log.id)
        final_transcript = _scene_transcript_text(final_messages)
        rating, reason, eval_debug = evaluate_rating(
            bundle.build_eval_prompt(current_scene["kind"], current_scene["scene"]),
            final_transcript,
        )
        delta = rating_to_delta(current_scene["scene"], rating)
        memory_text = summarize_memory(final_transcript, locale=locale)
        scene_log.state_delta = delta
        scene_log.eval_rating = rating
        scene_log.eval_reason = reason
        _set_eval_debug(scene_log, eval_debug)
        scene_log.memory_text = memory_text

        new_state = apply_state_delta(session.state, delta)
        transfer_requested = _transfer_requested(final_messages)
        pip_survived = _pip_survived(new_state, rating)
        transfer_success = _pip_transfer_success(new_state, rating, transfer_requested)
        session.state = new_state

        if transfer_success:
            old_manager_name = session.characters["manager"]["name"]
            manager, buddy, team_members = _pick_cast(locale)
            characters = dict(session.characters)
            characters["manager"] = manager
            characters["buddy"] = buddy
            characters["team_members"] = team_members
            session.characters = characters
            session.state = {**new_state, "pip_potential": 0, "perf_review_misses": 0, "rounds_since_promo": 0}
            _sync_scene_history_from_logs(db, session)
            next_ref = _draw_next_scene_for_session(session, "project")
            outcome_kind = "transfer_survive" if pip_survived else "transfer_escape"
            outcome_text = _pip_outcome_text(outcome_kind, old_manager_name, locale)
            db.add(Message(scene_log_id=scene_log.id, role="assistant", content=outcome_text))
            _activate_next_scene(db, session, next_ref, [])
            db.commit()
            return {
                "text": outcome_text,
                "generated_by": None,
                "options": [],
                "scene_ended": True,
                "round": session.round_in_scene,
            }

        if pip_survived:
            session.state = {**new_state, "pip_potential": 0, "perf_review_misses": 0, "rounds_since_promo": 0}
            _sync_scene_history_from_logs(db, session)
            next_ref = _draw_next_scene_for_session(session, "project")
            outcome_text = _pip_outcome_text("survive", session.characters["manager"]["name"], locale)
            db.add(Message(scene_log_id=scene_log.id, role="assistant", content=outcome_text))
            _activate_next_scene(db, session, next_ref, [])
            db.commit()
            return {
                "text": outcome_text,
                "generated_by": None,
                "options": [],
                "scene_ended": True,
                "round": session.round_in_scene,
            }

        firing_text = _pip_outcome_text("fired", session.characters["manager"]["name"], locale, transfer_requested)
        db.add(Message(scene_log_id=scene_log.id, role="assistant", content=firing_text))
        _end_session(db, session, "fired")
        db.commit()
        return {
            "text": firing_text,
            "generated_by": None,
            "options": [],
            "scene_ended": True,
            "round": session.round_in_scene,
            "game_ended": True,
            "end_reason": "fired",
            "ending": _ending_payload_for_session(db, session, "fired"),
        }

    db.commit()
    return {
        "text": narration,
        "generated_by": _scene_generated_by(scene_log),
        "options": [],
        "scene_ended": False,
        "round": session.round_in_scene,
    }


def _opening_text_for_scene(db: Session, scene_log_id: str) -> str:
    msg = db.execute(
        select(Message)
        .where(Message.scene_log_id == scene_log_id, Message.role == "assistant")
        .order_by(asc(Message.created_at), asc(Message.id))
        .limit(1)
    ).scalar_one_or_none()
    return msg.content if msg else ""


def _latest_eval_info(db: Session, session_id: str) -> dict | None:
    scene = db.execute(
        select(SceneLog)
        .where(SceneLog.session_id == session_id, SceneLog.eval_rating.is_not(None))
        .order_by(desc(SceneLog.created_at), desc(SceneLog.id))
        .limit(1)
    ).scalar_one_or_none()
    if scene is None:
        return None

    scene_kind = _scene_kind_from_ids(scene.project_id, scene.event_id)
    scene_id = scene.project_id if scene_kind == "project" else scene.event_id
    return {
        "scene_type": scene_kind,
        "scene_id": scene_id,
        "rating": scene.eval_rating,
        "reason": scene.eval_reason,
        "delta": scene.state_delta or {},
    }


def _settle_scene(session_id: str, finished_scene_log_id: str) -> None:
    db = SessionLocal()
    try:
        session = db.get(GameSession, session_id)
        if session is None or session.status != "active":
            return
        locale = _session_locale(session)
        bundle = _prompt_bundle_for_session(session)

        scene_log = db.get(SceneLog, finished_scene_log_id)
        if scene_log is None:
            session.settlement_status = "idle"
            db.commit()
            return

        scene_kind = _scene_kind_from_ids(scene_log.project_id, scene_log.event_id)
        scene_id = scene_log.project_id if scene_kind == "project" else scene_log.event_id
        scene = _resolve_scene(scene_kind, scene_id, locale)
        messages = _scene_messages(db, scene_log.id)
        transcript_text = _scene_transcript_text(messages)

        rating, reason, eval_debug = evaluate_rating(bundle.build_eval_prompt(scene_kind, scene), transcript_text)
        delta = _perf_review_delta(rating) if _is_perf_scene(scene_id) else rating_to_delta(scene, rating)
        memory_text = summarize_memory(transcript_text, locale=locale)

        scene_log.state_delta = delta
        scene_log.eval_rating = rating
        scene_log.eval_reason = reason
        _set_eval_debug(scene_log, eval_debug)
        scene_log.memory_text = memory_text
        if not (_is_perf_scene(scene_id) or _is_promo_scene(scene_id) or _is_pip_scene(scene_id) or _is_reorg_scene(scene_id)):
            achievements = _perf_achievements(scene) or [{"framings": {}}]
            achievement = achievements[_primary_perf_achievement_index(scene_log, achievements)]
            perf_config = _perf_review_config(scene)
            ai_artifact = {}
            if scene_kind == "project" or perf_config.get("eligible"):
                ai_artifact = generate_perf_artifact(
                    scene_title=str(scene["title"]),
                    scene_id=scene_id,
                    rating=rating,
                    memory_text=memory_text,
                    eval_reason=reason,
                    transcript_text=transcript_text,
                    locale=locale,
                )
            scene_log.perf_artifact = _build_perf_artifact(
                scene_kind,
                scene_id,
                scene,
                scene_log,
                achievement,
                locale,
                ai_artifact,
            )
        db.flush()

        session.state = _advance_progress_state(apply_state_delta(session.state, delta), scene_kind, scene_id)
        _sync_scene_history_from_logs(db, session)
        next_ref, pending_scenes = _choose_followup_scene(session, scene_kind, scene_id)
        _activate_next_scene(db, session, next_ref, pending_scenes)

        db.commit()
    except Exception:
        db.rollback()
        failed_session = db.get(GameSession, session_id)
        if failed_session is not None:
            failed_session.settlement_status = "idle"
            db.commit()
    finally:
        db.close()


@app.post("/sessions")
def create_session(
    request: Request,
    response: Response,
    body: CreateSessionRequest | None = None,
    db: Session = Depends(get_db),
):
    _consume_session_create_limit(request)
    locale = normalize_locale((body.locale if body else None) or locale_from_accept_language(request.headers.get("accept-language")))
    raw_name = (body.player_name if body else None) or ""
    player_name = _sanitize_player_text(raw_name, limit=MAX_PLAYER_NAME_LENGTH, allow_empty=True) or default_player_name(locale)
    browser_id = _browser_id_from_request(request)

    manager, buddy, team_members = _pick_cast(locale)
    state = dict(INITIAL_MID_STATE)

    first_scene_ref = {"kind": "project", "id": draw_project(state, locale=locale)["id"]}
    first_scene = _scene_config_from_ref(first_scene_ref, locale)

    game_session = GameSession(
        locale=locale,
        browser_id=browser_id,
        session_meta=_session_meta_from_request(request),
        state=state,
        characters={
            "player_name": player_name,
            "locale": locale,
            "manager": manager,
            "buddy": buddy,
            "team_members": team_members,
            "pending_scenes": [],
        },
        current_event_id=first_scene["event_id"],
        current_project_id=first_scene["project_id"],
        current_scene_log_id="",
        round_in_scene=0,
        scene_round_limit=first_scene["rounds"],
        settlement_status="idle",
    )
    _record_scene_history(game_session, first_scene_ref)
    db.add(game_session)
    db.flush()

    scene_log = SceneLog(
        session_id=game_session.id,
        event_id=first_scene["event_id"],
        project_id=first_scene["project_id"],
        state_snapshot=state,
        cast_snapshot=_scene_cast_snapshot(game_session),
    )
    db.add(scene_log)
    db.flush()

    game_session.current_scene_log_id = scene_log.id

    opening_narration, options, story_debug = _build_scene_opening(db, game_session, first_scene, [])
    if _story_response_unavailable(opening_narration, story_debug):
        db.rollback()
        raise HTTPException(status_code=503, detail=_ai_retry_later_detail(locale))
    _append_story_debug(
        scene_log,
        phase="opening",
        scene_kind=first_scene["kind"],
        scene_id=first_scene["project_id"] if first_scene["kind"] == "project" else first_scene["event_id"],
        current_round=1,
        messages=[{"role": "user", "content": _scene_start_marker(locale)}],
        debug_payload=story_debug,
    )
    _set_current_options(game_session, options)
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=opening_narration))
    db.commit()
    _set_session_cookie(response, game_session.id)

    return {
        "session_id": game_session.id,
        "text": opening_narration,
        "generated_by": _scene_generated_by(scene_log),
        "options": options,
        "start_level": "mid",
        "player_name": player_name,
        "locale": locale,
        "characters": game_session.characters,
        "scene_type": first_scene["kind"],
        "scene_id": first_scene["scene"]["id"],
        "project_id": first_scene["project_id"],
        "event_id": first_scene["event_id"],
        "max_rounds": first_scene["rounds"],
    }


@app.post("/dev/sessions/perf-review-fixture")
def dev_create_perf_review_fixture(
    request: Request,
    response: Response,
    body: DevPerfFixtureRequest | None = None,
    db: Session = Depends(get_db),
):
    if not _dev_tools_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    _consume_session_create_limit(request)
    locale = normalize_locale(body.locale if body else None)
    raw_name = (body.player_name if body else None) or ""
    player_name = _sanitize_player_text(raw_name, limit=MAX_PLAYER_NAME_LENGTH, allow_empty=True) or default_player_name(locale)
    browser_id = _browser_id_from_request(request)
    scenario = ((body.scenario if body else None) or "regular").strip().lower()
    if scenario not in {"regular", "promo", "pip"}:
        raise HTTPException(status_code=400, detail="Unknown perf review fixture scenario")
    manager, buddy, team_members = _pick_cast(locale)
    scenario_state = {
        "regular": {"tech": 5, "visibility": 5, "affinity": 5, "pip_potential": 1},
        "promo": {"tech": 7, "visibility": 6, "affinity": 5, "pip_potential": 1},
        "pip": {"tech": 4, "visibility": 4, "affinity": 3, "pip_potential": 8},
    }
    state = {**dict(INITIAL_MID_STATE), **scenario_state[scenario]}
    state["completed_cycles"] = PERF_TRIGGER_CYCLES
    state["rounds_since_promo"] = PERF_TRIGGER_CYCLES
    perf_scene_config = _perf_review_scene(locale)
    game_session = GameSession(
        locale=locale,
        browser_id=browser_id,
        session_meta=_session_meta_from_request(request),
        state=state,
        characters={
            "player_name": player_name,
            "locale": locale,
            "manager": manager,
            "buddy": buddy,
            "team_members": team_members,
            "pending_scenes": [],
        },
        current_event_id=PERF_REVIEW_ID,
        current_project_id=EMPTY_SCENE_ID,
        current_scene_log_id="",
        round_in_scene=0,
        scene_round_limit=perf_scene_config["rounds"],
        settlement_status="idle",
    )
    db.add(game_session)
    db.flush()

    project_fixtures = [
        {
            "project_id": "standard_engineering_project",
            "event_id": EMPTY_SCENE_ID,
            "rating": "good",
            "reason": "玩家在模糊需求下選擇低風險優化方向，成功在 Demo 前交付可展示成果。",
            "memory_text": "玩家選擇了專注改善現有功能，並找出一個風險較低的小功能模組進行優化。儘管時程緊迫，玩家仍在 Demo 上成功展示改動，並獲得 PM 與主管的認可。",
            "state_delta": {"tech": 1, "visibility": 1},
        },
        {
            "project_id": "cross_team_collab",
            "event_id": EMPTY_SCENE_ID,
            "rating": "good",
            "reason": "玩家主動定義資料合約邊界，有效對齊跨組目標並避免合作失焦。",
            "memory_text": "玩家擬定了一份 Project Chimera 的最小可行資料合約草稿，列出目前能穩定提供的資料欄位與 API 邊界，並獲得己方 PM David 肯定。",
            "state_delta": {"visibility": 1, "affinity": 1},
        },
        {
            "project_id": "system_design_rfc",
            "event_id": EMPTY_SCENE_ID,
            "rating": "neutral",
            "reason": "玩家有整理 RFC 取捨，但部分 reviewer 質疑仍未完全解開。",
            "memory_text": "玩家整理了交易資料即時性與完整性之間的架構取捨，提交 RFC 草稿後在 review 中接住部分質疑，但仍留下需要後續補強的風險。",
            "state_delta": {},
        },
    ]
    event_fixtures = [
        {
            "project_id": EMPTY_SCENE_ID,
            "event_id": "teammate_no_handoff",
            "rating": "good",
            "reason": "玩家快速補齊未交接任務脈絡，並把下一步對齊到可執行方向。",
            "memory_text": "玩家調查 Jira、日誌與程式碼後，發現資料異常與隔壁組上線時間吻合，並取得 Brian 同意，下一步將聯繫隔壁組 PM 確認資料流向。",
            "state_delta": {"affinity": 1, "visibility": 1},
        },
        {
            "project_id": EMPTY_SCENE_ID,
            "event_id": "deadline_compressed",
            "rating": "good",
            "reason": "玩家在壓縮時程下保住核心交付，並把延伸功能合理移到下一階段。",
            "memory_text": "面對執行長要求專案提前發布，玩家專注於核心功能開發，透過華麗詞藻包裝成果，最終趕工成功上線並獲得 PM 與同事肯定。",
            "state_delta": {"visibility": 1, "tech": 1},
        },
        {
            "project_id": EMPTY_SCENE_ID,
            "event_id": "teammate_no_handoff",
            "rating": "good",
            "reason": "玩家快速釐清多個任務的急迫性，避免把精力花在已經降級的活動頁面。",
            "memory_text": "玩家先向 Tina 確認活動頁面修正的優先級，得知急迫性已降低，接著把精力轉向 Kevin 的數據報表與 API 對接問題。",
            "state_delta": {"affinity": 1},
        },
    ]

    for fixture in random.sample(project_fixtures, k=2) + random.sample(event_fixtures, k=2):
        _create_scene_log_with_perf_artifact(db, game_session, **fixture)

    perf_scene = SceneLog(
        session_id=game_session.id,
        event_id=PERF_REVIEW_ID,
        project_id=EMPTY_SCENE_ID,
        state_snapshot=game_session.state,
        cast_snapshot=_scene_cast_snapshot(game_session),
    )
    db.add(perf_scene)
    db.flush()

    game_session.current_scene_log_id = perf_scene.id
    opening_narration, options = _build_perf_opening(db, game_session)
    _set_current_options(game_session, options)
    db.add(Message(scene_log_id=perf_scene.id, role="assistant", content=opening_narration))
    db.commit()
    _set_session_cookie(response, game_session.id)
    return {
        "session_id": game_session.id,
        "text": opening_narration,
        "generated_by": _scene_generated_by(perf_scene),
        "options": options,
        "start_level": "mid",
        "player_name": player_name,
        "characters": game_session.characters,
        "scene_type": "event",
        "scene_id": PERF_REVIEW_ID,
        "project_id": EMPTY_SCENE_ID,
        "event_id": PERF_REVIEW_ID,
        "max_rounds": perf_scene_config["rounds"],
        "locale": locale,
        "dev_scenario": scenario,
    }


@app.post("/sessions/{session_id}/turn")
def take_turn(
    session_id: str,
    request: Request,
    body: TurnRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    _require_session_cookie(request, session_id)
    _consume_turn_rate_limit(request, session_id)
    session = db.get(GameSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    if session.settlement_status in {"running", "ready"}:
        raise HTTPException(status_code=400, detail="Scene settlement in progress")
    if session.round_in_scene >= session.scene_round_limit:
        raise HTTPException(status_code=400, detail="Scene already ended")

    scene_log = db.get(SceneLog, session.current_scene_log_id)
    if scene_log is None:
        raise HTTPException(status_code=500, detail="Current scene missing")
    locale = _session_locale(session)
    options = _current_options(session)

    if body.message.strip() == "/end":
        db.add(Message(scene_log_id=scene_log.id, role="user", content="/end"))
        db.add(
            Message(
                scene_log_id=scene_log.id,
                role="assistant",
                content="遊戲已結束。" if _is_zh(locale) else "The game has ended.",
            )
        )
        _end_session(db, session, "quit")
        db.commit()
        message = "遊戲已結束。" if _is_zh(locale) else "The game has ended."
        return {
            "text": message,
            "generated_by": None,
            "options": [],
            "scene_ended": True,
            "round": session.round_in_scene,
            "game_ended": True,
            "end_reason": "quit",
            "ending": _ending_payload_for_session(db, session, "quit"),
        }

    if _current_quit_context(session):
        return _handle_quit_confirmation(session, scene_log, body, db)

    if _is_quit_intent(body.message):
        sanitized_message = _sanitize_player_text(body.message, allow_empty=True) or ("我要辭職" if _is_zh(locale) else "I want to quit")
        db.add(Message(scene_log_id=scene_log.id, role="user", content=sanitized_message))
        confirmation_text = _quit_confirmation_text(locale)
        confirm_options = _quit_confirmation_options(locale)
        db.add(Message(scene_log_id=scene_log.id, role="assistant", content=confirmation_text))
        _set_quit_context(
            session,
            {
                "resume_options": options,
            },
        )
        _set_current_options(session, confirm_options)
        db.commit()
        return {
            "text": confirmation_text,
            "generated_by": None,
            "options": confirm_options,
            "scene_ended": False,
            "round": session.round_in_scene,
        }

    current_scene = _current_scene_for_session(session)
    if _is_perf_scene(current_scene["id"]):
        return _handle_perf_turn(session, scene_log, body, background_tasks, db)
    if _is_promo_scene(current_scene["id"]):
        return _handle_promo_turn(session, scene_log, body, db)
    if _is_reorg_scene(current_scene["id"]):
        return _handle_reorg_turn(session, scene_log, body, db)
    if _is_pip_scene(current_scene["id"]):
        return _handle_pip_turn(session, scene_log, body, db)

    sanitized_message = _sanitize_player_text(body.message)
    normalized_message = _normalize_player_message_with_options(sanitized_message, options)
    db.add(Message(scene_log_id=scene_log.id, role="user", content=normalized_message))
    db.flush()

    messages = _scene_messages(db, scene_log.id)
    memories = _recent_memories(db, session.id, limit=5)
    current_round = _prompt_round_for_turn(session.round_in_scene, session.scene_round_limit)
    bundle = _prompt_bundle_for_session(session)
    system_prompt = bundle.build_story_system_prompt(
        player_name=session.characters.get("player_name", default_player_name(locale)),
        manager=session.characters["manager"],
        buddy=session.characters["buddy"],
        team_members=session.characters.get("team_members", []),
        scene_kind=current_scene["kind"],
        scene=current_scene["scene"],
        current_round=current_round,
        rounds=session.scene_round_limit + 1,
        memories=memories,
    )
    ai_text, story_debug = story_response(system_prompt, messages)
    if _story_response_unavailable(ai_text, story_debug):
        db.rollback()
        raise HTTPException(status_code=503, detail=_ai_retry_later_detail(locale))
    _append_story_debug(
        scene_log,
        phase="turn",
        scene_kind=current_scene["kind"],
        scene_id=current_scene["id"],
        current_round=current_round,
        messages=messages,
        debug_payload=story_debug,
    )
    is_conversational = current_scene["scene"].get("conversational", False)
    show_options = _should_show_options(current_scene["kind"], current_round, is_conversational)
    narration, next_options = _split_narration_and_options(ai_text, expect_options=show_options, locale=locale)
    if show_options and current_scene["kind"] == "project":
        next_options = _ensure_project_options(
            current_scene["id"],
            current_round,
            next_options,
            narration,
            normalized_message,
            locale=locale,
        )
    will_end_after_response = session.round_in_scene + 1 >= session.scene_round_limit
    if will_end_after_response:
        narration = _strip_trailing_question_ending(narration)
        narration = _ensure_scene_resolution(narration, locale, current_scene["kind"], current_scene["id"])
    elif _should_force_question(not will_end_after_response, show_options):
        narration = _ensure_question_ending(narration, locale)
    _set_current_options(session, next_options)
    db.add(Message(scene_log_id=scene_log.id, role="assistant", content=narration))

    session.round_in_scene += 1
    scene_ended = session.round_in_scene >= session.scene_round_limit
    if scene_ended:
        session.settlement_status = "running"
        background_tasks.add_task(_settle_scene, session.id, scene_log.id)

    db.commit()
    return {
        "text": narration,
        "generated_by": _scene_generated_by(scene_log),
        "options": [] if scene_ended else next_options,
        "scene_ended": scene_ended,
        "round": session.round_in_scene,
    }


@app.get("/sessions/{session_id}/next-scene")
def next_scene(session_id: str, request: Request, db: Session = Depends(get_db)):
    _require_session_cookie(request, session_id)
    session = db.get(GameSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.settlement_status != "ready":
        return {"ready": False}

    opening_text = _opening_text_for_scene(db, session.current_scene_log_id)
    current_scene = _current_scene_for_session(session)
    scene_log = db.get(SceneLog, session.current_scene_log_id)
    if scene_log is not None:
        story_debug_json = scene_log.story_debug_json if isinstance(scene_log.story_debug_json, dict) else {}
        calls = list(story_debug_json.get("calls") or [])
        if calls:
            last_call = calls[-1] if isinstance(calls[-1], dict) else {}
            if str(last_call.get("phase") or "").strip() == "opening" and _story_debug_indicates_unavailable(last_call.get("debug")):
                raise HTTPException(status_code=503, detail=_ai_retry_later_detail(_session_locale(session)))
    session.settlement_status = "idle"
    db.commit()
    return {
        "ready": True,
        "text": opening_text,
        "generated_by": _scene_generated_by(scene_log),
        "options": _current_options(session),
        "scene_type": current_scene["kind"],
        "scene_id": current_scene["id"],
        "event_id": session.current_event_id,
        "project_id": session.current_project_id,
    }


@app.get("/sessions/{session_id}")
def get_session_state(session_id: str, request: Request, db: Session = Depends(get_db)):
    _require_session_cookie(request, session_id)
    session = db.get(GameSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    opening_text = _opening_text_for_scene(db, session.current_scene_log_id)
    current_scene = _current_scene_for_session(session)
    latest_eval = _latest_eval_info(db, session.id)
    scene_log = db.get(SceneLog, session.current_scene_log_id)
    return {
        "session_id": session.id,
        "locale": _session_locale(session),
        "state": session.state,
        "characters": session.characters,
        "current_scene_type": current_scene["kind"],
        "current_scene_id": current_scene["id"],
        "current_event_id": session.current_event_id,
        "current_project_id": session.current_project_id,
        "current_opening_text": opening_text,
        "current_generated_by": _scene_generated_by(scene_log),
        "current_options": _current_options(session),
        "status": session.status,
        "end_reason": session.end_reason,
        "ending": _ending_payload_for_session(db, session) if session.status == "ended" else None,
        "round": session.round_in_scene,
        "max_rounds": session.scene_round_limit,
        "latest_eval": latest_eval,
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "ok": True,
        "database_ok": True,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
