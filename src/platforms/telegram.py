import requests

from .base import Platform, PostError


class Telegram(Platform):
    name = "telegram"

    def is_configured(self) -> bool:
        return bool(self.creds.telegram_bot_token and self.creds.telegram_chat_id)

    def publish(self, text: str) -> str:
        url = f"https://api.telegram.org/bot{self.creds.telegram_bot_token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": self.creds.telegram_chat_id, "text": text},
            timeout=30,
        )
        data = resp.json()
        if not data.get("ok"):
            raise PostError(f"Telegram API error: {data.get('description', resp.text)}")
        return str(data["result"]["message_id"])
