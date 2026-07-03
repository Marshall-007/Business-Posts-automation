"""TikTok publisher (Content Posting API, Direct Post).

Mirrors feed content to TikTok:
  - videos  -> a TikTok video, uploaded straight from the repo file bytes
               (FILE_UPLOAD, so no media-domain verification is needed).
  - photos  -> a TikTok photo post, pulled from the public media URL
               (PULL_FROM_URL, which requires the media domain to be verified
               in the TikTok developer portal).

TikTok has no public Stories API, so Instagram stories are not sent to TikTok.

Auth: the durable secret is the refresh token (valid ~1 year). A short-lived
(24h) access token is used per post; TIKTOK_ACCESS_TOKEN is used if present
(refreshed out-of-band by scripts/refresh_tiktok_token.py), otherwise one is
minted on the spot from the refresh token.

Privacy: unaudited apps may only post SELF_ONLY (visible to the account owner).
After TikTok approves the app, set TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE.
"""

import os

import requests

from .base import Platform, PostError

API = "https://open.tiktokapis.com/v2"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


class TikTok(Platform):
    name = "tiktok"

    def is_configured(self) -> bool:
        return bool(
            self.creds.tiktok_client_key
            and self.creds.tiktok_client_secret
            and (self.creds.tiktok_refresh_token or self.creds.tiktok_access_token)
        )

    # ---- auth --------------------------------------------------------------

    def _access_token(self) -> str:
        if self.creds.tiktok_access_token:
            return self.creds.tiktok_access_token
        resp = requests.post(
            f"{API}/oauth/token/",
            data={
                "client_key": self.creds.tiktok_client_key,
                "client_secret": self.creds.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.creds.tiktok_refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise PostError(f"TikTok token refresh failed: {data.get('error_description') or data}")
        return token

    def _post_info(self, caption: str) -> dict:
        return {
            "title": (caption or "")[:2200],
            "privacy_level": self.creds.tiktok_privacy_level,
            "disable_comment": False,
        }

    # ---- publish -----------------------------------------------------------

    def publish(self, text: str) -> str:
        raise PostError("TikTok requires media; use publish_media")

    def publish_media(
        self,
        caption: str,
        media_url: str,
        post_type: str = "feed",
        is_video: bool = False,
        media_path: str | None = None,
    ) -> str:
        """Post one item to TikTok. Stories are not supported and are skipped."""
        if (post_type or "feed").lower() == "story":
            raise PostError("TikTok has no Stories API; skipped")
        token = self._access_token()
        if is_video:
            return self._post_video(token, caption, media_url, media_path)
        return self._post_photo(token, caption, media_url)

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _post_video(self, token, caption, media_url, media_path) -> str:
        data = self._read_bytes(media_url, media_path)
        size = len(data)
        init = requests.post(
            f"{API}/post/publish/video/init/",
            headers=self._headers(token),
            json={
                "post_info": self._post_info(caption),
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            },
            timeout=60,
        ).json()
        self._raise_on_error(init, "video init")
        info = init.get("data", {})
        upload_url = info.get("upload_url")
        publish_id = info.get("publish_id")
        if not upload_url:
            raise PostError(f"TikTok video init returned no upload_url: {init}")

        put = requests.put(
            upload_url,
            data=data,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            timeout=180,
        )
        if put.status_code not in (200, 201, 206):
            raise PostError(f"TikTok video upload failed (HTTP {put.status_code})")
        return publish_id or ""

    def _post_photo(self, token, caption, media_url) -> str:
        init = requests.post(
            f"{API}/post/publish/content/init/",
            headers=self._headers(token),
            json={
                "post_info": self._post_info(caption),
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "photo_cover_index": 0,
                    "photo_images": [media_url],
                },
                "post_mode": "DIRECT_POST",
                "media_type": "PHOTO",
            },
            timeout=60,
        ).json()
        self._raise_on_error(init, "photo init")
        return init.get("data", {}).get("publish_id", "")

    # ---- helpers -----------------------------------------------------------

    def _read_bytes(self, media_url: str, media_path: str | None) -> bytes:
        """Prefer the local repo file (the runner has it); fall back to the URL."""
        if media_path and os.path.isfile(media_path):
            with open(media_path, "rb") as fh:
                return fh.read()
        resp = requests.get(media_url, timeout=120)
        if resp.status_code != 200:
            raise PostError(f"TikTok could not read media (HTTP {resp.status_code})")
        return resp.content

    @staticmethod
    def _raise_on_error(payload: dict, phase: str) -> None:
        err = (payload or {}).get("error") or {}
        code = err.get("code")
        if code and code != "ok":
            raise PostError(f"TikTok {phase} error: {err.get('message') or code}")
