"""Instagram publisher using the Instagram API with Instagram Login.

Uses graph.instagram.com and an "IGAA..." access token plus the Instagram user id.
Supports both images (feed) and videos (Reels). Every post needs a publicly
reachable media URL, so image_urls must be populated in config.yaml for the
default scheduled post; the queue passes per-item media URLs directly.
"""

import time

import requests

from .. import history
from .base import Platform, PostError

GRAPH = "https://graph.instagram.com/v21.0"


class Instagram(Platform):
    name = "instagram"

    def is_configured(self) -> bool:
        return bool(
            self.creds.instagram_access_token
            and self.creds.instagram_user_id
            and self.business_config.get("image_urls")
        )

    def _refresh_token(self) -> str:
        """Best-effort upgrade/refresh of the access token (never raises)."""
        token = self.creds.instagram_access_token

        if self.creds.instagram_app_secret:
            try:
                resp = requests.get(
                    "https://graph.instagram.com/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": self.creds.instagram_app_secret,
                        "access_token": token,
                    },
                    timeout=30,
                )
                exchanged = resp.json().get("access_token")
                if exchanged:
                    return exchanged
            except Exception:
                pass

        try:
            resp = requests.get(
                "https://graph.instagram.com/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": token},
                timeout=30,
            )
            return resp.json().get("access_token", token)
        except Exception:
            return token

    def publish(self, text: str) -> str:
        """Default scheduled post: publish an image from config.yaml."""
        images = self.business_config.get("image_urls") or []
        if not images:
            raise PostError(
                "Instagram requires media; add public URLs to image_urls in config.yaml"
            )
        image_url = images[history.post_count() % len(images)]
        return self.publish_media(text, image_url, "IMAGE")

    def publish_media(self, caption: str, media_url: str, media_type: str = "IMAGE") -> str:
        """Publish a single image (media_type "IMAGE") or video Reel ("REELS")."""
        user_id = self.creds.instagram_user_id
        token = self._refresh_token()
        is_video = media_type.upper() == "REELS"

        # Step 1: create the media container.
        params = {"caption": caption, "access_token": token}
        if is_video:
            params["media_type"] = "REELS"
            params["video_url"] = media_url
            params["share_to_feed"] = "true"
        else:
            params["image_url"] = media_url

        resp = requests.post(f"{GRAPH}/{user_id}/media", data=params, timeout=60)
        data = resp.json()
        if "error" in data:
            raise PostError(f"Instagram container error: {data['error'].get('message')}")
        container_id = data["id"]

        # Step 2: wait for processing (videos take much longer than images).
        attempts = 90 if is_video else 15
        for _ in range(attempts):
            status = requests.get(
                f"{GRAPH}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=30,
            ).json()
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise PostError("Instagram media processing failed (bad URL or format?)")
            time.sleep(4)
        else:
            raise PostError("Instagram media did not finish processing in time")

        # Step 3: publish the container.
        resp = requests.post(
            f"{GRAPH}/{user_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            raise PostError(f"Instagram publish error: {data['error'].get('message')}")
        return data.get("id", "")
