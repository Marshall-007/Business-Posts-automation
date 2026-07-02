import requests

from .base import Platform, PostError


class LinkedIn(Platform):
    name = "linkedin"

    def is_configured(self) -> bool:
        return bool(
            self.creds.linkedin_access_token and self.creds.linkedin_author_urn
        )

    def publish(self, text: str) -> str:
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {self.creds.linkedin_access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json={
                "author": self.creds.linkedin_author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise PostError(f"LinkedIn API error {resp.status_code}: {resp.text}")
        return resp.headers.get("x-restli-id", "")
