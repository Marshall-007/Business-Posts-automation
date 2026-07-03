"""Mint a fresh TikTok access token and persist the rotated tokens as secrets.

TikTok access tokens live only ~24h; the refresh token lasts ~1 year and is
rotated on every refresh. This script runs in GitHub Actions (which can reach
open.tiktokapis.com) several times a day. It:
  1. Exchanges TIKTOK_REFRESH_TOKEN for a new access token (+ new refresh token).
  2. Writes TIKTOK_ACCESS_TOKEN and the rotated TIKTOK_REFRESH_TOKEN back to the
     repo secrets, so the posting workflow always has a valid 24h token and the
     refresh token never goes stale.

Env vars:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET   app credentials
  TIKTOK_REFRESH_TOKEN                       current refresh token
  GH_PAT                                     fine-grained PAT (Secrets: write)
  GITHUB_REPOSITORY                          owner/repo (set by Actions)

Tokens are never printed.
"""

import base64
import os
import sys

import requests

TIKTOK = "https://open.tiktokapis.com/v2"
GITHUB = "https://api.github.com"


def refresh(client_key: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        f"{TIKTOK}/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    return resp.json()


def update_secret(repo: str, pat: str, name: str, value: str) -> None:
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key = requests.get(
        f"{GITHUB}/repos/{repo}/actions/secrets/public-key", headers=headers, timeout=30
    )
    key.raise_for_status()
    key = key.json()

    pub = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pub).encrypt(value.encode())
    encrypted = base64.b64encode(sealed).decode()

    resp = requests.put(
        f"{GITHUB}/repos/{repo}/actions/secrets/{name}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key["key_id"]},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> int:
    client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()
    pat = os.environ.get("GH_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not (client_key and client_secret and refresh_token):
        print("TikTok client key/secret/refresh token missing — nothing to do.",
              file=sys.stderr)
        return 1

    data = refresh(client_key, client_secret, refresh_token)
    access = data.get("access_token")
    new_refresh = data.get("refresh_token") or refresh_token
    if not access:
        print(f"TikTok refresh failed: {data.get('error_description') or data}",
              file=sys.stderr)
        return 1

    hours = round((data.get("expires_in") or 0) / 3600, 1)
    print(f"Obtained a TikTok access token valid for ~{hours}h.")

    if not pat or not repo:
        print("GH_PAT or GITHUB_REPOSITORY missing — cannot persist tokens.",
              file=sys.stderr)
        return 1

    update_secret(repo, pat, "TIKTOK_ACCESS_TOKEN", access)
    update_secret(repo, pat, "TIKTOK_REFRESH_TOKEN", new_refresh)
    print("Updated TIKTOK_ACCESS_TOKEN and TIKTOK_REFRESH_TOKEN secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
