import requests

from .base import Platform, PostError

GRAPH = "https://graph.facebook.com/v21.0"


class Facebook(Platform):
    name = "facebook"

    def is_configured(self) -> bool:
        return bool(
            self.creds.facebook_page_id and self.creds.facebook_page_access_token
        )

    def publish(self, text: str) -> str:
        resp = requests.post(
            f"{GRAPH}/{self.creds.facebook_page_id}/feed",
            data={
                "message": text,
                "access_token": self.creds.facebook_page_access_token,
            },
            timeout=30,
        )
        data = resp.json()
        if "error" in data:
            raise PostError(f"Facebook API error: {data['error'].get('message')}")
        return data.get("id", "")
