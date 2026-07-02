"""Track published posts so topics and templates don't repeat back-to-back."""

import json
from datetime import datetime, timezone

from .config import HISTORY_FILE

MAX_ENTRIES = 200


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def recent_topics(limit: int = 5) -> list[str]:
    return [entry["topic"] for entry in load_history()[-limit:] if entry.get("topic")]


def post_count() -> int:
    return len(load_history())


def record_post(topic: str, results: dict[str, str]) -> None:
    history = load_history()
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "topic": topic,
            "results": results,
        }
    )
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history[-MAX_ENTRIES:], indent=2), encoding="utf-8"
    )
