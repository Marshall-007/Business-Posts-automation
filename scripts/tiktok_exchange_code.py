"""Exchange a TikTok OAuth authorization code for tokens, store them as secrets.

Runs in GitHub Actions (which can reach open.tiktokapis.com). Given a one-time
authorization code from the OAuth redirect, it obtains an access token + refresh
token and writes them to the TIKTOK_ACCESS_TOKEN / TIKTOK_REFRESH_TOKEN
repository secrets (encrypted with the repo public key). Tokens are never
printed.

Env vars:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET   app credentials
  TIKTOK_AUTH_CODE                           code from the redirect URL
  TIKTOK_REDIRECT_URI                        the exact redirect_uri used
  GH_PAT                                     fine-grained PAT (Secrets: write)
  GITHUB_REPOSITORY                          owner/repo (set by Actions)
"""

import base64
import os
import sys
from urllib.parse import unquote

import requests

TIKTOK = "https://open.tiktokapis.com/v2"
GITHUB = "https://api.github.com"


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
    # The code arrives URL-encoded in the redirect (it can contain '*' -> %2A).
    code = unquote(os.environ.get("TIKTOK_AUTH_CODE", "").strip())
    redirect = os.environ.get("TIKTOK_REDIRECT_URI", "").strip()
    pat = os.environ.get("GH_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not (client_key and client_secret and code and redirect):
        print("Missing client key/secret, auth code, or redirect URI.", file=sys.stderr)
        return 1

    resp = requests.post(
        f"{TIKTOK}/oauth/token/",
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    data = resp.json()
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not (access and refresh):
        print(f"Code exchange failed: {data.get('error_description') or data}",
              file=sys.stderr)
        print("The code is single-use and expires within minutes -- generate a "
              "fresh one from the authorize link and run this again quickly.",
              file=sys.stderr)
        return 1

    scopes = data.get("scope", "")
    hours = round((data.get("expires_in") or 0) / 3600, 1)
    print(f"Got a TikTok token (scopes: {scopes}); access token valid ~{hours}h.")

    if not (pat and repo):
        print("GH_PAT or GITHUB_REPOSITORY missing — cannot persist tokens.",
              file=sys.stderr)
        return 1

    update_secret(repo, pat, "TIKTOK_ACCESS_TOKEN", access)
    update_secret(repo, pat, "TIKTOK_REFRESH_TOKEN", refresh)
    print("Stored TIKTOK_ACCESS_TOKEN and TIKTOK_REFRESH_TOKEN. TikTok is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
