import copy
import os
import random

from prompt_registry import get_prompt_bundle, normalize_locale


REORG_EVENT_ID = "reorg_cycle"
DEFAULT_REORG_PROBABILITY = 0.15
REORG_LAYOFF_PROBABILITY = 0.2
REORG_COOLDOWN_EVENTS = 2
REORG_COOLDOWN_PROBABILITY = 0.05
SPECIAL_EVENTS = {
    "zh-Hant": {
        REORG_EVENT_ID: {
            "id": REORG_EVENT_ID,
            "title": "Reorg",
            "story": "週五下午四點半，全公司收到 reorg 公告。你被丟進一個新的 org chart，舊匯報線和同組名單瞬間作廢。",
            "rounds": 1,
            "conversational": True,
            "rubric": {
                "good": "這是系統事件，不做表現評分。",
                "neutral": "這是系統事件，不做表現評分。",
                "bad": "這是系統事件，不做表現評分。",
            },
            "affects": {},
        }
    },
    "en": {
        REORG_EVENT_ID: {
            "id": REORG_EVENT_ID,
            "title": "Reorg",
            "story": "Friday, 4:30 PM. A reorg announcement hits the entire company. You are dropped into a new org chart and your old reporting line and team list become obsolete instantly.",
            "rounds": 1,
            "conversational": True,
            "rubric": {
                "good": "This is a system event and is not performance-scored.",
                "neutral": "This is a system event and is not performance-scored.",
                "bad": "This is a system event and is not performance-scored.",
            },
            "affects": {},
        }
    },
}


def _bundle(locale: str | None):
    return get_prompt_bundle(locale)


def _projects(locale: str | None) -> list[dict]:
    return list(_bundle(locale).PROJECTS)


def _events(locale: str | None) -> list[dict]:
    return list(_bundle(locale).EVENTS)


def _managers(locale: str | None) -> list[dict]:
    return list(_bundle(locale).MANAGERS)


def _team_members(locale: str | None) -> list[dict]:
    return list(_bundle(locale).TEAM_MEMBERS)


def _name_pool(locale: str | None) -> list[str]:
    return list(_bundle(locale).NAME_POOL)


def _is_unlocked(item: dict, state: dict) -> bool:
    unlock = item.get("unlock", {})
    if "tech_min" in unlock and state.get("tech", 0) < unlock["tech_min"]:
        return False
    if "visibility_min" in unlock and state.get("visibility", 0) < unlock["visibility_min"]:
        return False
    return True


def _weighted_draw(
    items: list[dict],
    state: dict,
    rng: random.Random | None = None,
    exclude_ids: set[str] | None = None,
) -> dict:
    picker = rng or random
    blocked = exclude_ids or set()
    eligible = [item for item in items if _is_unlocked(item, state) and item["id"] not in blocked]
    if not eligible and blocked:
        eligible = [item for item in items if _is_unlocked(item, state)]
    if not eligible:
        eligible = items
    weights = [max(1, int(item.get("weight", 1))) for item in eligible]
    return picker.choices(eligible, weights=weights, k=1)[0]


def draw_project(
    state: dict,
    rng: random.Random | None = None,
    exclude_ids: set[str] | None = None,
    *,
    locale: str | None = None,
) -> dict:
    return _weighted_draw(_projects(locale), state, rng=rng, exclude_ids=exclude_ids)


def draw_event(
    state: dict,
    rng: random.Random | None = None,
    exclude_ids: set[str] | None = None,
    *,
    locale: str | None = None,
) -> dict:
    return _weighted_draw(
        [event for event in _events(locale) if event["id"] not in {"perf_review_cycle", "reorg", REORG_EVENT_ID}],
        state,
        rng=rng,
        exclude_ids=exclude_ids,
    )


