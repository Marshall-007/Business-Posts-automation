"""Keep the Instagram access token alive and persist it back to the repo secret.

Runs in GitHub Actions (which can reach graph.instagram.com). It:
  1. Refreshes a long-lived (60-day) token, or if that fails and an app secret
     is available, exchanges a short-lived token for a long-lived one.
  2. Writes the new token back to the INSTAGRAM_ACCESS_TOKEN repository secret
     (encrypted with the repo public key), so the 60-day clock keeps resetting
     and the schedule never breaks.

Env vars:
  INSTAGRAM_ACCESS_TOKEN   current token (short- or long-lived)
  INSTAGRAM_APP_SECRET     optional; needed only to upgrade a short-lived token
  GH_PAT                   fine-grained PAT with "Secrets: write" on this repo
  GITHUB_REPOSITORY        owner/repo (provided automatically by Actions)

The token is never printed.
"""

import base64
import os
import sys

import requests

GRAPH = "https://graph.instagram.com"
GITHUB = "https://api.github.com"
SECRET_NAME = "INSTAGRAM_ACCESS_TOKEN"


def try_refresh(token: str):
    r = requests.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    ).json()
    return r.get("access_token"), r.get("expires_in"), r.get("error")


def try_exchange(token: str, app_secret: str):
    r = requests.get(
        f"{GRAPH}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": token,
        },
        timeout=30,
    ).json()
    return r.get("access_token"), r.get("expires_in"), r.get("error")


def update_secret(repo: str, pat: str, value: str) -> None:
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
        f"{GITHUB}/repos/{repo}/actions/secrets/{SECRET_NAME}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key["key_id"]},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> int:
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip()
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET", "").strip()
    pat = os.environ.get("GH_PAT", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if not token:
        print("No INSTAGRAM_ACCESS_TOKEN set — nothing to refresh.", file=sys.stderr)
        return 1

    new_token, expires, err = try_refresh(token)
    if not new_token and app_secret:
        print("Refresh did not apply; trying short-lived -> long-lived exchange.")
        new_token, expires, err = try_exchange(token, app_secret)

    if not new_token:
        msg = err.get("message") if isinstance(err, dict) else err
        print(f"Could not obtain a long-lived token: {msg}", file=sys.stderr)
        print(
            "Generate a fresh token in the Meta dashboard and set INSTAGRAM_APP_SECRET, "
            "then run this workflow again.",
            file=sys.stderr,
        )
        return 1

    days = round((expires or 0) / 86400, 1)
    print(f"Obtained a long-lived token valid for ~{days} days.")

    if not pat or not repo:
        print(
            "GH_PAT or GITHUB_REPOSITORY missing — cannot persist the token to the "
            "secret. Add a GH_PAT secret (Secrets: write) to enable auto-persistence.",
            file=sys.stderr,
        )
        return 1

    update_secret(repo, pat, new_token)
    print(f"Updated the {SECRET_NAME} secret. The schedule will keep working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
