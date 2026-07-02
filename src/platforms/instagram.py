"""Instagram publisher using the Instagram API with Instagram Login.

Uses graph.instagram.com and an "IGAA…" access token plus the Instagram user id
(from GET https://graph.instagram.com/me). This flow does not require a Facebook
Page. Every Instagram post must include a publicly reachable image URL, so
image_urls must be populated in config.yaml.
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
        """Best-effort refresh of a long-lived token so its 60-day clock resets
        each run. Returns a refreshed token if successful, else the original.
        Short-lived (1-hour) tokens cannot be refreshed this way; the original
        is returned and used as-is."""
        token = self.creds.instagram_access_token
        try:
            resp = requests.get(
                "https://graph.instagram.com/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": token},
                timeout=30,
            )
            data = resp.json()
            return data.get("access_token", token)
        except Exception:
            return token

    def publish(self, text: str) -> str:
        images = self.business_config.get("image_urls") or []
        if not images:
            raise PostError(
                "Instagram requires an image; add public URLs to image_urls in config.yaml"
            )
        image_url = images[history.post_count() % len(images)]
        user_id = self.creds.instagram_user_id
        token = self._refresh_token()

        # Step 1: create a media container.
        resp = requests.post(
            f"{GRAPH}/{user_id}/media",
            data={"image_url": image_url, "caption": text, "access_token": token},
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            raise PostError(f"Instagram container error: {data['error'].get('message')}")
        container_id = data["id"]

        # Step 2: wait for the container to finish processing.
        for _ in range(15):
            status = requests.get(
                f"{GRAPH}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=30,
            ).json()
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise PostError("Instagram media processing failed (bad image URL?)")
            time.sleep(3)
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
