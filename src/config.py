"""Load environment credentials and the business profile from config.yaml."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
HISTORY_FILE = PROJECT_ROOT / "data" / "history.json"

load_dotenv(PROJECT_ROOT / ".env")


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_business_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Credentials:
    """Reads platform credentials from the environment. A platform is
    considered configured when all of its required variables are set."""

    def __init__(self):
        self.anthropic_api_key = env("ANTHROPIC_API_KEY")

        self.telegram_bot_token = env("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = env("TELEGRAM_CHAT_ID")

        self.facebook_page_id = env("FACEBOOK_PAGE_ID")
        self.facebook_page_access_token = env("FACEBOOK_PAGE_ACCESS_TOKEN")

        # Instagram Login flow (graph.instagram.com): token starts with "IGAA".
        self.instagram_access_token = env("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_user_id = env("INSTAGRAM_USER_ID")
        # Optional: lets a short-lived (1h) token be exchanged for a
        # long-lived (60-day) one at post time.
        self.instagram_app_secret = env("INSTAGRAM_APP_SECRET")

        # TikTok Content Posting API. The refresh token (valid ~1 year) is the
        # durable secret; a fresh 24h access token is minted from it each run.
        self.tiktok_client_key = env("TIKTOK_CLIENT_KEY")
        self.tiktok_client_secret = env("TIKTOK_CLIENT_SECRET")
        self.tiktok_refresh_token = env("TIKTOK_REFRESH_TOKEN")
        self.tiktok_access_token = env("TIKTOK_ACCESS_TOKEN")
        # SELF_ONLY until the app passes TikTok review; then PUBLIC_TO_EVERYONE.
        self.tiktok_privacy_level = env("TIKTOK_PRIVACY_LEVEL") or "SELF_ONLY"

        self.linkedin_access_token = env("LINKEDIN_ACCESS_TOKEN")
        self.linkedin_author_urn = env("LINKEDIN_AUTHOR_URN")

        self.twitter_api_key = env("TWITTER_API_KEY")
        self.twitter_api_secret = env("TWITTER_API_SECRET")
        self.twitter_access_token = env("TWITTER_ACCESS_TOKEN")
        self.twitter_access_token_secret = env("TWITTER_ACCESS_TOKEN_SECRET")
