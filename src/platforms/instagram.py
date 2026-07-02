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
        """Default scheduled post: publish an image from config.yaml to the feed."""
        images = self.business_config.get("image_urls") or []
        if not images:
            raise PostError(
                "Instagram requires media; add public URLs to image_urls in config.yaml"
            )
        image_url = images[history.post_count() % len(images)]
        return self.publish_media(text, image_url, "feed", False)

    def publish_media(
        self, caption: str, media_url: str, post_type: str = "feed", is_video: bool = False
    ) -> str:
        """Publish media to Instagram.

        post_type: "feed" or "story". A video posted to the feed becomes a Reel.
        is_video: True for MP4/MOV, False for images.
        Captions apply to feed posts and Reels; Stories ignore the caption.
        """
        user_id = self.creds.instagram_user_id
        token = self._refresh_token()
        post_type = (post_type or "feed").lower()

        # Step 1: build the container parameters for the kind of post.
        params = {"access_token": token}
        if post_type == "story":
            params["media_type"] = "STORIES"
            params["video_url" if is_video else "image_url"] = media_url
        elif is_video:  # video on the feed = Reel
            params["media_type"] = "REELS"
            params["video_url"] = media_url
            params["share_to_feed"] = "true"
            params["caption"] = caption
        else:  # feed image
            params["image_url"] = media_url
            params["caption"] = caption

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
