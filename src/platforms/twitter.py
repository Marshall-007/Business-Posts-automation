from requests_oauthlib import OAuth1Session

from .base import Platform, PostError


class Twitter(Platform):
    name = "twitter"

    def is_configured(self) -> bool:
        return all(
            [
                self.creds.twitter_api_key,
                self.creds.twitter_api_secret,
                self.creds.twitter_access_token,
                self.creds.twitter_access_token_secret,
            ]
        )

    def publish(self, text: str) -> str:
        session = OAuth1Session(
            self.creds.twitter_api_key,
            client_secret=self.creds.twitter_api_secret,
            resource_owner_key=self.creds.twitter_access_token,
            resource_owner_secret=self.creds.twitter_access_token_secret,
        )
        resp = session.post(
            "https://api.twitter.com/2/tweets", json={"text": text}, timeout=30
        )
        if resp.status_code >= 300:
            raise PostError(f"X/Twitter API error {resp.status_code}: {resp.text}")
        return resp.json().get("data", {}).get("id", "")
