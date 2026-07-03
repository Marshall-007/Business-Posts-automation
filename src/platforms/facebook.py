"""Facebook Page publisher (Graph API).

Posts to a Facebook Page using a Page id and a long-lived Page access token.
Supports plain text, photos, videos, and native Page Stories (both photo and
video), so every Instagram post -- feed, Reel, or story -- can be mirrored to
the Page in the matching format.
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
        publisher the same way. post_type "story" posts to the Page's Stories;
        "feed" posts to the Page timeline (photos or videos).
        """
        post_type = (post_type or "feed").lower()
        if post_type == "story":
            return self._publish_story(media_url, is_video)
        if is_video:
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

    # ---- Stories -----------------------------------------------------------

    def _publish_story(self, media_url: str, is_video: bool) -> str:
        """Publish to the Page's Stories ring.

        Photos: upload as unpublished, then POST to /photo_stories.
        Videos: three-step resumable upload -- start, upload from hosted URL,
        finish with video_state=PUBLISHED. All powered by the same
        pages_manage_posts scope the Page token already carries.
        """
        if is_video:
            return self._publish_video_story(media_url)
        return self._publish_photo_story(media_url)

    def _publish_photo_story(self, media_url: str) -> str:
        page_id = self.creds.facebook_page_id
        # Step 1: upload the photo unpublished so it becomes a story container.
        photo = self._post(
            f"/{page_id}/photos",
            {"url": media_url, "published": "false"},
            id_key="id",
        )
        # Step 2: publish that photo id as a story.
        return self._post(
            f"/{page_id}/photo_stories",
            {"photo_id": photo},
            id_key="post_id",
        )

    def _publish_video_story(self, media_url: str) -> str:
        page_id = self.creds.facebook_page_id
        token = self.creds.facebook_page_access_token

        # Step 1: start an upload session; response gives video_id + upload_url.
        started = self._raw(
            f"/{page_id}/video_stories", {"upload_phase": "start"}
        )
        video_id = started.get("video_id")
        upload_url = started.get("upload_url")
        if not (video_id and upload_url):
            raise PostError(f"Facebook video story start returned {started}")

        # Step 2: hand Facebook the public URL to fetch.
        upload_resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "file_url": media_url,
            },
            timeout=120,
        )
        try:
            upload = upload_resp.json()
        except ValueError:
            raise PostError(
                f"Facebook video story upload returned non-JSON (HTTP {upload_resp.status_code})"
            )
        if "error" in upload:
            raise PostError(
                f"Facebook video story upload failed: {upload['error'].get('message')}"
            )

        # Step 3: publish the finished video as a story.
        return self._post(
            f"/{page_id}/video_stories",
            {
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
            },
            id_key="post_id",
        )

    # ---- HTTP --------------------------------------------------------------

    def _raw(self, path: str, extra: dict) -> dict:
        """POST and return parsed JSON; raise on API error/non-JSON."""
        payload = {"access_token": self.creds.facebook_page_access_token, **extra}
        resp = requests.post(f"{GRAPH}{path}", data=payload, timeout=60)
        try:
            data = resp.json()
        except ValueError:
            raise PostError(f"Facebook API returned non-JSON (HTTP {resp.status_code})")
        if "error" in data:
            raise PostError(f"Facebook API error: {data['error'].get('message')}")
        return data

    def _post(self, path: str, extra: dict, id_key: str = "id") -> str:
        data = self._raw(path, extra)
        # photos return {id, post_id}; videos/feed return {id}. Callers pick.
        for key in (id_key, "post_id", "video_id", "id"):
            if data.get(key):
                return data[key]
        return ""
