"""Facebook Page publisher (Graph API).

Posts to a Facebook Page using a Page id and a long-lived Page access token.
Supports plain text, photos (from a public URL) and videos (from a public
URL), so the scheduler can mirror every Instagram post onto the Page.

Facebook has no first-class "story" via a simple URL call, so Instagram
stories are cross-posted as normal Page photo/video posts -- the content still
appears on the Page. Feed images post as photos, feed videos (Instagram Reels)
post as Page videos.
"""

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
        """Text-only status update on the Page feed."""
        return self._post(
            f"/{self.creds.facebook_page_id}/feed", {"message": text}
        )

    def publish_media(
        self, caption: str, media_url: str, post_type: str = "feed", is_video: bool = False
    ) -> str:
        """Mirror an Instagram post onto the Page.

        Signature matches Instagram.publish_media so the queue can call either
        publisher the same way. post_type is accepted for symmetry but Facebook
        posts everything to the Page (there is no simple story-by-URL call).
        """
        if is_video:
            # Page video from a public URL; Facebook processes it server-side.
            return self._post(
                f"/{self.creds.facebook_page_id}/videos",
                {"file_url": media_url, "description": caption or ""},
                id_key="id",
            )
        return self._post(
            f"/{self.creds.facebook_page_id}/photos",
            {"url": media_url, "caption": caption or ""},
            id_key="post_id",
        )

    def _post(self, path: str, extra: dict, id_key: str = "id") -> str:
        payload = {"access_token": self.creds.facebook_page_access_token, **extra}
        resp = requests.post(f"{GRAPH}{path}", data=payload, timeout=60)
        try:
            data = resp.json()
        except ValueError:
            raise PostError(f"Facebook API returned non-JSON (HTTP {resp.status_code})")
        if "error" in data:
            raise PostError(f"Facebook API error: {data['error'].get('message')}")
        # photos return {id, post_id}; videos/feed return {id}. Prefer post_id.
        return data.get(id_key) or data.get("id", "")