def reorg_probability() -> float:
    raw = os.getenv("REORG_PROBABILITY", str(DEFAULT_REORG_PROBABILITY)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = DEFAULT_REORG_PROBABILITY
    return max(0.0, min(1.0, value))


def should_trigger_reorg(state: dict, rng: random.Random | None = None) -> bool:
    if int(state.get("completed_cycles", 0)) < 1:
        return False
    recent_event_ids = [str(value) for value in (state.get("recent_event_ids") or []) if str(value)]
    if recent_event_ids and recent_event_ids[-1] == REORG_EVENT_ID:
        return False
    cooldown_remaining = int(state.get("reorg_cooldown_events_remaining", 0) or 0)
    picker = rng or random
    threshold = REORG_COOLDOWN_PROBABILITY if cooldown_remaining > 0 else reorg_probability()
    return picker.random() < threshold


def draw_scene_cycle(
    state: dict,
    rng: random.Random | None = None,
    exclude_project_ids: set[str] | None = None,
    exclude_event_ids: set[str] | None = None,
    *,
    locale: str | None = None,
) -> list[dict]:
    project = draw_project(state, rng=rng, exclude_ids=exclude_project_ids, locale=locale)
    event = draw_event(state, rng=rng, exclude_ids=exclude_event_ids, locale=locale)
    if should_trigger_reorg(state, rng=rng):
        event = get_special_event(REORG_EVENT_ID, locale=locale)
    return [
        {"kind": "project", "id": project["id"]},
        {"kind": "event", "id": event["id"]},
    ]


def is_special_event(event_id: str) -> bool:
    return any(event_id in locale_events for locale_events in SPECIAL_EVENTS.values())


def get_special_event(event_id: str, *, locale: str | None = None) -> dict:
    normalized = normalize_locale(locale)
    try:
        return SPECIAL_EVENTS[normalized][event_id]
    except KeyError as exc:
        raise KeyError(f"Unknown special_event_id: {event_id}") from exc


def _choose_name(excluded_names: set[str], rng: random.Random | None = None) -> str:
    picker = rng or random
    candidates = [name for name in _name_pool("en") if name not in excluded_names]
    if candidates:
        return picker.choice(candidates)
    suffix = 1
    while f"New Hire {suffix}" in excluded_names:
        suffix += 1
    return f"New Hire {suffix}"


def _replacement_from_pool(
    current: dict,
    pool: list[dict],
    excluded_names: set[str],
    rng: random.Random | None = None,
) -> dict:
    picker = rng or random
    candidates = [item for item in pool if item["id"] != current["id"]]
    if not candidates:
        candidates = pool
    picked = copy.deepcopy(picker.choice(candidates))
    return {
        "id": picked["id"],
        "name": _choose_name(excluded_names, rng=picker),
        "display_desc": picked["display_desc"],
        "ai_personality_desc": picked["ai_personality_desc"],
    }


def _changed_entry(role: str, old: dict, new: dict, slot: int | None = None) -> dict:
    entry = {"role": role, "old": old, "new": new}
    if slot is not None:
        entry["slot"] = slot
    return entry


def apply_reorg_cast_swap(characters: dict, rng: random.Random | None = None) -> tuple[dict, dict]:
    picker = rng or random
    updated = copy.deepcopy(characters)
    locale = normalize_locale(updated.get("locale"))
    laid_off_names = {str(name).strip() for name in updated.get("laid_off_names", []) if str(name).strip()}
    excluded_names = {
        str(updated.get("manager", {}).get("name", "")).strip(),
        str(updated.get("buddy", {}).get("name", "")).strip(),
        *[str(member.get("name", "")).strip() for member in updated.get("team_members", [])],
        *laid_off_names,
    }
    excluded_names.discard("")
    changes: list[dict] = []

    if picker.random() < 0.5:
        old_manager = copy.deepcopy(updated["manager"])
        updated["manager"] = _replacement_from_pool(old_manager, _managers(locale), excluded_names, rng=picker)
        excluded_names.add(updated["manager"]["name"])
        changes.append(_changed_entry("manager", old_manager, copy.deepcopy(updated["manager"])))

    team_members = list(updated.get("team_members", []))
    for index, member in enumerate(team_members):
        if picker.random() >= 0.3:
            continue
        old_member = copy.deepcopy(member)
        team_members[index] = _replacement_from_pool(old_member, _team_members(locale), excluded_names, rng=picker)
        excluded_names.add(team_members[index]["name"])
        changes.append(_changed_entry("team_member", old_member, copy.deepcopy(team_members[index]), slot=index))
    updated["team_members"] = team_members

    if not changes:
        replaceable_roles: list[tuple[str, int | None]] = [("manager", None)]
        replaceable_roles.extend(("team_member", index) for index, _ in enumerate(team_members))
        forced_role, slot = picker.choice(replaceable_roles)
        if forced_role == "manager":
            old_manager = copy.deepcopy(updated["manager"])
            updated["manager"] = _replacement_from_pool(old_manager, _managers(locale), excluded_names, rng=picker)
            changes.append(_changed_entry("manager", old_manager, copy.deepcopy(updated["manager"])))
        else:
            old_member = copy.deepcopy(team_members[slot])
            team_members[slot] = _replacement_from_pool(old_member, _team_members(locale), excluded_names, rng=picker)
            updated["team_members"] = team_members
            changes.append(_changed_entry("team_member", old_member, copy.deepcopy(team_members[slot]), slot=slot))

    raw_reorg_count = updated.get("reorg_count")
    try:
        reorg_count = int(raw_reorg_count) if raw_reorg_count is not None else (1 if updated.get("last_reorg") else 0)
    except (TypeError, ValueError):
        reorg_count = 0
    layoff_change = None
    if reorg_count > 0 and changes and picker.random() < REORG_LAYOFF_PROBABILITY:
        layoff_change = picker.choice(changes)
        layoff_change["laid_off"] = True
        old_name = str((layoff_change.get("old") or {}).get("name", "")).strip()
        if old_name:
            laid_off_names.add(old_name)
    metadata = {"changes": changes, "reorg_count": reorg_count + 1}
    if layoff_change:
        metadata["layoff"] = {
            "role": layoff_change.get("role"),
            "name": (layoff_change.get("old") or {}).get("name"),
            "replacement": (layoff_change.get("new") or {}).get("name"),
        }
    updated["reorg_count"] = reorg_count + 1
    updated["laid_off_names"] = sorted(laid_off_names)
    updated["last_reorg"] = metadata
    return updated, metadata


def describe_reorg_changes(metadata: dict, *, locale: str | None = None) -> list[str]:
    zh = normalize_locale(locale) == "zh-Hant"
    lines: list[str] = []
    for change in metadata.get("changes", []):
        old = change.get("old", {})
        new = change.get("new", {})
        if zh:
            layoff_suffix = "（被裁，替補人選已經出現在 org chart 上）" if change.get("laid_off") else ""
            old_manager = "舊主管"
            new_manager = "新主管"
            old_member = "舊同事"
            new_member = "新同事"
        else:
            layoff_suffix = " (laid off; the replacement is already on the org chart)" if change.get("laid_off") else ""
            old_manager = "previous manager"
            new_manager = "new manager"
            old_member = "previous teammate"
            new_member = "new teammate"
        if change.get("role") == "manager":
            lines.append(f"Manager: {old.get('name', old_manager)} -> {new.get('name', new_manager)}{layoff_suffix}")
        else:
            lines.append(f"Team member: {old.get('name', old_member)} -> {new.get('name', new_member)}{layoff_suffix}")
    return lines


def get_project(project_id: str, *, locale: str | None = None) -> dict:
    for project in _projects(locale):
        if project["id"] == project_id:
            return project
    raise KeyError(f"Unknown project_id: {project_id}")


def get_event(event_id: str, *, locale: str | None = None) -> dict:
    if is_special_event(event_id):
        return get_special_event(event_id, locale=locale)
    for event in _events(locale):
        if event["id"] == event_id:
            return event
    raise KeyError(f"Unknown event_id: {event_id}")
