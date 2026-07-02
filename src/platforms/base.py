"""Common interface for platform publishers."""

from abc import ABC, abstractmethod

from ..config import Credentials


class PostError(Exception):
    """Raised when publishing to a platform fails."""


class Platform(ABC):
    name: str

    def __init__(self, creds: Credentials, business_config: dict):
        self.creds = creds
        self.business_config = business_config

    @abstractmethod
    def is_configured(self) -> bool:
        """True when all required credentials are present."""

    @abstractmethod
    def publish(self, text: str) -> str:
        """Publish the post. Returns an identifier/URL of the created post.
        Raises PostError on failure."""
