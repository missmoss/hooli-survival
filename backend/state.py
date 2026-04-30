INITIAL_MID_STATE = {
    "tech": 4,
    "visibility": 4,
    "affinity": 4,
    "pip_potential": 0,
    "perf_review_misses": 0,
    "rounds_since_promo": 0,
    "completed_cycles": 0,
}


TRACKED_KEYS = ("tech", "visibility", "affinity", "pip_potential")


def apply_state_delta(state: dict, delta: dict) -> dict:
    updated = dict(state)
    for key in TRACKED_KEYS:
        updated[key] = int(updated.get(key, 0) + delta.get(key, 0))
    return updated


def rating_to_delta(scene: dict, rating: str) -> dict:
    if rating == "neutral":
        return {}

    source = "good" if rating == "good" else "bad"
    result: dict[str, int] = {}
    for key, value in scene.get("affects", {}).get(source, {}).items():
        result[key] = int(result.get(key, 0) + value)
    return result
