import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable regardless of how pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def ig_env(monkeypatch):
    """Instagram credentials in the environment (values are fake)."""
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "12345")
    monkeypatch.delenv("INSTAGRAM_APP_SECRET", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def business_config():
    return {
        "business": {"name": "Test Biz"},
        "hashtags": ["#one", "#two"],
        "template_posts": ["Template caption A", "Template caption B"],
        "topics": ["topic x", "topic y"],
        "image_urls": ["https://example.com/a.jpg"],
    }
