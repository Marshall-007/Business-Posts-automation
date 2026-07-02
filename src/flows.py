"""Named posting presets ("flows") managed by the dashboard.

A flow is a saved configuration for a post:
    id         unique slug
    name       human-readable label
    platforms  list of platform names, or [] for all configured
    caption    fixed caption text, or "" to auto-generate
    image_url  Instagram image override, or "" to use config.yaml rotation
"""

import json
from pathlib import Path

FLOWS_FILE = Path(__file__).resolve().parent.parent / "data" / "flows.json"


def load_flows() -> list[dict]:
    if not FLOWS_FILE.exists():
        return []
    try:
        return json.loads(FLOWS_FILE.read_text(encoding="utf-8")).get("flows", [])
    except (json.JSONDecodeError, OSError):
        return []


def get_flow(flow_id: str) -> dict | None:
    for flow in load_flows():
        if flow.get("id") == flow_id:
            return flow
    return None
