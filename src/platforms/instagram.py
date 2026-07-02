import time

import requests

from .. import history
from .base import Platform, PostError

GRAPH = "https://graph.facebook.com/v21.0"


class Instagram(Platform):
    name = "instagram"

    def is_configured(self) -> bool:
        return bool(
            self.creds.instagram_business_account_id
            and self.creds.facebook_page_access_token
            and self.business_config.get("image_urls")
        )

    def publish(self, text: str) -> str:
        images = self.business_config.get("image_urls") or []
        if not images:
            raise PostError(
                "Instagram requires an image; add public URLs to image_urls in config.yaml"
            )
        image_url = images[history.post_count() % len(images)]
        account = self.creds.instagram_business_account_id
        token = self.creds.facebook_page_access_token

        # Step 1: create a media container.
        resp = requests.post(
            f"{GRAPH}/{account}/media",
            data={"image_url": image_url, "caption": text, "access_token": token},
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            raise PostError(f"Instagram container error: {data['error'].get('message')}")
        container_id = data["id"]

        # Step 2: wait for processing, then publish.
        for _ in range(10):
            status = requests.get(
                f"{GRAPH}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=30,
            ).json()
            if status.get("status_code") == "FINISHED":
                break
            if status.get("status_code") == "ERROR":
                raise PostError("Instagram media processing failed")
            time.sleep(3)

        resp = requests.post(
            f"{GRAPH}/{account}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=60,
        )
        data = resp.json()
        if "error" in data:
            raise PostError(f"Instagram publish error: {data['error'].get('message')}")
        return data.get("id", "")
