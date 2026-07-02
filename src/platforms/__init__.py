from ..config import Credentials
from .base import Platform, PostError
from .facebook import Facebook
from .instagram import Instagram
from .linkedin import LinkedIn
from .telegram import Telegram
from .twitter import Twitter

ALL_PLATFORMS = [Telegram, Facebook, Instagram, LinkedIn, Twitter]


def build_platforms(creds: Credentials, business_config: dict) -> list[Platform]:
    return [cls(creds, business_config) for cls in ALL_PLATFORMS]
